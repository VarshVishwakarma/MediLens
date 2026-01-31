import os
import re
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
from thefuzz import fuzz
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
import json
import string
import sys

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_PATH = os.path.join(BASE_DIR, "data", "medical_knowledge_base")
JSON_SOURCE = os.path.join(BASE_DIR, "data", "medicines.json")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
LLM_MODEL_NAME = "llama3"

# Windows Path Fix
if os.name == 'nt':
    default_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.join(os.getenv('LOCALAPPDATA', ''), r"Tesseract-OCR\tesseract.exe")
    ]
    for p in default_paths:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            break

class OCRService:
    """
    Production-grade OCR service with Hybrid Extraction.
    """
    @staticmethod
    def _preprocess_for_handwriting(img):
        """Advanced preprocessing to isolate ink from paper noise."""
        gray = ImageOps.grayscale(img)
        # Increase contrast to separate ink
        enhancer = ImageEnhance.Contrast(gray)
        contrast = enhancer.enhance(2.5)
        # Sharpness helps with cursive edges
        sharpener = ImageEnhance.Sharpness(contrast)
        sharp = sharpener.enhance(2.0)
        return sharp

    def extract_signals(self, image_file):
        """
        Extracts both raw text and 'medical signals' (dosages, frequencies).
        """
        try:
            if hasattr(image_file, 'seek'):
                image_file.seek(0)
            img = Image.open(image_file)
            
            # Strategy 1: Standard Printed Extraction
            text_printed = pytesseract.image_to_string(img, config=r'--oem 3 --psm 3')
            
            # Strategy 2: Handwriting/Signal Mode
            # We assume handwriting is often larger/sparser or needs specific filters
            hw_img = self._preprocess_for_handwriting(img)
            # PSM 6 assumes a block of text, good for lists of meds
            text_hw = pytesseract.image_to_string(hw_img, config=r'--oem 3 --psm 6')
            
            combined_text = text_printed + "\n" + text_hw
            
            # Signal Extraction (Regex for common Rx patterns)
            # This helps even if the medicine name is garbled
            signals = {
                "dosages": re.findall(r'\d+\s?mg|\d+\s?ml|\d+\s?g', combined_text, re.IGNORECASE),
                "frequencies": re.findall(r'\b(?:OD|BD|TDS|BID|QID|SOS|1-0-1|0-1-0)\b', combined_text, re.IGNORECASE),
                "raw_text": combined_text.strip()
            }
            return signals
        except Exception as e:
            return {"error": str(e), "raw_text": ""}

class IdentificationService:
    """
    Multi-tier Medicine Matching Engine.
    """
    def __init__(self):
        self.known_db = self._load_medicines()

    def _load_medicines(self):
        # Load aliases and names from JSON source for freshness
        mapping = {} # Name/Alias -> Canonical Name
        if os.path.exists(JSON_SOURCE):
            try:
                with open(JSON_SOURCE, 'r') as f:
                    data = json.load(f)
                    for item in data.get("medicines", []):
                        canonical = item['name']
                        mapping[canonical.lower()] = canonical
                        for alias in item.get('aliases', []):
                            mapping[alias.lower()] = canonical
            except Exception as e:
                print(f"Error loading medicines.json: {e}")
        return mapping

    def identify(self, text, threshold=65):
        if not text: return []
        
        # Normalize
        translator = str.maketrans(string.punctuation, ' ' * len(string.punctuation))
        clean_text = text.lower().translate(translator)
        tokens = set(clean_text.split())
        
        candidates = {} # Canonical -> Score

        for key, canonical in self.known_db.items():
            score = 0
            
            # 1. Exact Token (High Confidence)
            if key in tokens:
                score = 100
            # 2. Substring (Medium Confidence)
            elif key in clean_text:
                score = 90
            # 3. Fuzzy (Fallback)
            else:
                score = fuzz.partial_ratio(key, clean_text)
            
            # Update best score for this canonical medicine
            if score >= threshold:
                if canonical not in candidates or score > candidates[canonical]:
                    candidates[canonical] = score
        
        # Convert to sorted list
        results = [{"name": k, "score": v} for k, v in candidates.items()]
        results.sort(key=lambda x: x['score'], reverse=True)
        return results

class KnowledgeService:
    """
    RAG Pipeline and Safety Governance.
    """
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        self.llm = Ollama(model=LLM_MODEL_NAME)
        # Load Vector Store
        if os.path.exists(KB_PATH):
            self.vector_store = FAISS.load_local(KB_PATH, self.embeddings, allow_dangerous_deserialization=True)
        else:
            self.vector_store = None
            print(f"⚠️ Knowledge Base not found at {KB_PATH}. Please run ingest_data.py")

    def get_analysis(self, medicines: list, user_query: str = ""):
        """
        Retrieves context and generates a safe, structured medical report.
        """
        if not self.vector_store:
            return "⚠️ System Error: Knowledge Base is offline. Please run ingest_data.py."

        # 1. Retrieval
        context_docs = []
        for med in medicines:
            # Retrieve specifically for this medicine
            docs = self.vector_store.similarity_search(med, k=2)
            context_docs.extend([d.page_content for d in docs])
        
        full_context = "\n\n".join(context_docs)

        # 2. Strict Governance Prompt
        template = """
        SYSTEM ROLE: You are a Medical AI Assistant. 
        MANDATE: You must ONLY use the provided Context. If information is missing, say "Data unavailable".
        SAFETY: Do not generate prescriptions. Do not diagnose.
        
        CONTEXT FROM VERIFIED DATABASE:
        {context}
        
        USER QUERY: {query}
        TARGET MEDICINES: {medicines}
        
        INSTRUCTIONS:
        Provide a structured report for the target medicines.
        Format:
        ### 💊 [Medicine Name]
        - **Uses**: ...
        - **Dosage**: ...
        - **How to Take**: ...
        - **⚠️ Warnings**: ...
        - **Source**: ...
        
        [If Chat Query]: Answer the specific question based on context.
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["context", "query", "medicines"]
        )
        
        # 3. Generation
        chain = prompt | self.llm | StrOutputParser()
        response = chain.invoke({
            "context": full_context, 
            "query": user_query if user_query else "Provide general summary",
            "medicines": ", ".join(medicines)
        })
        
        # 4. Disclaimer Injection (Hardcoded Safety Layer)
        disclaimer = (
            "\n\n---\n"
            "**🚨 MEDICAL DISCLAIMER:** "
            "This information is retrieved from the WHO Model List (23rd Ed) and official labels. "
            "It is for educational purposes only. **This system is NOT a doctor.** "
            "Always consult a licensed physician before taking any medication."
        )
        
        return response + disclaimer