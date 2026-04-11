import re
import io
import logging
from typing import Dict, Any, List, Tuple

import cv2
import numpy as np
import pytesseract
from PIL import Image

class OCRService:
    """
    A robust OCR service designed for medical prescription scanning.
    Handles image preprocessing, text extraction, and token/signal parsing.
    """

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.logger = logging.getLogger(__name__)
        
        # Setup basic logging if not already configured
        if not self.logger.handlers:
            logging.basicConfig(level=logging.INFO if not debug else logging.DEBUG)

    def _bytes_to_cv2(self, image_bytes: bytes) -> np.ndarray:
        """
        Safely decodes raw image bytes into a format OpenCV can process,
        using Pillow to handle a wide variety of image formats.
        """
        try:
            # Load bytes using PIL
            image = Image.open(io.BytesIO(image_bytes))
            
            # Convert to RGB to ensure consistent channel structure
            if image.mode != 'RGB':
                image = image.convert('RGB')
                
            # Convert PIL Image to numpy array
            open_cv_image = np.array(image)
            
            # Convert RGB to BGR (OpenCV's default color format)
            open_cv_image = open_cv_image[:, :, ::-1].copy()
            return open_cv_image
            
        except Exception as e:
            raise ValueError(f"Failed to parse image bytes: {e}")

    def preprocess_image(self, image_bytes: bytes, strategy: str = 'adaptive') -> np.ndarray:
        """
        Enhances the image to make text as clear as possible for Tesseract.
        Includes resizing, contrast enhancement, and thresholding.
        
        Strategies:
            - 'adaptive': Best for uneven lighting (shadows on prescriptions).
            - 'otsu': Best for high-contrast, well-lit images.
        """
        img = self._bytes_to_cv2(image_bytes)

        # 1. Convert to Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 2. Resize (Scale up 2x) - Tesseract performs better on characters ~30px height
        resized = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

        # 3. Contrast Enhancement (CLAHE) - Solves local washout and shadows
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast = clahe.apply(resized)

        # 4. Thresholding to create a binary image (black/white)
        if strategy == 'adaptive':
            # Adaptive threshold handles varying illumination across the image
            processed = cv2.adaptiveThreshold(
                contrast, 255, 
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
        elif strategy == 'otsu':
            # Gaussian blur removes noise before global Otsu thresholding
            blur = cv2.GaussianBlur(contrast, (5, 5), 0)
            _, processed = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            # Fallback simple binary
            _, processed = cv2.threshold(contrast, 128, 255, cv2.THRESH_BINARY)

        # 5. Handwriting Boost: Morphological dilation to connect broken text lines
        kernel = np.ones((2, 2), np.uint8)
        processed = cv2.dilate(processed, kernel, iterations=1)

        # [DEBUG] Save intermediate image to disk if debug mode is active
        if self.debug:
            import os
            os.makedirs("/tmp/debug_ocr", exist_ok=True)
            debug_path = f"/tmp/debug_ocr/processed_{strategy}.png"
            cv2.imwrite(debug_path, processed)
            self.logger.debug(f"Saved debug image to {debug_path}")

        return processed

    def extract_text(self, image_bytes: bytes, strategy: str = 'adaptive') -> Tuple[str, float]:
        """
        Preprocesses the image and performs OCR using Tesseract.
        Cleans up the resulting text and calculates a confidence score.
        """
        try:
            processed_img = self.preprocess_image(image_bytes, strategy=strategy)
            
            # oem 3: Default LSTM engine
            # psm 6: Assume a single uniform block of text (good for prescription bodies)
            config = "--oem 3 --psm 6"
            
            # Extract raw string for layout mapping
            raw_text = pytesseract.image_to_string(processed_img, config=config)
            
            # Extract confidence scores
            data = pytesseract.image_to_data(processed_img, config=config, output_type=pytesseract.Output.DICT)
            valid_confidences = [int(c) for c in data['conf'] if int(c) >= 0]
            avg_conf = sum(valid_confidences) / len(valid_confidences) if valid_confidences else 0.0

            # Noise Filtering: Remove everything except alphanumeric, spaces, and periods
            cleaned_text = re.sub(r'[^a-zA-Z0-9\s\.]', '', raw_text)

            # Clean output spacing and newlines
            cleaned_text = cleaned_text.strip()
            # Replace multiple inline spaces/tabs with a single space
            cleaned_text = re.sub(r'[ \t]+', ' ', cleaned_text)
            # Remove excessive empty lines
            cleaned_text = re.sub(r'\n\s*\n', '\n', cleaned_text)
            
            return cleaned_text, avg_conf

        except Exception as e:
            self.logger.error(f"Text extraction failed: {e}")
            raise

    def extract_signals(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Orchestrates the OCR process and uses regex to find structured signals.
        Implements a fallback mechanism across different preprocessing strategies.
        """
        try:
            # Fallback Loop: Try 'adaptive' first, if result is poor, try 'otsu'
            extracted_text = ""
            confidence = 0.0
            
            for strategy in ['adaptive', 'otsu']:
                extracted_text, confidence = self.extract_text(image_bytes, strategy=strategy)
                if len(extracted_text.strip()) > 10: 
                    # If we captured a meaningful amount of text, break the loop
                    break

            if not extracted_text:
                return {"error": "Failed to extract legible text from the image. Ensure the image is well-lit and focused."}

            # 1. Line Extraction (Preserve structured lines)
            lines = [line.strip() for line in extracted_text.split("\n") if line.strip()]

            # 2. Smart Tokenization (Handle compound medical terms & delimiters gracefully)
            raw_tokens = re.split(r'[\s,;:()-]+', extracted_text)
            tokens = [t.strip() for t in raw_tokens if t.strip()]

            # 3. Dosage Pattern Detection (e.g., 500mg, 10 ml, 2.5g, 50mcg, 100 IU)
            # Matches digits (with optional decimals), optional spaces, and specific units
            dosage_pattern = r'\b\d+(?:\.\d+)?\s*(?:mg|ml|g|mcg|µg|IU)\b'
            raw_dosages = re.findall(dosage_pattern, extracted_text, flags=re.IGNORECASE)
            
            # Standardize dosage formatting (remove spaces, lowercase) and deduplicate
            normalized_dosages = list(dict.fromkeys([d.lower().replace(" ", "") for d in raw_dosages]))

            return {
                "raw_text": extracted_text,
                "confidence": round(confidence, 2),
                "lines": lines,
                "tokens": tokens,
                "dosages": normalized_dosages
            }

        except ValueError as ve:
            self.logger.warning(f"Validation error: {ve}")
            return {"error": f"Invalid image format: {str(ve)}"}
        except Exception as e:
            self.logger.error(f"Signal extraction failed with unexpected error: {e}")
            return {"error": "An internal system error occurred during image processing."}

# ==============================================================================
# Example Usage Block (for testing locally)
# ==============================================================================
if __name__ == "__main__":
    # Setup test
    ocr = OCRService(debug=True)
    
    # Try reading a mock local file if running directly
    try:
        with open("sample_prescription.jpg", "rb") as f:
            test_bytes = f.read()
            
        result = ocr.extract_signals(test_bytes)
        print("--- OCR Result ---")
        import json
        print(json.dumps(result, indent=2))
        
    except FileNotFoundError:
        print("sample_prescription.jpg not found. Place a file in the directory to test locally.")