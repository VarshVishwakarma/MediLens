import os
import google.generativeai as genai

def format_section(title, content):
    if isinstance(content, list):
        content = "\n".join([f"• {item}" for item in content])
    return f"\n{title}\n{content}\n"

def generate_explanation(medicine_name: str, medicine_info: dict, instructions: dict, confidence: str = "high") -> str:
    """
    Generates a structured explanation strictly using the local database.
    Does NOT use the LLM to prevent hallucinations on known data.
    """
    try:
        if not medicine_info:
            return "Medicine not found in database. Please consult a healthcare professional."
            
        if confidence == "low":
            return "⚠️ Low confidence reading. Please verify the medicine manually."
            
        uses = medicine_info.get("uses", "Information not available")
        dosage = medicine_info.get("dosage", "Information not available")
        warnings = medicine_info.get("warnings", "Information not available")
        side_effects = medicine_info.get("side_effects", "Information not available")
        
        # Build rich output directly from DB
        output = f"💊 {medicine_name.capitalize()}\n"
        output += format_section("🧾 Uses", uses)
        output += format_section("💊 Dosage", dosage)
        output += format_section("⚠️ Warnings", warnings)
        output += format_section("⚡ Side Effects", side_effects)
        
        med_type = medicine_info.get("type")
        if med_type:
            output += f"\n🏷️ Category\n{med_type}\n"
            
        output += "\n⚠️ Always consult a doctor"
        
        return output

    except Exception:
        return "Unable to generate explanation at the moment."

def generate_fallback_explanation(medicine_name: str) -> str:
    """
    Fallback function that uses the LLM to provide general, safe information 
    when a medicine is not found in the local database.
    """
    fallback_msg = (
        f"💊 {medicine_name.capitalize()}\n\n"
        "Medicine not found in local database.\n\n"
        "⚠️ Please consult a healthcare professional for Uses, Dosage, Warnings, and Side Effects."
    )
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return fallback_msg
        
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = (
            "System: You are a professional medical assistant. "
            f"The medicine '{medicine_name}' was not found in our primary database.\n\n"
            "Please provide general information for this medicine including:\n"
            "- Uses\n"
            "- Dosage (if known)\n"
            "- Warnings\n"
            "- Side effects\n\n"
            "STRICT RULES:\n"
            "1. If you are unsure about ANY field, explicitly state 'may vary' or 'consult a doctor'.\n"
            "2. Keep the information safe, general, and strictly advisory.\n"
            "3. Make NO fake claims or definitive medical prescriptions.\n"
            "4. Format the output clearly with bullet points.\n"
            "5. Keep the response under 200 words."
        )
        
        response = model.generate_content(prompt)
        if response.text:
            return response.text.strip() + "\n\n⚠️ Always consult a doctor"
            
        return fallback_msg
        
    except Exception:
        return fallback_msg
