import os
import logging
from typing import Union, Dict, Tuple, Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

class ImagePreprocessor:
    """
    A robust, production-grade image preprocessing pipeline optimized for OCR
    on medicine boxes and handwritten prescriptions. 
    Designed for high speed and accuracy without relying on heavy ML models.
    """

    def __init__(self):
        pass

    def load_image(self, file_path_or_bytes: Union[str, bytes]) -> np.ndarray:
        """
        Safely loads an image from a file path or raw bytes.
        Returns the image as an OpenCV array (BGR format).
        """
        try:
            if isinstance(file_path_or_bytes, bytes):
                # Decode raw bytes directly to OpenCV image
                nparr = np.frombuffer(file_path_or_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is None:
                    raise ValueError("Could not decode image from bytes.")
                return img
            
            elif isinstance(file_path_or_bytes, str):
                # Read from file path
                if not os.path.exists(file_path_or_bytes):
                    raise FileNotFoundError(f"Image not found at path: {file_path_or_bytes}")
                img = cv2.imread(file_path_or_bytes)
                if img is None:
                    raise ValueError(f"Could not read image from path: {file_path_or_bytes}")
                return img
                
            else:
                raise TypeError("Input must be a file path (str) or raw bytes (bytes).")
                
        except Exception as e:
            logger.error(f"Error loading image: {e}")
            raise

    def calculate_quality_score(self, image: np.ndarray) -> float:
        """
        Calculates a quality/sharpness score (0.0 to 1.0) using the variance of the Laplacian.
        Higher variance means more edges (sharper image).
        """
        gray = self.to_grayscale(image) if len(image.shape) == 3 else image
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        # Typically, < 100 is blurry, > 500 is sharp. Cap at 1000 for normalization.
        score = min(laplacian_var / 1000.0, 1.0)
        return round(float(score), 2)

    def resize_image(self, image: np.ndarray, scale: float = 2.0) -> np.ndarray:
        """
        Upscales the image to improve OCR character recognition accuracy.
        Maintains aspect ratio and uses cubic interpolation for better quality.
        """
        if image is None:
            raise ValueError("Input image is None.")
        
        # INTER_CUBIC is slower but produces sharper scaled images than INTER_LINEAR
        return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    def to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """
        Converts a BGR image to grayscale.
        """
        if len(image.shape) == 2:
            return image  # Already grayscale
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    def deskew(self, image: np.ndarray) -> np.ndarray:
        """
        Detects text skew angle and rotates the image to correct it.
        Assumes input is a grayscale image.
        """
        # Create a binary image with text as white, background as black
        _, thresh = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(thresh > 0))
        
        if len(coords) == 0:
            return image
            
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]
        
        # Normalize angle to the range [-45, 45]
        if angle > 45:
            angle = angle - 90
        elif angle < -45:
            angle = angle + 90
            
        # Ignore extremely small rotations or unreasonable angles (> 20 degrees)
        if abs(angle) < 0.5 or abs(angle) > 20:
            return image
            
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        # Use BORDER_REPLICATE to avoid black corners after rotation
        rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return rotated

    def denoise(self, image: np.ndarray) -> np.ndarray:
        """
        Reduces image noise while preserving edges using a Gaussian blur.
        Useful for low-light images or high-ISO noise.
        """
        # 3x3 kernel provides gentle blurring without destroying text edges
        return cv2.GaussianBlur(image, (3, 3), 0)

    def sharpen(self, image: np.ndarray) -> np.ndarray:
        """
        Applies a sharpening kernel to enhance the edges of text,
        compensating for any blur introduced during resizing or denoising.
        """
        # Standard sharpening kernel
        kernel = np.array([
            [ 0, -1,  0],
            [-1,  5, -1],
            [ 0, -1,  0]
        ], dtype=np.float32)
        return cv2.filter2D(image, -1, kernel)

    def enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """
        Enhances contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization).
        Crucial for evening out shadows and uneven lighting common in phone scans.
        """
        # clipLimit=2.0 and tileGridSize=(8,8) are standard reliable defaults
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(image)

    def smart_threshold(self, image: np.ndarray) -> np.ndarray:
        """
        Dynamically chooses between Adaptive and Otsu thresholding.
        Adaptive is used for uneven lighting; Otsu is used for uniform lighting.
        """
        # Estimate background illumination variance by heavily blurring
        bg_blur = cv2.GaussianBlur(image, (51, 51), 0)
        lighting_variance = np.var(bg_blur)
        
        # High variance in background implies uneven lighting/shadows
        if lighting_variance > 500:
            return cv2.adaptiveThreshold(
                image, 255, 
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
        else:
            # Low variance implies uniform lighting; Otsu excels here
            _, thresh = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
            return thresh

    def morphological_operations(self, image: np.ndarray) -> np.ndarray:
        """
        Applies morphological operations (closing: dilation followed by erosion)
        to connect broken characters and remove small artifacts.
        """
        # A tiny 2x2 kernel ensures we don't accidentally merge separate letters
        kernel = np.ones((2, 2), np.uint8)
        
        # Dilate to connect broken pen strokes
        dilated = cv2.dilate(image, kernel, iterations=1)
        # Erode to trim back the thickened strokes
        eroded = cv2.erode(dilated, kernel, iterations=1)
        
        return eroded

    def preprocess_pipeline(
        self, 
        file_path_or_bytes: Union[str, bytes], 
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Combines all preprocessing steps in the optimal order for OCR.
        
        Args:
            file_path_or_bytes: The input image (path or bytes).
            debug: If True, includes intermediate images in the return dict.
                   
        Returns:
            A dictionary containing the final processed image and quality score.
            Example: {"processed_image": img, "quality_score": 0.87}
        """
        try:
            debug_steps = {}
            
            # 1. Load Image
            img = self.load_image(file_path_or_bytes)
            quality_score = self.calculate_quality_score(img)
            if debug: debug_steps['1_original'] = img.copy()

            # 2. Resize
            img = self.resize_image(img, scale=2.0)
            if debug: debug_steps['2_resized'] = img.copy()

            # 3. Grayscale
            img = self.to_grayscale(img)
            if debug: debug_steps['3_grayscale'] = img.copy()

            # 4. Deskew (Optimal to do on grayscale before heavy contrasting)
            img = self.deskew(img)
            if debug: debug_steps['4_deskewed'] = img.copy()

            # 5. Denoise
            img = self.denoise(img)
            if debug: debug_steps['5_denoised'] = img.copy()

            # 6. Sharpen
            img = self.sharpen(img)
            if debug: debug_steps['6_sharpened'] = img.copy()

            # 7. Enhance Contrast
            img = self.enhance_contrast(img)
            if debug: debug_steps['7_contrast'] = img.copy()

            # 8. Smart Threshold
            img = self.smart_threshold(img)
            if debug: debug_steps['8_thresholded'] = img.copy()

            # 9. Morphological Operations
            img = self.morphological_operations(img)
            if debug: debug_steps['9_morphological'] = img.copy()

            result = {
                "processed_image": img,
                "quality_score": quality_score
            }
            
            if debug:
                result["debug_steps"] = debug_steps
                
            return result

        except Exception as e:
            logger.error(f"Preprocessing pipeline failed: {e}")
            raise