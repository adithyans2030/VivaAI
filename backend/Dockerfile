FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for audio processing, ffmpeg, and compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libsndfile1 \
    fonts-dejavu-core \
    curl \
    && rm -rf /var/lib/apt/lists/*

ARG REQUIREMENTS_FILE=requirements.txt
COPY requirements.txt requirements-ml.txt ./
RUN pip install --no-cache-dir -r ${REQUIREMENTS_FILE}

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
