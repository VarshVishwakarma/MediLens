import os
import base64
import requests
import cv2
import pytesseract
import time

def _setup_tesseract_bias():
    """Creates a custom dictionary file to bias Tesseract towards medical terms."""
    bias_file = "/tmp/med_words.txt"
    if not os.path.exists(bias_file):
        medical_terms = ["mg", "ml", "tablet", "pill", "capsule", "BD", "TDS", "SOS", "OD", "paracetamol", "ibuprofen"]
        with open(bias_file, "w") as f:
            f.write("\n".join(medical_terms))
    return bias_file

def google_ocr(image_path):
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Google OCR failed: Missing GOOGLE_API_KEY environment variable.")
        return ""

    try:
        with open(image_path, "rb") as image_file:
            content = base64.b64encode(image_file.read()).decode("utf-8")

        url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
        payload = {
            "requests": [
                {
                    "image": {"content": content},
                    "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                    "imageContext": {"languageHints": ["en"]}  # 3. Language Hint (BIG BOOST)
                }
            ]
        }

        # 4. Rate Limit / Retry Logic with Escalating Timeout
        for attempt in range(2):
            timeout_val = 5 + (attempt * 5)  # 1. Timeout Strategy Escalation
            try:
                response = requests.post(url, json=payload, timeout=timeout_val)
                
                if response.status_code == 200:
                    result = response.json()
                    if "responses" in result and result["responses"]:
                        annotations = result["responses"][0]
                        if "fullTextAnnotation" in annotations:
                            return annotations["fullTextAnnotation"].get("text", "")
                    return ""
                else:
                    # Debug Visibility
                    print(f"Google OCR failed (Attempt {attempt + 1}):", response.text)
                    time.sleep(1) # Brief backoff before retry
            except requests.exceptions.RequestException as req_err:
                print(f"Google OCR network error (Attempt {attempt + 1}, timeout={timeout_val}s): {req_err}")
                time.sleep(1)

        return ""
    except Exception as e:
        print(f"Google OCR exception: {e}")
        return ""

def tesseract_ocr(image_path):
    try:
        img = cv2.imread(image_path)
        if img is None:
            print("Tesseract OCR failed: Could not read image.")
            return ""
        
        # Preprocessing for Tesseract
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        
        # 4. Medicine Biasing
        bias_file = _setup_tesseract_bias()
        custom_config = f'--oem 3 --psm 6 -c user_words_file={bias_file}'
        
        text = pytesseract.image_to_string(thresh, config=custom_config)
        return text if text else ""
    except Exception as e:
        print(f"Tesseract OCR exception: {e}")
        return ""

def extract_text(image_path):
    print("Using Google OCR")
    text = google_ocr(image_path)
    source = "google"

    # Confidence Awareness
    # Treat as low confidence if text is too short or lacks alphabetical characters
    is_confident = text and len(text.strip()) >= 10 and any(c.isalpha() for c in text)
    confidence = "high" if is_confident else "low"

    if not is_confident:
        print("Falling back to Tesseract (Google OCR result weak, short, or empty)")
        text = tesseract_ocr(image_path)
        source = "tesseract"
        
        # Re-evaluate confidence for Tesseract fallback
        is_confident = text and len(text.strip()) >= 10 and any(c.isalpha() for c in text)
        confidence = "medium" if is_confident else "low"

    if not text or not text.strip():
        print("OCR failed completely on both engines")
        return {
            "text": "",
            "source": "none",
            "confidence": "low"
        }

    # 2. Structured Output
    return {
        "text": text.strip(),
        "source": source,
        "confidence": confidence
    }
