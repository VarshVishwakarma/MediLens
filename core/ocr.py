import os
import cv2
import pytesseract
import re
import time
import uuid

def create_med_words_file():
    filepath = "/tmp/med_words.txt"
    if not os.path.exists(filepath):
        words = [
            "paracetamol", "ibuprofen", "tablet", "mg", "capsule", 
            "syrup", "prescription", "dose", "daily", "ml"
        ]
        try:
            with open(filepath, "w") as f:
                f.write("\n".join(words))
        except Exception as e:
            print(f"Could not write medical dictionary: {e}")
    return filepath

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
        
        success = cv2.imwrite(temp_path, img, [cv2.IMWRITE_JPEG_QUALITY, 60])
        return temp_path if success else image_path
    except Exception as e:
        print(f"Image compression failed: {e}")
        return image_path

def tesseract_ocr(image_path):
    try:
        img = cv2.imread(image_path)
        if img is None:
            print("Tesseract OCR failed: Could not read image.")
            return ""

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        med_words_path = create_med_words_file()
        config = f"--oem 3 --psm 6 -c user_words_file={med_words_path}"
        
        text = pytesseract.image_to_string(thresh, config=config, timeout=2)
        
        if text:
            text = re.sub(r'\s+', ' ', text).strip().lower()[:1000]
            return text
            
        return ""
    except RuntimeError:
        print("Tesseract failed: Process timed out.")
        return ""
    except Exception as e:
        print(f"Tesseract OCR exception: {e}")
        return ""

def extract_text(image_path):
    start_time = time.time()
    print("Using Tesseract OCR")
    
    compressed_path = compress_image(image_path)
    
    text = tesseract_ocr(compressed_path)
    
    if compressed_path != image_path and os.path.exists(compressed_path):
        os.remove(compressed_path)
        
    length = len(text)
    print(f"OCR length: {length}")
    
    valid_words = sum(1 for w in text.split() if len(w) > 3)
    
    if length > 50 and valid_words >= 2:
        confidence = "high"
    elif length > 20:
        confidence = "medium"
    else:
        confidence = "low"

    print(f"Processing time: {time.time() - start_time:.2f} sec")

    return {
        "text": text,
        "source": "tesseract",
        "confidence": confidence
    }
