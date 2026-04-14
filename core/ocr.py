import os
import requests
import cv2
import pytesseract
import re
import time
import uuid
import base64

def compress_image(image_path):
    try:
        img = cv2.imread(image_path)
        if img is None:
            return image_path
        
        h, w = img.shape[:2]
        max_dim = max(h, w)
        if max_dim > 600:
            scale = 600.0 / max_dim
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        
        filename = os.path.basename(image_path)
        if not filename.lower().endswith(('.jpg', '.jpeg')):
            filename += ".jpg"
            
        temp_path = os.path.join("/tmp", f"compressed_{uuid.uuid4().hex}_{filename}")
        
        success = cv2.imwrite(temp_path, img, [cv2.IMWRITE_JPEG_QUALITY, 50])
        return temp_path if success else image_path
    except Exception as e:
        print(f"Image compression failed: {e}")
        return image_path

def ocr_space(image_path):
    api_key = os.environ.get("OCR_SPACE_API_KEY")
    if not api_key:
        print("OCR.space failed: Missing OCR_SPACE_API_KEY environment variable.")
        return ""

    try:
        with open(image_path, "rb") as image_file:
            base64_string = base64.b64encode(image_file.read()).decode('utf-8')
            
        payload = {
            "apikey": api_key,
            "language": "eng",
            "OCREngine": "1",
            "scale": "true",
            "detectOrientation": "true",
            "base64Image": "data:image/jpeg;base64," + base64_string
        }
        
        start_time = time.time()
        
        response = requests.post(
            "https://api.ocr.space/parse/image",
            data=payload,
            timeout=(3, 6)
        )
        
        if time.time() - start_time > 8:
            print("Force exit OCR")
            return ""

        if response.status_code == 200:
            result = response.json()
            if not result.get("IsErroredOnProcessing"):
                parsed_results = result.get("ParsedResults", [])
                text = "\n".join([res.get("ParsedText", "") for res in parsed_results])
                return text.strip()
            else:
                print(f"OCR.space API error: {result.get('ErrorMessage')}")
        else:
            print(f"OCR.space failed: HTTP {response.status_code}")
            
    except requests.exceptions.Timeout:
        print("OCR.space timeout → skipping")
    except Exception as e:
        print(f"OCR.space exception: {e}")

    return ""

def tesseract_ocr(image_path):
    try:
        img = cv2.imread(image_path)
        if img is None:
            print("Tesseract OCR failed: Could not read image.")
            return ""

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        text = pytesseract.image_to_string(thresh, timeout=10)
        return text.strip() if text else ""
        
    except RuntimeError:
        print("Tesseract failed: Process timed out after 10 seconds.")
        return ""
    except Exception as e:
        print(f"Tesseract OCR exception: {e}")
        return ""

def extract_text(image_path):
    start_time = time.time()
    
    compressed_path = compress_image(image_path)
    
    print("Using OCR.space")
    text = ocr_space(compressed_path)
    source = "ocr_space"

    valid_words = sum(1 for w in text.split() if len(w) > 3)
    is_confident = text and len(text) >= 10 and valid_words >= 2

    if is_confident and len(text) > 50:
        text = re.sub(r'\s+', ' ', text).strip().lower()[:1000]
        print(f"OCR time: {time.time() - start_time:.2f}s")
        
        if compressed_path != image_path and os.path.exists(compressed_path):
            os.remove(compressed_path)
            
        return {
            "text": text,
            "source": source,
            "confidence": "high"
        }

    if not is_confident:
        print("Fallback to Tesseract")
        text = tesseract_ocr(compressed_path)
        source = "tesseract"

    if text:
        text = re.sub(r'\s+', ' ', text).strip().lower()[:1000]

    if not text:
        source = "none"
        confidence = "low"
    else:
        words = text.split()
        word_count = len(words)
        valid_words = sum(1 for w in words if len(w) > 3)
        has_numbers = any(c.isdigit() for c in text)
        valid_ratio = valid_words / word_count if word_count > 0 else 0

        if len(text) > 50 and valid_ratio >= 0.3 and has_numbers:
            confidence = "high"
        elif len(text) > 20 and valid_words >= 2:
            confidence = "medium"
        else:
            confidence = "low"

    print(f"OCR time: {time.time() - start_time:.2f}s")

    if compressed_path != image_path and os.path.exists(compressed_path):
        os.remove(compressed_path)

    return {
        "text": text,
        "source": source,
        "confidence": confidence
    }
