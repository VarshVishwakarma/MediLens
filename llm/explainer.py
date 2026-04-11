import os
import json
import logging
import time
from typing import Dict, Any

# Safely attempt to import Gemini
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

logger = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURATION
# ==============================================================================
MODEL_NAME = os.getenv("LLM_MODEL", "gemini-2.5-flash")
MAX_RETRIES = 2
TIMEOUT_SECONDS = 5.0
MAX_INPUT_LENGTH = 1500  # Character limit to prevent token overflow

# Try to initialize the client lazily to avoid startup blocking
_gemini_configured = False

def configure_gemini():
    global _gemini_configured
    if not _gemini_configured and HAS_GEMINI:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            _gemini_configured = True
    return _gemini_configured

def validate_data(data: Dict[str, Any]) -> bool:
    """
    Validates that the input data contains all required fields with non-empty values.
    Prevents malformed schemas from crashing the explanation pipeline.
    """
    if not isinstance(data, dict):
        return False
    required = ["name", "uses", "dosage", "warnings"]
    return all(k in data and str(data.get(k)).strip() for k in required)

def _fallback_explanation(data: Dict[str, Any], mode: str) -> str:
    """
    Generates a safe, manual string formatting explanation if the LLM is unavailable,
    errors out, or lacks credentials.
    """
    name = data.get("name", "Unknown Medicine")
    if isinstance(name, str):
        name = name.capitalize()
        
    uses = data.get("uses", "Information not available.")
    dosage = data.get("dosage", "Information not available.")
    warnings = data.get("warnings", "Information not available.")
    
    if mode == "simple":
        return (
            f"💊 **{name}**\n"
            f"🔹 **Used for:** {uses}\n"
            f"📏 **Dosage:** {dosage}\n"
            f"⚠️ **Warning:** {warnings}\n\n"
            f"*(Disclaimer: This is an automated summary. Always consult a doctor.)*"
        )
    else:
        # Technical mode formatting
        return (
            f"MEDICATION PROFILE: {str(name).upper()}\n"
            f"- Indications: {uses}\n"
            f"- Administration/Dosage: {dosage}\n"
            f"- Contraindications & Warnings: {warnings}\n\n"
            f"DISCLAIMER: For informational purposes only. Not medical advice."
        )

def generate_explanation(data: Dict[str, Any], mode: str = "simple") -> str:
    """
    Generates a human-readable explanation of medicine data using an LLM.
    Strictly constrained to prevent hallucinations with validation, guards, and retries.
    
    Args:
        data (Dict[str, Any]): The medicine data dictionary.
        mode (str): The formatting mode ("simple" or "technical").
        
    Returns:
        str: The formatted explanation.
    """
    # 1. Validation Guard
    if not validate_data(data):
        logger.warning("Invalid data format or missing required fields. Using fallback.")
        return _fallback_explanation(data, mode)

    # 2. Token / Length Guard
    data_str = json.dumps(data)
    if len(data_str) > MAX_INPUT_LENGTH:
        logger.warning(f"Input data exceeds maximum allowed length of {MAX_INPUT_LENGTH}. Using fallback.")
        return _fallback_explanation(data, mode)

    # If LLM is not configured, fallback instantly
    if not configure_gemini():
        logger.info("Gemini API key not configured or package missing. Using fallback formatter.")
        return _fallback_explanation(data, mode)

    # Prepare strict contextual instructions
    tone_instruction = (
        "Use patient-friendly language with emojis for readability." 
        if mode == "simple" 
        else "Use clinical, structured bullet points."
    )

    # 3. Bulletproof Prompt
    system_prompt = f"""You are a strict medical data formatter.
    RULES:
    1. Use ONLY the JSON data provided by the user.
    2. DO NOT hallucinate, add external medical knowledge, diagnose, or give advice.
    3. If a field is missing, state 'Information not available'.
    4. Format the output clearly. {tone_instruction}
    5. Output MUST strictly reflect input fields.
    6. Do NOT rephrase beyond given meaning.
    7. Always end with this exact disclaimer: "Disclaimer: This is an automated summary. Always consult a doctor."
    """

    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=system_prompt
    )

    # 4. Retry & Timeout Handling
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = model.generate_content(
                data_str,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=150,
                    temperature=0.0
                ),
                request_options={"timeout": TIMEOUT_SECONDS}
            )
            
            explanation = response.text.strip()
            return explanation
            
        except Exception as e:
            logger.warning(f"LLM Explanation attempt {attempt + 1} failed: {e}")
            if attempt == MAX_RETRIES:
                logger.error("All LLM attempts failed. Falling back to manual formatting.")
                return _fallback_explanation(data, mode)
            time.sleep(1) # Short backoff before retry

    return _fallback_explanation(data, mode)

# ==============================================================================
# Execution Test Block
# ==============================================================================
if __name__ == "__main__":
    # Test valid data
    test_data = {
        "name": "Paracetamol",
        "uses": "Fever, mild pain",
        "dosage": "500mg every 6 hours",
        "warnings": "Do not exceed 4g per day to prevent liver damage"
    }
    
    # Test invalid data (Will trigger the validation fallback)
    invalid_data = {
        "name": "",
        "uses": "Headache"
    }

    print("--- VALID DATA TEST (SIMPLE MODE) ---")
    print(generate_explanation(test_data, mode="simple"))
    
    print("\n--- INVALID DATA TEST (SHOULD TRIGGER FALLBACK) ---")
    print(generate_explanation(invalid_data, mode="technical"))