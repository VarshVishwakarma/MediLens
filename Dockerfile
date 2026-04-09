# Build Timestamp: Attempt 26 - Optimized & Fixed Shell Logic
FROM python:3.10-slim

# 1. System Dependencies
# Optimized to include common dependencies and cleanup in one layer
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    curl \
    procps \
    zstd \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Ollama
# Installed early as it changes less frequently than app code
RUN curl -fsSL https://ollama.com/install.sh | sh

# 3. Setup User and App Directory
RUN useradd -m -u 1000 user
WORKDIR /app

# 4. Environment Variables
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata/
ENV HOME=/home/user
ENV PATH=/home/user/.local/bin:$PATH
ENV OLLAMA_MODELS=/home/user/.ollama/models
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# 5. Setup Permissions for Ollama
RUN mkdir -p /home/user/.ollama/models && \
    chown -R user:user /home/user && \
    chown -R user:user /app

# 6. Python Dependencies
# Copy only requirements first to leverage Docker cache
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copy Application Code
COPY --chown=user:user . .

# 8. Create Entrypoint Script
# Using a more robust method to create the start script
RUN printf "#!/bin/bash\n\
echo '🚀 Starting MediLens Services...'\n\
\n\
echo '1️⃣ Starting Ollama in background...'\n\
ollama serve > /home/user/ollama.log 2>&1 &\n\
\n\
# Wait a few seconds for Ollama to initialize\n\
sleep 5\n\
\n\
echo '2️⃣ Starting Streamlit (Main Process)...'\n\
exec streamlit run web_platform.py --server.port \$PORT --server.address 0.0.0.0\n" > /app/start.sh

RUN chmod +x /app/start.sh && chown user:user /app/start.sh

# 9. Switch User
USER user

# 10. Expose Port
EXPOSE 8000

# 11. Start App
CMD ["/app/start.sh"]
