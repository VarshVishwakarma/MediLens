import os
import requests
import cv2
import pytesseract
import re
import time
import uuid

def compress_image(image_path):
    try:
        img = cv2.imread(image_path)
        if img is None:
            return image_path
        
        h, w = img.shape[:2]
        max_dim = max(h, w)
        if max_dim > 800:
            scale = 800.0 / max_dim
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        
        filename = os.path.basename(image_path)
        if not filename.lower().endswith(('.jpg', '.jpeg')):
            filename += ".jpg"
            
        # Fix 5: Prevent collision with UUID
        temp_path = os.path.join("/tmp", f"compressed_{uuid.uuid4().hex}_{filename}")
        cv2.imwrite(temp_path, img, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return temp_path
    except Exception as e:
        print(f"Image compression failed: {e}")
        return image_path

def ocr_space(image_path):
    api_key = os.environ.get("OCR_SPACE_API_KEY")
    if not api_key:
        print("OCR.space failed: Missing OCR_SPACE_API_KEY environment variable.")
        return ""

    for attempt in range(2):
        try:
            with open(image_path, "rb") as image_file:
                payload = {
                    "apikey": api_key,
                    "language": "eng",
                    "OCREngine": "1",
                    "scale": "true",
                    "detectOrientation": "true"
                }
                response = requests.post(
                    "https://api.ocr.space/parse/image",
                    files={"file": image_file},
                    data=payload,
                    timeout=15
                )

            if response.status_code == 200:
                result = response.json()
                if not result.get("IsErroredOnProcessing"):
                    parsed_results = result.get("ParsedResults", [])
                    text = "\n".join([res.get("ParsedText", "") for res in parsed_results])
                    return text.strip()
                else:
                    print(f"OCR.space API error (Attempt {attempt + 1}): {result.get('ErrorMessage')}")
            else:
                print(f"OCR.space failed (Attempt {attempt + 1}): HTTP {response.status_code}")
            
            time.sleep(1)
        except Exception as e:
            print(f"OCR.space exception (Attempt {attempt + 1}): {e}")
            time.sleep(1)

    return ""

def tesseract_ocr(image_path):
    try:
        img = cv2.imread(image_path)
        if img is None:
            print("Tesseract OCR failed: Could not read image.")
            return ""

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        text = pytesseract.image_to_string(thresh)
        return text.strip() if text else ""
    except Exception as e:
        print(f"Tesseract OCR exception: {e}")
        return ""

def extract_text(image_path):
    # Fix 3: API Latency Logging start
    start_time = time.time()
    
    compressed_path = compress_image(image_path)
    
    print("Using OCR.space")
    text = ocr_space(compressed_path)
    source = "ocr_space"

    valid_words = sum(1 for w in text.split() if len(w) > 3)
    is_confident = text and len(text) >= 10 and valid_words >= 2

    # Fix 2: Early Exit Optimization
    if is_confident and len(text) > 50:
        text = re.sub(r'\s+', ' ', text).strip().lower()[:1000]
        print(f"OCR time: {time.time() - start_time:.2f}s")
        return {
            "text": text,
            "source": source,
            "confidence": "high"
        }

    if not is_confident:
        print("Fallback to Tesseract")
        # Fix 1: Pass compressed_path instead of original image_path
        text = tesseract_ocr(compressed_path)
        source = "tesseract"

    if text:
        text = re.sub(r'\s+', ' ', text)
        text = text.strip().lower()
        text = text[:1000]
        print(f"OCR length: {len(text)}")

    if not text:
        source = "none"
        confidence = "low"
    else:
        # Fix 4: Smarter Confidence Logic
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

    # Fix 3: API Latency Logging end
    print(f"OCR time: {time.time() - start_time:.2f}s")

    return {
        "text": text,
        "source": source,
        "confidence": confidence
    }
