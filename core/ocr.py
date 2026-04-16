import os
import time
import requests

def easyocr_api(image_path):
    api_key = os.getenv("EASYOCR_API_KEY")
    if not api_key:
        print("Missing EASYOCR_API_KEY environment variable.")
        return ""

    try:
        with open(image_path, "rb") as image_file:
            response = requests.post(
                "https://app.easyocr.es/api/v1/ocr/file",
                headers={"X-API-Key": api_key},
                files={"file": image_file},
                data={"structure": "false"},
                timeout=10
            )

        if response.status_code != 200:
            return ""

        result = response.json()
        
        if result.get("status") != "success":
            return ""

        if "text" in result:
            text = result["text"]
        elif "structured_data" in result:
            text = str(result["structured_data"])
        else:
            text = ""

        print("RAW OCR OUTPUT:", text)

        return text.lower().strip()
        
    except Exception as e:
        print(f"EasyOCR API Exception: {e}")
        return ""

def extract_text(image_path):
    start_time = time.time()
    print("Using EasyOCR API")
    
    text = easyocr_api(image_path)
    source = "easyocr_api"

    if not text or len(text) < 10:
        return {
            "text": "",
            "source": "none",
            "confidence": "low"
        }

    length = len(text)

    if length > 50:
        confidence = "high"
    elif length > 20:
        confidence = "medium"
    else:
        confidence = "low"

    print(f"OCR length: {length}")
    print(f"Processing time: {time.time() - start_time:.2f} sec")

    return {
        "text": text,
        "source": source,
        "confidence": confidence
    }
