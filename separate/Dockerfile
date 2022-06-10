FROM python:3.8-slim

# COPY requirements.txt main.py key.json ./
COPY requirements.txt key.json ./

RUN apt update && apt install -y git ffmpeg && \
    cat requirements.txt | grep -v '^#' | xargs -n 1 -L 1 pip install --timeout 60 --no-cache-dir && \
    git clone -b main --single-branch https://github.com/facebookresearch/demucs && \
    cd demucs && python3 -m pip install -e . && \
    python3 -m demucs.separate -d cpu test.mp3 && \
    rm -r separated

ENV GOOGLE_APPLICATION_CREDENTIALS=key.json

# CMD uvicorn main:app --host 0.0.0.0 --port 7000
