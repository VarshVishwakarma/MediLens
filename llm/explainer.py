import os
import google.generativeai as genai

def generate_explanation(medicine_name: str, medicine_info: dict, instructions: dict, confidence: str = "high") -> str:
    try:
        if not medicine_info:
            return "Medicine not found in database. Please consult a healthcare professional."
            
        if confidence == "low":
            return "⚠️ Low confidence reading. Please verify the medicine manually."
            
        uses = medicine_info.get("uses", "Information not available")
        dosage = medicine_info.get("dosage", "Information not available")
        warnings = medicine_info.get("warnings", "Information not available")
        side_effects = medicine_info.get("side_effects", "Information not available")
        
        fallback_text = (
            f"💊 {medicine_name.capitalize()}\n\n"
            f"• Uses: {uses}\n"
            f"• Dosage: {dosage}\n"
            f"• Warnings: {warnings}\n"
            f"• Side Effects: {side_effects}\n\n"
            f"⚠️ Always consult a doctor"
        )
        
        api_key = os.getenv("GEMINI_API_KEY")
        
        if api_key and confidence in ["high", "medium"]:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-pro')
                
                instruction_text = instructions.get(medicine_name, "No specific instructions available.")
                
                prompt = (
                    "System: You are a professional medical assistant. "
                    "Strict instruction: Use ONLY the provided data. Do NOT generate unknown information. "
                    "Do NOT hallucinate medical facts. Do NOT guess missing fields. "
                    "Format the information clearly and keep the response under 200 words.\n\n"
                    f"Data for {medicine_name}:\n"
                    f"Uses: {uses}\n"
                    f"Dosage: {dosage}\n"
                    f"Warnings: {warnings}\n"
                    f"Side Effects: {side_effects}\n"
                    f"Instructions: {instruction_text}"
                )
                
                response = model.generate_content(prompt)
                if response.text:
                    return response.text.strip()
            except Exception:
                return fallback_text
                
        return fallback_text

    except Exception:
        return "Unable to generate explanation at the moment."
