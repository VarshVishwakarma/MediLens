import os
import time
import requests

def easyocr_api(image_path):
    api_key = os.getenv("EASYOCR_API_KEY")
    if not api_key:
        print("Missing EASYOCR_API_KEY environment variable.")
        return ""

    start = time.time()

    try:
        with open(image_path, "rb") as image_file:
            for _ in range(2):
                if time.time() - start > 12:
                    print("OCR taking too long → aborting")
                    return ""
                    
                try:
                    # Seek to beginning in case this is a retry to prevent sending an empty payload
                    image_file.seek(0)
                    
                    response = requests.post(
                        "https://app.easyocr.es/api/v1/ocr/file",
                        headers={"X-API-Key": api_key},
                        files={"file": image_file},
                        data={"structure": "false"},
                        timeout=10
                    )

                    if response.status_code != 200:
                        print("EasyOCR HTTP Error:", response.text)
                        return ""

                    result = response.json()
                    
                    if result.get("status") != "success":
                        print("EasyOCR API Failed:", result)
                        return ""

                    if "text" in result:
                        text = result["text"]
                    elif "structured_data" in result:
                        text = str(result["structured_data"])
                    else:
                        text = ""

                    print("RAW OCR OUTPUT:", text)

                    return text.lower().strip()[:1000]
                    
                except requests.exceptions.RequestException:
                    print("Retrying OCR...")
                    time.sleep(1)
                except Exception as e:
                    print(f"EasyOCR API Exception: {e}")
                    return ""
                    
    except Exception as e:
        print(f"File handling exception: {e}")
        return ""
            
    return ""

def extract_text(image_path):
    start_time = time.time()
    print("Using EasyOCR API")
    
    text = easyocr_api(image_path)
    source = "easyocr_api"

    if not text or len(text) < 10:
        return {
            "text": "",
            "source": source,
            "confidence": "low"
        }

    valid_words = sum(1 for w in text.split() if len(w) > 3)

    if valid_words >= 3:
        confidence = "high"
    elif valid_words >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    print(f"OCR length: {len(text)}")
    print(f"Processing time: {time.time() - start_time:.2f} sec")

    return {
        "text": text,
        "source": source,
        "confidence": confidence
    }
