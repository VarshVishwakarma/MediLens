import os
import time
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.ocr import extract_text
from core.matcher import detect_medicines
from core.loader import get_medicines, get_instructions
from llm.explainer import generate_explanation, generate_fallback_explanation

# ==============================================================================
# PATH CONFIGURATION
# ==============================================================================
# main.py lives at /app/api/main.py → parent.parent = /app
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
INDEX_FILE = FRONTEND_DIR / "index.html"

# ==============================================================================
# APP INITIALIZATION
# ==============================================================================
app = FastAPI(title="MediLens AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files only if frontend directory exists
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
else:
    print(f"[WARNING] Frontend directory not found at: {FRONTEND_DIR}")

# ==============================================================================
# ROUTES
# ==============================================================================
@app.get("/")
def serve_home():
    """Serves the frontend index.html using an absolute path."""
    if not INDEX_FILE.exists():
        return JSONResponse(
            status_code=404,
            content={"error": f"Frontend file missing at: {INDEX_FILE}"}
        )
    return FileResponse(INDEX_FILE)


@app.get("/health")
def health_check():
    """Simple health check for uptime monitoring."""
    return {"status": "ok"}


@app.get("/debug")
def debug():
    """Temporary debug route — remove before going fully live."""
    return {
        "status": "ok",
        "base_dir": str(BASE_DIR),
        "frontend_dir": str(FRONTEND_DIR),
        "frontend_dir_exists": FRONTEND_DIR.exists(),
        "index_file": str(INDEX_FILE),
        "frontend_exists": INDEX_FILE.exists(),
    }


@app.post("/scan")
async def scan_prescription(image: UploadFile = File(...)):
    """
    Full prescription scan pipeline:
      1. Save uploaded image to temp file
      2. Run OCR
      3. Detect medicines via fuzzy matcher
      4. Hybrid Logic (DB vs LLM Fallback)
      5. Return structured result
    """
    start_time = time.time()
    temp_path = None

    try:
        # Step 1: Save uploaded file to a temp location
        file_extension = os.path.splitext(image.filename)[1] or ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_file.write(await image.read())
            temp_path = temp_file.name

        # Extract text
        ocr_result = extract_text(temp_path)
        text = ocr_result.get("text", "") if isinstance(ocr_result, dict) else ocr_result

        # Step 2: Detect medicines
        medicines = detect_medicines(text)

        # Step 3: Load database
        med_db = get_medicines()
        instructions = get_instructions()

        # Step 4: Core Logic
        summary = ""
        fallback_used = False

        if medicines:
            med = medicines[0]

            # CASE 1 — MEDICINE FOUND (HIGH CONFIDENCE)
            if med.get("confidence", 0) >= 75:
                med_name = med["name"].lower()
                med_info = med_db.get(med_name)

                if med_info:
                    summary = generate_explanation(
                        medicine_name=med_name,
                        medicine_info=med_info,
                        instructions=instructions,
                        confidence=med.get("level", "high")
                    )
                # CASE 2 — NOT IN DB
                else:
                    fallback_used = True
                    summary = generate_fallback_explanation(text)
            # CASE 2 — LOW CONFIDENCE
            else:
                fallback_used = True
                summary = generate_fallback_explanation(text)
        # CASE 3 — NO MEDICINES DETECTED
        else:
            fallback_used = True
            summary = generate_fallback_explanation(text)

        return {
            "success": True,
            "medicines": medicines,
            "summary": summary,
            "fallback": fallback_used,
            "ocr_text": text,
            "confidence": "high" if not fallback_used else "low",
            "processing_time": round(time.time() - start_time, 2)
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "medicines": [],
            "summary": "Something went wrong. Please try again."
        }

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
