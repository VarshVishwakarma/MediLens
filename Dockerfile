# Build Timestamp: Attempt 24 - Render Timeout Fix

FROM python:3.10-slim

# 1. System Dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    curl \
    procps \
    zstd \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# 3. App Directory
WORKDIR /app

# 4. Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Create User
RUN useradd -m -u 1000 user

# 6. Environment
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata/
ENV HOME=/home/user
ENV PATH=/home/user/.local/bin:$PATH
ENV OLLAMA_MODELS=/home/user/.ollama/models
ENV PORT=8000

# 7. Setup Permissions
RUN mkdir -p /home/user/.ollama/models && \
    chown -R user:user /home/user

# 8. Copy Code
COPY --chown=user . .

# 9. External Startup Script (FAST START)
RUN echo '#!/bin/bash
echo "🚀 Starting MediLens..."

echo "1️⃣ Starting Streamlit FIRST..."
streamlit run web_platform.py --server.port $PORT --server.address 0.0.0.0 &

echo "2️⃣ Starting Ollama in background..."
ollama serve > /dev/null 2>&1 &

echo "3️⃣ System initialized"
wait
' > /app/start.sh

RUN chmod +x /app/start.sh

# 10. Switch User
USER user

# 11. Expose Port
EXPOSE 8000

# 12. Start App
CMD ["/app/start.sh"]
