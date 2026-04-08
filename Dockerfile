# Build Timestamp: Attempt 22 - Render Stable Version

# 1. Base Image
FROM python:3.10-slim

# 2. System Dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    curl \
    procps \
    zstd \
    && rm -rf /var/lib/apt/lists/*

# 3. Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# 4. Setup App Directory
WORKDIR /app

# 5. Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Create User
RUN useradd -m -u 1000 user

# 7. Environment Variables
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata/
ENV HOME=/home/user
ENV PATH=/home/user/.local/bin:$PATH
ENV OLLAMA_MODELS=/home/user/.ollama/models

# 🔥 IMPORTANT FOR RENDER
ENV PORT=8000

# 8. Setup Permissions
RUN mkdir -p /home/user/.ollama/models && \
    chown -R user:user /home/user

# 9. Copy Code
COPY --chown=user . .

# 10. Create Startup Script
RUN echo '#!/bin/bash
echo "🚀 Starting MediLens..."

echo "1️⃣ Starting Ollama..."
ollama serve > /dev/null 2>&1 &

echo "2️⃣ Waiting for Ollama..."
until curl -s http://localhost:11434 > /dev/null; do
  sleep 1
done

echo "3️⃣ Pulling Model (Background)..."
(ollama pull llama3.2:1b &) 

echo "4️⃣ Starting Streamlit..."
streamlit run web_platform.py --server.port $PORT --server.address 0.0.0.0
' > /app/start.sh && chmod +x /app/start.sh

# 11. Switch User
USER user

# 12. Expose Port
EXPOSE 8000

# 13. Start App
CMD ["/app/start.sh"]
