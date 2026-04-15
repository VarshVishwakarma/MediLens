import os
import time
import json
import logging
import re
import cv2
import pytesseract
from rapidfuzz import fuzz
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from llm.explainer import generate_explanation

# ==============================================================================
# CONFIGURATION & LOGGING
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

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

app.mount("/static", StaticFiles(directory="frontend"), name="static")

MEDICINES_DB_PATH = "medicines.json"
INSTRUCTIONS_PATH = "instructions.json"

# ==============================================================================
# DATA ACCESS (LAZY LOADING)
# ==============================================================================
_medicines_db = None
_instructions = None

def get_medicines_db():
    global _medicines_db
    if _medicines_db is None:
        try:
            if os.path.exists(MEDICINES_DB_PATH):
                with open(MEDICINES_DB_PATH, "r", encoding="utf-8") as f:
                    _medicines_db = json.load(f)
            else:
                _medicines_db = {}
        except Exception as e:
            logger.error(f"Failed to load medicines DB: {e}")
            _medicines_db = {}
    return _medicines_db

def get_instructions():
    global _instructions
    if _instructions is None:
        try:
            if os.path.exists(INSTRUCTIONS_PATH):
                with open(INSTRUCTIONS_PATH, "r", encoding="utf-8") as f:
                    _instructions = json.load(f)
            else:
                _instructions = {}
        except Exception as e:
            logger.error(f"Failed to load instructions: {e}")
            _instructions = {}
    return _instructions

# ==============================================================================
# FAST OCR PIPELINE
# ==============================================================================
def extract_text(image_path: str) -> str:
    start_time = time.time()
    try:
        img = cv2.imread(image_path)
        if img is None:
            return ""
        
        # 1. FORCE SMALL IMAGE SIZE
        img = cv2.resize(img, (500, 500))
        
        # 2. SIMPLE PREPROCESSING
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 3. SINGLE PASS TESSERACT
        text = pytesseract.image_to_string(gray, config="--oem 3 --psm 7")
        
        # 4. CLEAN OUTPUT
        text = re.sub(r'\s+', ' ', text).strip().lower()[:1000]
        
        logger.info(f"OCR time: {time.time() - start_time:.2f} sec")
        return text
    except Exception as e:
        logger.error(f"OCR Error: {e}")
        return ""

# ==============================================================================
# MEDICINE DETECTION
# ==============================================================================
def detect_medicines(text: str):
    start_time = time.time()
    if not text:
        return []

    db = get_medicines_db()
    results = []

    for med_name, med_info in db.items():
        score = fuzz.token_set_ratio(med_name.lower(), text)
        
        if score >= 70:
            if score >= 90:
                level = "high"
            elif score >= 80:
                level = "medium"
            else:
                level = "low"

            results.append({
                "name": med_name.capitalize(),
                "confidence": round(score, 2),
                "level": level,
                "info": med_info
            })

    # Sort and return top 3 matches
    results.sort(key=lambda x: x["confidence"], reverse=True)
    top_results = results[:3]
    
    logger.info(f"Detection time: {time.time() - start_time:.2f} sec")
    return top_results

# ==============================================================================
# API ENDPOINTS
# ==============================================================================
@app.get("/")
def serve_frontend():
    return FileResponse("frontend/index.html")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/scan")
async def scan(file: UploadFile = File(...)):
    start_time = time.time()
    temp_file = os.path.join("/tmp", file.filename)
    
    try:
        with open(temp_file, "wb") as buffer:
            buffer.write(await file.read())

        text = extract_text(temp_file)
        detected = detect_medicines(text)
        
        explanation = ""
        
        if detected:
            top_med = detected[0]
            conf_level = top_med["level"]
            
            # LLM USAGE STRATEGY
            if conf_level in ["high", "medium"]:
                instructions = get_instructions()
                explanation = generate_explanation(
                    medicine_name=top_med["name"],
                    medicine_info=top_med["info"],
                    instructions=instructions,
                    confidence=conf_level
                )
            else:
                explanation = f"⚠️ Low confidence reading. Detected {top_med['name']}, but please verify manually."
        else:
            explanation = "No medicines detected. Please ensure the scan is clear."

        # Filter out full 'info' payload for clean response
        final_medicines = [
            {
                "name": m["name"],
                "confidence": m["confidence"],
                "level": m["level"]
            } for m in detected
        ]

        total_time = time.time() - start_time
        logger.info(f"Total request time: {total_time:.2f} sec")

        return {
            "text": text,
            "medicines": final_medicines,
            "explanation": explanation,
            "processing_time": f"{total_time:.2f} sec"
        }
        
    except Exception as e:
        return {"error": str(e)}
        
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
