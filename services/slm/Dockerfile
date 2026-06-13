FROM python:3.11-slim

ARG MODEL_ID=Qwen/Qwen2.5-Coder-0.5B-Instruct
ARG DOWNLOAD_MODEL_AT_BUILD=true

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models/hf \
    MODEL_ID=${MODEL_ID}

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt
COPY app ./app

RUN if [ "$DOWNLOAD_MODEL_AT_BUILD" = "true" ]; then python -m app.download_model; else echo "Skipping model download"; fi

CMD ["python", "-m", "app.main"]
