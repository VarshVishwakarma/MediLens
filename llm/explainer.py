import os
import google.generativeai as genai

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-pro")


def format_list(data):
    if not data:
        return "Not specified"
    if isinstance(data, list):
        return "\n".join([f"• {item}" for item in data])
    return str(data)


def generate_explanation(medicine_name, medicine_info, instructions=None, confidence="high"):
    try:
        if not medicine_info:
            return "Medicine not found in database. Please consult a healthcare professional."
            
        uses = format_list(medicine_info.get("uses"))
        dosage = medicine_info.get("dosage", "Not specified")
        warnings = format_list(medicine_info.get("warnings"))
        side_effects = format_list(medicine_info.get("side_effects"))
        category = medicine_info.get("type", "Not specified")
        tips = format_list(medicine_info.get("tips"))
        avoid = format_list(medicine_info.get("when_to_avoid"))

        prompt = f"""
You are a helpful and safe medical assistant.

Explain the following medicine in a clear, simple, and human-friendly way.

Medicine: {medicine_name}

Data:
Uses:
{uses}

Dosage:
{dosage}

Warnings:
{warnings}

Side Effects:
{side_effects}

Category:
{category}

Extra Tips:
{tips}

When to Avoid:
{avoid}

Instructions:
- Do NOT add new medical facts
- Do NOT hallucinate
- Just rephrase and explain clearly
- Keep it structured and easy to read
"""

        response = model.generate_content(prompt)
        text = response.text.strip()

        return f"💊 {medicine_name.capitalize()}\n\n{text}\n\n⚠️ Always consult a doctor"

    except Exception as e:
        print("LLM Error:", e)

        # 🔥 FALLBACK (NO LLM)
        return f"""💊 {medicine_name.capitalize()}

🧾 Uses
{uses}

💊 Dosage
{dosage}

⚠️ Warnings
{warnings}

⚡ Side Effects
{side_effects}

⚠️ Always consult a doctor
"""
