# Build Timestamp: Attempt 23 - Docker Parse Fix

FROM python:3.10-slim

# System Dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    curl \
    procps \
    zstd \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# App Directory
WORKDIR /app

# Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create User
RUN useradd -m -u 1000 user

# Environment
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata/
ENV HOME=/home/user
ENV PATH=/home/user/.local/bin:$PATH
ENV OLLAMA_MODELS=/home/user/.ollama/models
ENV PORT=8000

# Setup Ollama Directory
RUN mkdir -p /home/user/.ollama/models && \
    chown -R user:user /home/user

# Copy Code
COPY --chown=user . .

# ✅ FIXED START SCRIPT (IMPORTANT)
RUN cat << 'EOF' > /app/start.sh
#!/bin/bash

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
EOF

RUN chmod +x /app/start.sh

# Switch User
USER user

# Expose Port
EXPOSE 8000

# Run
CMD ["/app/start.sh"]
