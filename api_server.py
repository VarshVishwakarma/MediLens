from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import shutil
import os
import uvicorn
import sys

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.platform_services import OCRService, IdentificationService, KnowledgeService # type: ignore
    from src.safety import SafetyGuard # type: ignore
except ImportError:
    print("⚠️  Warning: src modules not found. Ensure structure is correct.")
    class OCRService: pass
    class IdentificationService: pass
    class KnowledgeService: pass
    class SafetyGuard: 
        def __init__(self, p): pass

app = FastAPI(title="MediLens AI Platform API", version="2.0.0")

# --- INITIALIZATION ---
ocr_service = None
id_service = None
knowledge_service = None
safety_guard = None

@app.on_event("startup")
async def startup_event():
    global ocr_service, id_service, knowledge_service, safety_guard
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_PATH = os.path.join(BASE_DIR, "data")
    
    print("🚀 Initializing MediLens Services...")
    ocr_service = OCRService()
    id_service = IdentificationService()
    knowledge_service = KnowledgeService()
    safety_guard = SafetyGuard(DATA_PATH)
    print("✅ Services Ready.")

# --- MODELS ---
class MedicineCandidate(BaseModel):
    name: str
    score: int

class OCRResponse(BaseModel):
    raw_text: str
    signals: Dict[str, Any]
    candidates: List[MedicineCandidate]

class AnalyzeRequest(BaseModel):
    medicines: List[str]
    acknowledge_risk: bool = False # Explicit user override for high risk

class ChatRequest(BaseModel):
    medicines: List[str]
    query: str

class ReportResponse(BaseModel):
    report: str
    disclaimer: str
    safety_status: str
    warnings: List[Dict[str, Any]]

# --- ENDPOINTS ---

@app.get("/")
def health_check():
    """Heartbeat endpoint to check if API is online."""
    return {"status": "online", "service": "MediLens Core", "version": "2.0.0"}

@app.post("/scan", response_model=OCRResponse)
async def scan_prescription(file: UploadFile = File(...)):
    if not ocr_service: raise HTTPException(503, "Services offline")
    
    temp_path = f"temp_{file.filename}"
    try:
        with open(temp_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
        
        # 1. Extraction
        with open(temp_path, "rb") as img_file: 
            signals = ocr_service.extract_signals(img_file)
        
        # 2. Identification (Enforces Failure Policy Threshold inside service)
        candidates = id_service.identify(signals.get("raw_text", ""))
        
        return {
            "raw_text": signals.get("raw_text", "")[:1000],
            "signals": {k: v for k, v in signals.items() if k != "raw_text"},
            "candidates": candidates
        }
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)

@app.post("/analyze", response_model=ReportResponse)
async def analyze_medicines(request: AnalyzeRequest):
    if not knowledge_service: raise HTTPException(503, "Services offline")
    if not request.medicines: raise HTTPException(400, "No medicines provided.")

    # 1. SAFETY CHECK (Interaction)
    # This runs BEFORE the LLM to prevent unsafe generation
    safety_report = safety_guard.check_interactions(request.medicines)
    
    # 2. HIGH RISK BLOCKING
    # If the safety guard flags a block action (High Risk), we refuse to generate.
    if safety_report["block_action"] and not request.acknowledge_risk:
        return {
            "report": "⚠️ ANALYSIS BLOCKED: High Risk Interaction Detected. Please review warnings.",
            "disclaimer": safety_guard.disclaimer_text,
            "safety_status": "blocked",
            "warnings": safety_report["warnings"]
        }

    # 3. RAG GENERATION (Only if safe or acknowledged)
    full_response = knowledge_service.get_analysis(request.medicines, user_query="")
    
    # 4. DISCLAIMER ENFORCEMENT
    final_output = safety_guard.inject_disclaimer(full_response)

    return {
        "report": final_output,
        "disclaimer": safety_guard.disclaimer_text,
        "safety_status": safety_report["status"],
        "warnings": safety_report["warnings"]
    }

@app.post("/chat", response_model=ReportResponse)
async def chat_medical_context(request: ChatRequest):
    """
    Context-aware Chatbot.
    """
    if not knowledge_service: raise HTTPException(503, "Services offline")
    if not request.medicines: raise HTTPException(400, "Context required.")

    # 1. POLICY CHECK (Diagnosis Guardrail)
    # Refuse if user asks for diagnosis
    policy_violation = safety_guard.check_policy_violation(request.query)
    if policy_violation:
        return {
            "report": policy_violation,
            "disclaimer": safety_guard.disclaimer_text,
            "safety_status": "blocked",
            "warnings": []
        }

    # 2. RAG GENERATION
    try:
        full_response = knowledge_service.get_analysis(request.medicines, user_query=request.query)
        final_output = safety_guard.inject_disclaimer(full_response)

        return {
            "report": final_output,
            "disclaimer": safety_guard.disclaimer_text,
            "safety_status": "safe", # Chat assumes interactions checked in Analyze step
            "warnings": []
        }
    except Exception as e:
        raise HTTPException(500, f"Chat Error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)