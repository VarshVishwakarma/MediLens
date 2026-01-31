# Build Timestamp: Attempt 20 - Fix Write Permissions
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

# 3. Install Ollama (Run as ROOT)
RUN curl -fsSL https://ollama.com/install.sh | sh

# 4. Setup Application Directory
WORKDIR /app

# 5. Copy & Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Create Non-Root User & Setup Permissions
RUN useradd -m -u 1000 user

# 7. Environment Variables
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata/
ENV STREAMLIT_SERVER_PORT=7860
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV HOME=/home/user
ENV PATH=/home/user/.local/bin:$PATH
ENV OLLAMA_MODELS=/home/user/.ollama/models

# 8. Create Model Directory & Fix Permissions
RUN mkdir -p /home/user/.ollama/models && \
    chown -R user:user /home/user && \
    chmod -R 777 /home/user

# 9. Copy Application Code (As User)
COPY --chown=user . .

# 10. Create Startup Script (AS ROOT)
# We create this before switching users to avoid "Permission Denied" errors.
# We then verify ownership so the user can execute it.
RUN echo '#!/bin/bash \n\
    echo "1. Starting Ollama Server..." \n\
    ollama serve > /dev/null 2>&1 & \n\
    \n\
    echo "2. Launching Background Model Download..." \n\
    ( \n\
    # Wait for server loop \n\
    while ! curl -s http://localhost:11434 > /dev/null; do sleep 1; done \n\
    echo "Ollama API Ready. Downloading Llama 3.2 (1B)..." \n\
    ollama pull llama3.2:1b \n\
    echo "Model Download Complete! AI is ready." \n\
    ) & \n\
    \n\
    echo "3. Starting Streamlit (Immediate)..." \n\
    streamlit run web_platform.py --server.port 7860 --server.address 0.0.0.0 \n\
    ' > /app/start.sh && \
    chmod +x /app/start.sh && \
    chown user:user /app/start.sh

# 11. Switch to User
USER user

# 12. Run
CMD ["/app/start.sh"]