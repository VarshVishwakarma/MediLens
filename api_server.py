from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import shutil
import os
import sys
import uvicorn

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.platform_services import load_services
except ImportError:
    print("[ERROR] Cannot import load_services from src.platform_services")
    def load_services():
        return {"ocr": None, "id": None}

app = FastAPI(title="MediLens AI Platform API", version="2.0.0")

# --- LAZY LOADING SERVICES ---
services = None
llm = None

def get_services():
    """Lazily loads heavy ML services only when the first request is made."""
    global services, llm
    if services is None:
        print("[INFO] Lazy loading core services...")
        services = load_services()
        
        # Safely load the LLM service to avoid deployment timeouts
        try:
            from src.llm_service import LLMService
            llm = LLMService()
            print("[INFO] LLMService loaded successfully.")
        except ImportError:
            print("[WARN] LLMService module not found.")
            llm = None
            
        print("[INFO] Core services loaded successfully.")
    return services, llm

# --- ENDPOINTS ---

@app.get("/")
def read_root():
    """Root endpoint to verify service is alive immediately."""
    return {"message": "MediLens is LIVE"}

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

@app.post("/scan")
async def scan_prescription(file: UploadFile = File(...)):
    """
    Accepts an image file upload, performs OCR, identifies medicines,
    and fetches LLM explanations for each identified medicine.
    """
    temp_path = f"temp_{file.filename}"
    
    try:
        print(f"[INFO] POST /scan - Received file: {file.filename}")
        
        # 1. Load services (instantiates only on first call)
        srvs, llm_service = get_services()
        ocr_service = srvs.get("ocr")
        id_service = srvs.get("id")
        
        if not ocr_service or not id_service:
            print("[ERROR] Services are not properly initialized.")
            return JSONResponse(
                status_code=503, 
                content={"error": "Core extraction services are currently unavailable."}
            )

        # 2. Save uploaded file temporarily
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 3. Perform OCR Extraction
        print("[INFO] POST /scan - Starting OCR extraction...")
        with open(temp_path, "rb") as img_file:
            ocr_result = ocr_service.extract_signals(img_file)
            
        raw_text = ocr_result.get("raw_text", "")
        print(f"[INFO] POST /scan - OCR completed. Extracted {len(raw_text)} characters.")
        
        # 4. Perform Medicine Identification
        print("[INFO] POST /scan - Starting Medicine Identification...")
        candidates = id_service.identify(raw_text)
        print(f"[INFO] POST /scan - Identification completed. Found {len(candidates)} matches.")
        
        # 5. Fetch Explanations via LLMService
        explanations = []
        if llm_service:
            print("[INFO] POST /scan - Generating LLM explanations...")
            for med in candidates:
                explanation = llm_service.explain_medicine(med["name"])
                explanations.append({
                    "name": med["name"],
                    "info": explanation
                })
        
        # 6. Return structured payload
        return {
            "medicines": candidates,
            "explanations": explanations,
            "text": raw_text
        }
        
    except Exception as e:
        print(f"[ERROR] POST /scan - Exception occurred: {str(e)}")
        return JSONResponse(
            status_code=500, 
            content={"error": f"An internal server error occurred processing the image: {str(e)}"}
        )
        
    finally:
        # 7. Ensure temporary file cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
            print(f"[INFO] POST /scan - Cleaned up temporary file: {temp_path}")


if __name__ == "__main__":
    # Run the server locally. In production, use `uvicorn api_server:app --host 0.0.0.0 --port 8000`
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=False)