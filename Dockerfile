# 1. Use a lightweight Python base image
FROM python:3.10-slim

# 2. Set Environment Variables
# PYTHONUNBUFFERED=1: Forces Python stdout/stderr to be unbuffered (better logging in Render/Railway)
# PYTHONDONTWRITEBYTECODE=1: Prevents Python from writing .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# 3. Install System Dependencies
# Install tesseract-ocr and clean up the apt cache in the same layer to minimize image size
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# 4. Create a non-root user for security best practices
RUN useradd -m -u 1000 appuser

# 5. Set Working Directory
WORKDIR /app

# 6. Copy Requirements First (Caching Layer)
# We copy only requirements.txt first. If it hasn't changed, Docker uses the cached layer for pip install
COPY --chown=appuser:appuser requirements.txt .

# 7. Install Python Dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 8. Copy Application Code
# Copy the rest of the application files, assigning ownership to the non-root user
COPY --chown=appuser:appuser . .

# 9. Switch to Non-Root User
USER appuser

# 10. Expose the Application Port
EXPOSE $PORT

# 11. Run FastAPI via Uvicorn
# Using sh -c allows platforms like Render to inject their own dynamic $PORT if necessary, 
# while defaulting to 8000 for local development.
CMD ["sh", "-c", "uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-8000}"]