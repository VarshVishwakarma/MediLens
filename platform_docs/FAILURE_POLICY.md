MediLens AI Platform (Medical-Grade V1)

A safety-first, offline Medical AI Platform with explicit governance and failure discipline.

🏥 Medical-Grade Governance

This version includes a formal Failure Policy. The system is designed to fail safely rather than guess.

Explicit Refusal: The system refuses to answer diagnostic queries (e.g., "Do I have the flu?") or identify medicines with low OCR confidence (<65%).

Interaction Blocking: High-risk drug interactions BLOCK the generation of medical advice until explicitly acknowledged.

Measurement: Includes evaluate_system.py to audit accuracy and refusal rates.

🚀 Deployment Modes

1. Local Private (Default)

Runs entirely on localhost. Ideal for individual pharmacists or clinics with strict privacy needs.

streamlit run web_platform.py

2. Controlled Server (API Mode)

Decouples the Brain (API) from the Body (UI). Ideal for hospital networks where the AI runs on a secure server and tablets connect via the frontend.

uvicorn api_server:app --host 0.0.0.0 --port 8000

🛠️ Usage

Install: pip install -r requirements.txt

Ingest Data: python src/ingest_data.py (Validates schema & builds DB)

Run Evaluation: python evaluate_system.py (Tests safety logic)

Launch: streamlit run web_platform.py

🛡️ Safety Architecture

Vision Layer: Multi-pass OCR with signal extraction.

Governance Layer: src/safety.py intercepts all requests.

Knowledge Layer: RAG pipeline strictly grounded in WHO Essential Medicines data.

⚖️ Non-Negotiable Limits

MediLens is NOT a diagnostic tool.

It will never diagnose a condition based on symptoms.

It will never prescribe medication.

It will refuse to identify a medicine if the image is ambiguous.
