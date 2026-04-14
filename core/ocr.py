import os
import requests
import cv2
import pytesseract
import re
import time

def ocr_space(image_path):
    api_key = os.environ.get("OCR_SPACE_API_KEY")
    if not api_key:
        print("OCR.space failed: Missing OCR_SPACE_API_KEY environment variable.")
        return ""

    # Adding a retry loop for API resilience
    for attempt in range(2):
        try:
            with open(image_path, "rb") as image_file:
                payload = {
                    "apikey": api_key,
                    "language": "eng",
                    "OCREngine": "2",
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
            
            time.sleep(1) # Brief wait before retrying
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
    print("Using OCR.space")
    text = ocr_space(image_path)
    source = "ocr_space"

    # OCR Quality Check: Focus on actual legible words rather than string length
    valid_words = sum(1 for w in text.split() if len(w) > 3)
    is_confident = valid_words >= 2

    if not is_confident:
        print("Fallback to Tesseract")
        text = tesseract_ocr(image_path)
        source = "tesseract"

    # Text Cleaning (Crucial OCR normalization step)
    if text:
        text = re.sub(r'\s+', ' ', text)
        text = text.strip().lower()
        print("OCR Output:", text[:100])

    if not text:
        source = "none"
        confidence = "low"
    else:
        # Multi-tier length-based confidence
        if len(text) > 50:
            confidence = "high"
        elif len(text) > 20:
            confidence = "medium"
        else:
            confidence = "low"

    return {
        "text": text,
        "source": source,
        "confidence": confidence
    }
