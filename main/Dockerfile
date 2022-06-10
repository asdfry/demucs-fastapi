FROM python:3.8-slim

COPY main.py requirements.txt key.json ./

RUN cat requirements.txt | grep -v '^#' | xargs -n 1 -L 1 pip install --timeout 60 --no-cache-dir

ENV GOOGLE_APPLICATION_CREDENTIALS=key.json

CMD uvicorn main:app --host 0.0.0.0 --port 8000
