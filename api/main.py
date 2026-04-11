import os
import uuid
import json
import logging
import re
import time
from collections import defaultdict
from typing import List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import cv2
import numpy as np
import pytesseract
from rapidfuzz import fuzz

# ==============================================================================
# CONFIGURATION & LOGGING
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

TEMP_DIR = "/tmp"
MEDICINES_DB_PATH = "medicines.json"
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB limit
DEBUG = True  # Toggle for returning raw OCR data and extended logs

# Basic In-Memory Rate Limiting
RATE_LIMIT_DURATION = 60  # seconds
MAX_REQUESTS_PER_IP = 10
ip_request_counts = defaultdict(list)

# ==============================================================================
# FASTAPI APP SETUP
# ==============================================================================
app = FastAPI(
    title="MediLens V2 API",
    description="Production-ready prescription scanning and OCR system.",
    version="2.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# DATA ACCESS (LAZY LOADING)
# ==============================================================================
_medicines_db = None

def get_medicines_db() -> Dict[str, Any]:
    """Lazy-loads the medicines.json file to avoid blocking startup."""
    global _medicines_db
    if _medicines_db is None:
        try:
            if os.path.exists(MEDICINES_DB_PATH):
                with open(MEDICINES_DB_PATH, "r", encoding="utf-8") as f:
                    _medicines_db = json.load(f)
                logger.info(f"Loaded {len(_medicines_db)} medicines from {MEDICINES_DB_PATH}")
            else:
                logger.warning(f"File {MEDICINES_DB_PATH} not found. Using fallback mock data.")
                _medicines_db = {
                    "paracetamol": {
                        "uses": "Pain relief, fever reduction",
                        "dosage": "500mg-1000mg every 4-6 hours",
                        "warnings": "Do not exceed 4g per day. Liver damage risk."
                    },
                    "amoxicillin": {
                        "uses": "Bacterial infections",
                        "dosage": "250mg-500mg every 8 hours",
                        "warnings": "May cause stomach upset. Allergic reactions possible."
                    },
                    "ibuprofen": {
                        "uses": "Pain relief, inflammation reduction",
                        "dosage": "200mg-400mg every 4-6 hours",
                        "warnings": "Stomach bleeding risk. Take with food."
                    }
                }
        except Exception as e:
            logger.error(f"Failed to load medicines DB: {e}")
            _medicines_db = {}
    return _medicines_db

# ==============================================================================
# PIPELINE FUNCTIONS
# ==============================================================================
def preprocess_image(img: np.ndarray) -> np.ndarray:
    """Enhances image quality before OCR to handle blur and handwriting."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Upscale to improve detection of small text
    resized = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    # Apply adaptive thresholding to handle uneven lighting
    thresh = cv2.adaptiveThreshold(
        resized, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )
    return thresh

def extract_text(image_path: str) -> str:
    """Extracts text using multi-pass Tesseract OCR for maximum accuracy."""
    try:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("Failed to load image for OCR.")
        
        texts = []

        # Pass 1: Raw image
        texts.append(pytesseract.image_to_string(img))

        # Pass 2: Preprocessed image (handles blur/lighting)
        processed = preprocess_image(img)
        texts.append(pytesseract.image_to_string(processed))

        # Pass 3: Sparse mode (PSM 11 - Excellent for scattered prescription text)
        config = "--psm 11"
        texts.append(pytesseract.image_to_string(processed, config=config))

        # Combine all passes
        return "\n".join(texts).strip()

    except Exception as e:
        logger.error(f"OCR failure on {image_path}: {e}")
        return ""

def detect_medicines(text: str) -> List[Dict[str, Any]]:
    """Identifies medicines using intelligent word-level fuzzy matching."""
    if not text:
        return []

    db = get_medicines_db()
    known_medicines = list(db.keys())
    detected_raw = []
    
    text_lower = text.lower()
    # Tokenize words for granular matching
    words = re.findall(r'\b\w+\b', text_lower)

    try:
        for med in known_medicines:
            best_score = 0.0
            med_lower = med.lower()
            
            # 1. Word-level exact/close matching
            for word in words:
                score = fuzz.ratio(med_lower, word)
                if score > best_score:
                    best_score = score
            
            # 2. Block-level partial matching (fallback for multi-word or compound names)
            partial_score = fuzz.partial_ratio(med_lower, text_lower)
            
            # Take the best matching confidence
            final_score = max(best_score, partial_score)

            if final_score >= 80.0:  # Threshold for detection
                # Assign UX Confidence Label
                if final_score >= 90:
                    level = "High"
                elif final_score >= 85:
                    level = "Medium"
                else:
                    level = "Low"

                detected_raw.append({
                    "name": med.capitalize(),
                    "confidence": round(final_score, 2),
                    "confidence_level": level,
                    "info": db.get(med, {})
                })
        
        # Deduplication Step: Keep the instance with the highest confidence
        unique_medicines = {}
        for med in detected_raw:
            name = med["name"]
            if name not in unique_medicines or med["confidence"] > unique_medicines[name]["confidence"]:
                unique_medicines[name] = med

        final_detected = list(unique_medicines.values())
        
        # Sort results by highest confidence first
        final_detected.sort(key=lambda x: x["confidence"], reverse=True)
        return final_detected

    except Exception as e:
        logger.error(f"Medicine matching error: {e}")
        return []

def generate_explanation(medicines: List[Dict[str, Any]]) -> str:
    """Generates a short, clear, and human-readable explanation."""
    try:
        if not medicines:
            return "No medicines detected. Please ensure the scan is clear and well-lit."
        
        lines = ["💊 **Detected Medications:**\n"]
        for med in medicines:
            name = med.get("name", "Unknown")
            info = med.get("info", {})
            uses = info.get("uses", "N/A")
            warnings = info.get("warnings", "None")
            
            lines.append(f"- **{name}**")
            lines.append(f"  • Uses: {uses}")
            lines.append(f"  • Warning: {warnings}\n")
            
        lines.append("⚠️ *Always consult a healthcare professional before taking medication.*")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Explanation generation error: {e}")
        return "Explanation could not be generated due to an internal error."

# ==============================================================================
# API ENDPOINTS
# ==============================================================================
@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}

import os
from fastapi import UploadFile, File

@app.post("/scan")
async def scan(file: UploadFile = File(...)):
    try:
        # ✅ Step 1: temp file
        temp_file = os.path.join("/tmp", file.filename)

        # ✅ Step 2: save file
        with open(temp_file, "wb") as buffer:
            buffer.write(await file.read())

        # ✅ Step 3: OCR (USE YOUR FUNCTION)
        text = extract_text(temp_file)

        # ✅ Step 4: medicine detection (USE YOUR FUNCTION)
        medicines = detect_medicines(text)

        # ✅ Step 5: cleanup
        if os.path.exists(temp_file):
            os.remove(temp_file)

        # ✅ Step 6: optional explanation
        explanation = generate_explanation(medicines)

        return {
            "extracted_text": text,
            "medicines": medicines,
            "explanation": explanation
        }

    except Exception as e:
        return {"error": str(e)}

# ==============================================================================
# RUN CONFIGURATION
# ==============================================================================
if __name__ == "__main__":
    import uvicorn
    # Instant startup locally, suitable for deployment environments
    uvicorn.run("main:app", host="0.0.0.0", port=8000)