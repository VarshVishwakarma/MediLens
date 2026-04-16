import os
import google.generativeai as genai

def format_section(title, content):
    if not content:
        return ""
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
        tips = medicine_info.get("tips")
        when_to_avoid = medicine_info.get("when_to_avoid")
        med_type = medicine_info.get("type")
        
        output = f"💊 {medicine_name.capitalize()}\n"
        output += format_section("🧾 Uses", uses)
        output += format_section("💊 Dosage", dosage)
        output += format_section("⚠️ Warnings", warnings)
        output += format_section("⚡ Side Effects", side_effects)
        
        if when_to_avoid:
            output += format_section("🚫 When to Avoid", when_to_avoid)
            
        if tips:
            output += format_section("💡 Tips", tips)
            
        if med_type:
            output += f"\n🏷️ Category\n{med_type}\n"
            
        output += "\n⚠️ Always consult a doctor"
        
        return output

    except Exception:
        return "Unable to generate explanation at the moment."

def generate_fallback_explanation(ocr_text: str) -> str:
    """
    Fallback function that uses the LLM to provide general, safe information 
    from the raw OCR text when a medicine is not found in the local database.
    """
    fallback_msg = (
        "⚠️ AI Estimated Medicine\n\n"
        "Unable to confidently identify medicine from the text.\n\n"
        "⚠️ Please consult a healthcare professional."
    )
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return fallback_msg
        
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = (
            "You are a safe and responsible medical assistant.\n\n"
            "Analyze the following OCR text from a prescription:\n\n"
            f"\"{ocr_text}\"\n\n"
            "Tasks:\n"
            "1. Identify the most likely medicine name\n"
            "2. Provide general explanation including:\n"
            "   - Uses\n"
            "   - Typical dosage range\n"
            "   - Warnings\n"
            "   - Side effects\n\n"
            "Rules:\n"
            "- If unsure, say \"Not confident\"\n"
            "- Do NOT hallucinate unknown medicines\n"
            "- Keep information general and safe\n"
            "- Do NOT give strict medical advice\n\n"
            "Format the output EXACTLY as follows:\n\n"
            "⚠️ AI Estimated Medicine\n\n"
            "💊 {Detected Name}\n\n"
            "🧾 Uses\n"
            "• ...\n\n"
            "💊 Dosage\n"
            "...\n\n"
            "⚠️ Warnings\n"
            "• ...\n\n"
            "⚡ Side Effects\n"
            "• ...\n\n"
            "⚠️ This is AI-estimated information and may not be fully accurate."
        )
        
        response = model.generate_content(prompt)
        if response.text:
            return response.text.strip()
            
        return fallback_msg
        
    except Exception:
        return "Unable to generate explanation at the moment."
