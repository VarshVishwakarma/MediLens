from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import shutil
import uvicorn
import os
import sys

# ✅ FIX IMPORT PATH FOR DOCKER / RENDER
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(BASE_DIR, "src")

if SRC_PATH not in sys.path:
    sys.path.append(SRC_PATH)

# ✅ SAFE IMPORT
try:
    from platform_services import load_services
except ImportError as e:
    print("❌ CRITICAL ERROR: Cannot import load_services:", str(e))

    def load_services():
        return {"ocr": None, "id": None}


app = FastAPI(title="MediLens AI Platform API", version="2.0.0")

# --- LAZY LOADING ---
services = None
llm = None


def get_services():
    global services, llm

    if services is None:
        print("🚀 Loading core services...")
        services = load_services()

        # ✅ SAFE LLM LOAD (OPTIONAL)
        try:
            from llm_service import LLMService
            llm = LLMService()
            print("✅ LLM loaded")
        except Exception as e:
            print("⚠️ LLM not available:", str(e))
            llm = None

    return services, llm


# --- ROOT ---
@app.get("/", response_class=HTMLResponse)
def home():
    with open("index.html", "r") as f:
        return f.read()


# --- HEALTH ---
@app.get("/health")
def health():
    return {"status": "ok"}


# --- MAIN SCAN ---
@app.post("/scan")
async def scan(file: UploadFile = File(...)):
    temp_path = os.path.join("/tmp", f"temp_{file.filename}")

    try:
        print("🔥 /scan endpoint hit")

        # 1. Load services
        srvs, llm_service = get_services()

        ocr = srvs.get("ocr")
        ident = srvs.get("id")

        if not ocr or not ident:
            return JSONResponse(
                status_code=503,
                content={"error": "Core services not available"}
            )

        # 2. Save file
        with open(temp_file, "wb") as buffer:
            buffer.write(await file.read())

        print("📁 File saved")

        # 3. OCR
        with open(temp_path, "rb") as img:
            result = ocr.extract_signals(img)

        raw_text = result.get("raw_text", "")
        print("🧠 OCR done")

        # 4. Identification
        meds = ident.identify(raw_text)
        print("💊 Identification done")

        # 5. LLM (OPTIONAL)
        explanations = []

        if llm_service:
            print("🤖 Generating explanations...")
            for med in meds:
                try:
                    explanation = llm_service.explain_medicine(med["name"])
                except Exception:
                    explanation = "No explanation available"

                explanations.append({
                    "name": med["name"],
                    "info": explanation
                })

        # 6. Response
        return {
            "medicines": meds,
            "explanations": explanations,
            "text": raw_text
        }

    except Exception as e:
        print("❌ ERROR:", str(e))

        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
            print("🧹 Temp file removed")


# --- LOCAL RUN ---
if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000)
