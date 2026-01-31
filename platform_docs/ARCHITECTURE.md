MediLens Medical AI Platform - System Architecture

1. Core Philosophy

This is a Safety-Critical System. Unlike generic chatbots, MediLens favors "Negative Containment" (refusing to answer) over "Hallucinated Helpfulness".

The system adheres to three mandatory rules:

Verification > Generation: No answer is generated without retrieving a verified document first.

Deterministic Identification: Medicine matching relies on exact token/substring matches first; fuzzy matching is a fallback only allowed above high thresholds.

Governance Layer: A dedicated service intercepts all inputs and outputs to enforce safety checks (interactions, disclaimers) regardless of what the AI "wants" to say.

2. Service-Oriented Architecture (SOA)

The system is decoupled into three independent layers.

A. The Vision Layer (OCR Service)

Responsible for turning pixels into signal data.

Engine: Tesseract v5 (LSTM) with a Multi-Pass Strategy.

Pass 1 (Raw): Standard extraction.

Pass 2 (Contrast): Upscaled (2x) + High Contrast for extracting text from shiny/colored boxes.

Pass 3 (Sparse): Uses psm=11 to find scattered numbers (dosage) and isolated words on prescriptions.

Signal Extraction: Post-processing regex to identify patterns like 1-0-1, 500mg, BD.

B. The Knowledge Layer (RAG Core)

Responsible for "Truth".

Source: data/medicines.json (Phase 1: WHO Essential Medicines List).

Vector Store: FAISS (Local dense retrieval).

Strict RAG: The LLM is PROHIBITED from answering if the Retrieval Score is below a threshold. It must use the context provided by FAISS.

C. The Governance Layer (Safety Service)

Responsible for "Safety".

Interaction Checker: Checks selected medicines against data/interactions.json before generation.

Output Guardrails: Post-processing to inject mandatory disclaimers.

Input Guardrails: Filters to ensure valid medicine names are passed to the context.

3. API Endpoints (FastAPI)

The backend (api_server.py) exposes these stateless endpoints:

Endpoint

Method

Purpose

/scan

POST

Upload image -> Return extracted text signals + Identified candidates with confidence scores.

/analyze

POST

Input Medicine List -> Return structured RAG Report + Interaction Warnings.

/chat

POST

Context-aware Q&A on specific medicines.

4. Scaling Strategy

Horizontal Scaling: The API is stateless. It can be deployed on multiple nodes/containers (Kubernetes) behind a load balancer.

Database: medicines.json is currently loaded into memory for speed (valid for <10,000 items). For >100k items, migrate to PostgreSQL with pgvector.

Models:

OCR: Tesseract is CPU-bound. For higher throughput, use GPU nodes with TrOCR.

LLM: Ollama runs locally. For production traffic, this can be swapped for vLLM or TGI on dedicated GPU instances without changing the API contract.
