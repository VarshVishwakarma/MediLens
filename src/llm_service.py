import os
from groq import Groq

class LLMService:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError("❌ GROQ_API_KEY not set")

        self.client = Groq(api_key=api_key)

    def explain_medicine(self, medicine_name):
        response = self.client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "You are a medical assistant."},
                {"role": "user", "content": f"What is {medicine_name} used for?"}
            ]
        )

        return response.choices[0].message.content