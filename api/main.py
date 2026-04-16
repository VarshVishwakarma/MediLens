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
      4. Generate LLM explanation
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

        # Step 2: OCR
        ocr_result = extract_text(temp_path)
        text = ocr_result.get("text", "") if isinstance(ocr_result, dict) else ocr_result

        # Step 3: Medicine detection
        medicines = detect_medicines(text)

        # Step 4: Hybrid LLM explanation
        summary = ""
        
        if not medicines:
            # CASE 3 (NO MEDICINE)
            summary = "No medicines detected. Please upload a clearer image."
        else:
            med_db = get_medicines()
            instructions = get_instructions()

            top_med = medicines[0]
            med_name_key = top_med["name"].lower()
            
            if med_db.get(med_name_key):
                # CASE 1 (FOUND)
                summary = generate_explanation(
                    medicine_name=med_name_key,
                    medicine_info=med_db.get(med_name_key),
                    instructions=instructions,
                    confidence=top_med.get("level", "high")
                )
            else:
                # CASE 2 (NOT FOUND)
                summary = generate_fallback_explanation(medicine_name=med_name_key)

        # Step 5: Confidence
        confidence = "high" if medicines else "low"

        return {
            "success": True,
            "text": text,
            "medicines": medicines,
            "summary": summary,
            "confidence": confidence,
            "processing_time": round(time.time() - start_time, 2)
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
