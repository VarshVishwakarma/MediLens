import os
import requests

def extract_text(image_path: str) -> dict:
    try:
        api_key = os.getenv("OCR_SPACE_API_KEY")
        url = "https://api.ocr.space/parse/image"
        
        payload = {
            "apikey": api_key,
            "language": "eng",
            "OCREngine": "1",
            "scale": "true",
            "detectOrientation": "true"
        }
        
        with open(image_path, "rb") as image_file:
            response = requests.post(
                url,
                files={"file": image_file},
                data=payload,
                timeout=15
            )
            
        response.raise_for_status()
        result = response.json()
        
        if result.get("IsErroredOnProcessing"):
            raise ValueError("OCR processing errored")
            
        parsed_results = result.get("ParsedResults", [])
        text = " ".join([r.get("ParsedText", "") for r in parsed_results])
        
        cleaned_text = text.strip().lower()[:1000]
        
        valid_words = sum(1 for word in cleaned_text.split() if len(word) > 3)
        
        if valid_words >= 3:
            confidence = "high"
        elif valid_words >= 1:
            confidence = "medium"
        else:
            confidence = "low"
            
        return {
            "text": cleaned_text,
            "source": "ocr_space",
            "confidence": confidence
        }
        
    except Exception:
        return {
            "text": "",
            "source": "ocr_space",
            "confidence": "low"
        }
