import os
import cv2
import pytesseract
import re
import time
import uuid
import pytesseract

pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"


# ==============================================================================
# CONFIGURATION
# ==============================================================================
MAX_IMAGE_DIM = 1000   # Max dimension for resizing (preserves aspect ratio)
JPEG_QUALITY  = 80     # High enough for OCR accuracy
TEMP_DIR      = "/tmp"


# ==============================================================================
# IMAGE COMPRESSION
# ==============================================================================
def compress_image(image_path: str) -> str:
    """
    Resizes image proportionally (max 1000px) and saves as JPEG.
    Never upscales. Preserves aspect ratio to avoid text distortion.
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            print(f"[compress_image] Could not read image: {image_path}")
            return image_path

        h, w = img.shape[:2]
        max_dim = max(h, w)

        # Only downscale — never upscale small images
        if max_dim > MAX_IMAGE_DIM:
            scale = MAX_IMAGE_DIM / max_dim
            new_w, new_h = int(w * scale), int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        temp_path = os.path.join(TEMP_DIR, f"compressed_{uuid.uuid4().hex}.jpg")
        success = cv2.imwrite(temp_path, img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])

        if success:
            return temp_path

        print("[compress_image] Failed to write compressed image, using original.")
        return image_path

    except Exception as e:
        print(f"[compress_image] Exception: {e}")
        return image_path


# ==============================================================================
# PREPROCESSING
# ==============================================================================
def preprocess_image(img: cv2.typing.MatLike) -> cv2.typing.MatLike:
    """
    Converts to grayscale, applies mild sharpening and adaptive thresholding.
    Adaptive threshold handles uneven lighting common in prescription photos.
    """
    # Step 1: Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Step 2: Mild sharpening (alpha > 1.3 causes halo artifacts)
    sharpened = cv2.convertScaleAbs(gray, alpha=1.2, beta=0)

    # Step 3: Adaptive threshold — handles shadows and uneven lighting
    thresh = cv2.adaptiveThreshold(
        sharpened, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=10
    )

    return thresh


# ==============================================================================
# TESSERACT OCR
# ==============================================================================
def tesseract_ocr(image_path: str) -> str:
    """
    Runs a single-pass Tesseract OCR on the preprocessed image.
    - OEM 1: LSTM only (faster than OEM 3, no accuracy loss)
    - PSM 6: Uniform block of text (correct for multi-line prescriptions)
    - No timeout: prevents silent empty-string failures on slow CPUs
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            print(f"[tesseract_ocr] Could not read image: {image_path}")
            return ""

        thresh = preprocess_image(img)

        # OEM 1 = LSTM only (faster), PSM 6 = multi-line block (correct for prescriptions)
        config = "--oem 1 --psm 6"
        text = pytesseract.image_to_string(thresh, config=config)

        if text:
            # Clean whitespace, normalize to lowercase, cap at 1000 chars
            text = re.sub(r'\s+', ' ', text).strip().lower()[:1000]
            return text

        return ""

    except Exception as e:
        print(f"[tesseract_ocr] Exception: {e}")
        return ""


# ==============================================================================
# CONFIDENCE SCORING
# ==============================================================================
def score_confidence(text: str) -> str:
    """
    Scores OCR confidence based on text length and meaningful word count.
    A meaningful word is longer than 3 characters.
    """
    length = len(text)
    valid_words = sum(1 for w in text.split() if len(w) > 3)

    if length > 50 and valid_words >= 2:
        return "high"
    elif length > 20:
        return "medium"
    else:
        return "low"


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
def extract_text(image_path: str) -> dict:
    """
    Full OCR pipeline:
      1. Compress & resize image
      2. Preprocess (grayscale → sharpen → adaptive threshold)
      3. Run Tesseract OCR
      4. Clean and score output
      5. Return structured result
    """
    start_time = time.time()
    print("[extract_text] Starting OCR pipeline...")

    # Step 1: Compress
    compressed_path = compress_image(image_path)

    # Step 2 + 3: Preprocess + OCR
    text = tesseract_ocr(compressed_path)

    # Step 4: Cleanup temp file
    if compressed_path != image_path and os.path.exists(compressed_path):
        os.remove(compressed_path)

    # Step 5: Logging
    length = len(text)
    confidence = score_confidence(text)
    elapsed = time.time() - start_time

    print(f"[extract_text] OCR length: {length}")
    print(f"[extract_text] Confidence: {confidence}")
    print(f"[extract_text] Processing time: {elapsed:.2f} sec")

    return {
        "text": text,
        "source": "tesseract",
        "confidence": confidence
    }
