import os
import json
import google.generativeai as genai

# 1. Initialize Gemini model once globally (MANDATORY FIX)
API_KEY = os.getenv("GEMINI_API_KEY")
model = None
if API_KEY:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel("gemini-pro")

def load_instructions(filepath="instructions.json"):
    """Loads system rules and formatting instructions for the LLM."""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        # Returning structural layout matching the new nested logic
        return {
            "system_rules": {
                "tone": "professional medical assistant",
                "format": "bullet points"
            },
            "confidence_handling": "Warning: Low confidence reading. Please verify manually.",
            "safety_rules": "Always consult a doctor.",
            "llm_rules": "Format response in bullet points. Keep it concise."
        }

def generate_explanation(medicine_name, medicine_info, instructions, confidence="high"):
    """
    Generates a controlled, formatted explanation of a medicine.
    Strictly constrained to prevent hallucinations and ensure safety.
    """
    # Safety Handling: Null Data
    if medicine_info is None:
        return "Medicine not found in database. Please consult a healthcare professional."

    # 2. STRUCTURED INSTRUCTIONS USAGE
    rules = instructions.get("system_rules", {})
    
    # Check if dict structure is respected, handle gracefully if strings are passed
    if isinstance(rules, dict):
        tone = rules.get("tone", "professional medical assistant")
        format_type = rules.get("format", "bullet points")
    else:
        tone = "professional medical assistant"
        format_type = "bullet points"

    llm_rules = instructions.get("llm_rules", "Format response in bullet points.")
    safety_rules = instructions.get("safety_rules", "⚠️ Always consult a doctor")

    # Confidence Handling
    if confidence == "low":
        warning_msg = instructions.get("confidence_handling", "Low confidence reading.")
        return f"⚠️ {warning_msg}\nUnable to provide safe explanation for {medicine_name}."

    # Extract medical facts
    uses = medicine_info.get("uses", "Information not available")
    dosage = medicine_info.get("dosage", "Information not available")
    warnings = medicine_info.get("warnings", "Information not available")
    side_effects = medicine_info.get("side_effects", "Information not available")

    # 3. ADD HARD OUTPUT FALLBACK
    fallback_text = f"""💊 {medicine_name.capitalize()}
• Uses: {uses}
• Dosage: {dosage}
• Warnings: {warnings}
• Side Effects: {side_effects}

{safety_rules}"""

    # Prompt Engineering
    prompt = f"""You are a {tone}. Format the output using {format_type}.
ONLY use the provided data.
Do NOT add extra information.
{llm_rules}
Response must be less than 200 words.

Format the output EXACTLY like this:
💊 {medicine_name.capitalize()}
• Uses: [Insert uses here]
• Dosage: [Insert dosage here]
• Warnings: [Insert warnings here]
• Side Effects: [Insert side effects here]

{safety_rules}

Medicine: {medicine_name}
Uses: {uses}
Dosage: {dosage}
Warnings: {warnings}
Side Effects: {side_effects}
"""

    # Single API Call with Error Handling
    try:
        if not model:
            # Drop cleanly to the fallback if environment isn't set up
            return fallback_text

        response = model.generate_content(prompt)
        
        # 4. RESPONSE VALIDATION (Fallback execution)
        if not response.text:
            return fallback_text
            
        # 5. LENGTH CONTROL & DEBUG LOG
        output = response.text.strip()[:500]
        print("LLM response generated")
        
        return output
    except Exception as e:
        print(f"Explanation Generation Error: {e}")
        return fallback_text
