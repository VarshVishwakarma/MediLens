# 1. Base Image: Lightweight Linux with Python
FROM python:3.10-slim

# 2. System Dependencies (Install Tesseract & GL Libraries for OCR & Curl for Ollama)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1-mesa-glx \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 3. Setup Working Directory
WORKDIR /app

# 4. Copy Dependencies
COPY requirements.txt .

# 5. Install Python Libraries
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy Application Code
COPY . .

# 7. Environment Variables
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata/
ENV STREAMLIT_SERVER_PORT=7860
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
# Hugging Face Spaces specific home directory
ENV HOME=/home/user

# 8. Create a User (Security Best Practice for HF Spaces)
RUN useradd -m -u 1000 user
USER user
ENV PATH=/home/user/.local/bin:$PATH

# 9. Install Ollama (Local AI Engine) inside the container
RUN curl -fsSL https://ollama.com/install.sh | sh

# 10. Create a Startup Script
# This script starts Ollama in the background, pulls the model, and then runs Streamlit
RUN echo '#!/bin/bash \n\
    ollama serve & \n\
    echo "Waiting for Ollama to start..." \n\
    sleep 5 \n\
    echo "Pulling Llama 3.2 (1B) Model..." \n\
    ollama pull llama3.2:1b \n\
    echo "Starting MediLens Platform..." \n\
    streamlit run web_platform.py --server.port 7860 --server.address 0.0.0.0 \n\
    ' > start.sh && chmod +x start.sh

# 11. Start the Container using the script
CMD ["./start.sh"]