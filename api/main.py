import os
import time
import tempfile
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.ocr import extract_text
from core.matcher import detect_medicines
from llm.explainer import generate_explanation
from fastapi.responses import FileResponse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

@app.get("/")
def serve_home():
    return FileResponse(BASE_DIR / "frontend" / "index.html")

app = FastAPI(title="MediLens AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "frontend"), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")

@app.post("/scan")
async def scan_prescription(image: UploadFile = File(...)):
    start_time = time.time()
    temp_path = None
    
    try:
        # 1. Save uploaded file temporarily
        file_extension = os.path.splitext(image.filename)[1] or ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_file.write(await image.read())
            temp_path = temp_file.name

        # 2. Call OCR
        text = extract_text(temp_path)

        # 3. Call matcher
        medicines = detect_medicines(text)

        # 4. Call LLM
        summary = generate_explanation(medicines) if medicines else "No medicines detected to explain."
        confidence = "high" if medicines else "low"

        # 5. Return response
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
