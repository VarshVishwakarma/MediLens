import os
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
        
        # FIX 2: PROPORTIONAL RESIZE (Max dimension 800) Prevents text distortion
        h, w = img.shape[:2]
        scale = 800 / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
        
        filename = os.path.basename(image_path)
        if not filename.lower().endswith(('.jpg', '.jpeg')):
            filename += ".jpg"
            
        temp_path = os.path.join("/tmp", f"compressed_{uuid.uuid4().hex}_{filename}")
        
        # FIX 2: AGGRESSIVE COMPRESSION (Quality 80)
        success = cv2.imwrite(temp_path, img, [cv2.IMWRITE_JPEG_QUALITY, 80])
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
        
        # FIX 3: ADD SHARPENING (BIG BOOST)
        gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)

        # PROBLEM 1 FIX: ADD THRESHOLDING
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

        # FIX 1: CHANGE PSM TO 6
        config = "--oem 3 --psm 6"
        
        # PROBLEM 3 FIX: TIMEOUT INCREASED TO 4 SECONDS
        text = pytesseract.image_to_string(thresh, config=config, timeout=4)
        
        # FIX 4: DEBUG OCR OUTPUT (TEMPORARY)
        print("RAW OCR OUTPUT:", text)
        
        if text:
            # FIX 5: TEMP DISABLE CLEANING (IMPORTANT)
            # text = re.sub(r'\s+', ' ', text).strip().lower()[:1000]
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
    
    # PROBLEM 4 FIX: ADJUSTED CONFIDENCE LOGIC
    if length > 25 and valid_words >= 2:
        confidence = "high"
    elif length > 10:
        confidence = "medium"
    else:
        confidence = "low"

    print(f"Processing time: {time.time() - start_time:.2f} sec")

    return {
        "text": text,
        "source": "tesseract",
        "confidence": confidence
    }
