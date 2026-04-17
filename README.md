<div align="center">

💊 MediLens AI

Smart Prescription & Medication Scanner

MediLens AI is an intelligent, high-performance system designed to extract, identify, and explain medications from raw prescription images. By combining deterministic matching with safe LLM formatting, it bridges the gap between messy medical handwriting and clear patient understanding.

Features • How It Works • Architecture • Installation • Disclaimer

</div>

🚀 Features

Optical Character Recognition (OCR): Accurately extracts raw text from noisy, handwritten, or printed prescription images.

Intelligent Medicine Detection: Utilizes a custom-built, deterministic fuzzy-matching engine to identify medications despite OCR typos.

Safe AI Explanations: Uses the Google Gemini LLM strictly as a formatter to explain medicines using a verified, local database.

Lightning Fast & Lightweight: Built on FastAPI with an optimized single-pass detection loop.

Premium Glassmorphism UI: A sleek, animated, and responsive frontend built with Tailwind CSS.

🧠 How It Works

MediLens AI utilizes a hybrid AI pipeline. Instead of relying on a single AI model to do everything, it breaks the problem into a verifiable, multi-step pipeline:

[Prescription Image] ➔ 🔍 OCR Engine ➔ ⚙️ Matcher ➔ 🗄️ Medicine DB ➔ 🤖 LLM Formatter ➔ 💻 Clean UI


Extract: The image is sent to the OCR.space API to extract raw text.

Detect: The Custom Matcher cleans the text and uses token-based and fuzzy-matching (RapidFuzz) against our verified database aliases.

Retrieve: If a match exceeds our strict confidence threshold (≥ 60%), we pull the verified data (uses, dosage, warnings) from the local JSON database.

Explain: The Gemini API receives the verified data only and formats it into a human-readable, easily digestible summary.

⚙️ Tech Stack

Backend

Python 3.11+

FastAPI & Uvicorn (High-performance web framework)

RapidFuzz (String matching & tokenization)

OCR.space API (Image-to-text extraction)

Google Generative AI (Gemini Pro) (Formatting and summarization)

Frontend

HTML5 / JavaScript

Tailwind CSS (Styling & Animations)

Phosphor Icons (UI Icons)

📦 Project Structure

medilens-ai/
├── api/
│   └── main.py              # FastAPI application & route orchestration
├── core/
│   ├── loader.py            # Local database loader & cacher
│   ├── matcher.py           # Custom fuzzy matching engine
│   └── ocr.py               # OCR API integration & text cleaning
├── data/
│   ├── medicines.json       # Ground-truth medication database
│   └── instructions.json    # Specific formatting instructions
├── frontend/
│   └── index.html           # Premium UI/UX dashboard
├── llm/
│   └── explainer.py         # Gemini API integration (Safe formatting logic)
├── Dockerfile               # Production containerization
└── requirements.txt         # Python dependencies


🔥 Key Engineering Decisions

MediLens AI was built with safety and determinism as the highest priorities. Medical AI cannot afford to hallucinate.

Why not use an LLM for detection?
LLMs are prone to hallucination and confidently guessing incorrect medications when faced with messy OCR data. By using RapidFuzz for deterministic token/alias matching, we guarantee the system only identifies medications that actually exist in our vetted database.

LLM as a Formatter, not an Oracle.
The Gemini API is completely blind to the internet for this application. It is fed a strict prompt containing only the retrieved database JSON and instructed purely to format the output for readability.

Dynamic Confidence Thresholding.
Our matcher engine dynamically adjusts confidence scores based on direct matches, alias matches, and token subsets, ensuring that OCR noise (e.g., "P@racetam0l") doesn't break the pipeline.

🧪 Example Output

Input: A blurry image of a prescription containing the text "Take 1 paractemol daily".

System Output:

{
  "success": true,
  "medicines": [
    {
      "name": "paracetamol",
      "confidence": 88.5,
      "level": "medium"
    }
  ],
  "summary": "💊 Paracetamol\n\n🧾 Uses\n• Pain relief\n• Fever reduction\n\n💊 Dosage\n500mg - 1000mg every 4-6 hours\n\n⚠️ Always consult a doctor",
  "ocr_text": "take 1 paractemol daily"
}


⚡ Installation Guide

1. Clone the repository:

git clone [https://github.com/yourusername/medilens-ai.git](https://github.com/yourusername/medilens-ai.git)
cd medilens-ai


2. Create a virtual environment:

python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`


3. Install dependencies:

pip install -r requirements.txt


🔑 Environment Variables

Create a .env file in the root directory and add your API keys:

# Required for Text Extraction
OCR_SPACE_API_KEY=your_ocr_space_api_key_here

# Required for AI Explanation Formatting
GEMINI_API_KEY=your_google_gemini_api_key_here


▶️ Run Locally

Start the FastAPI server:

uvicorn api.main:app --reload --host 0.0.0.0 --port 8000


Visit http://localhost:8000 in your browser to access the MediLens UI.

🌐 Deployment

MediLens AI is completely containerized and ready for deployment on platforms like Render, Railway, or AWS.

Using Docker:

# Build the image
docker build -t medilens-ai .

# Run the container
docker run -p 8000:8000 --env-file .env medilens-ai


⚠️ Disclaimer

MediLens AI is for informational and educational purposes only. It is not a substitute for professional medical advice, diagnosis, or treatment. Always seek the advice of your physician or other qualified health provider with any questions you may have regarding a medical condition or prescription. The developers assume no liability for the accuracy of the extracted data.

<div align="center">
<p>🧑‍💻 Author

Varsh Vishwakarma
AI • ML • DL • Data Science • Cloud • Full-Stack ML Developer.</p>
</div>
