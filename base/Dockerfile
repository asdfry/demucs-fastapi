FROM python:3.8-slim

COPY requirements.txt .

RUN apt update && apt install -y git && \
    cat requirements.txt | grep -v '^#' | xargs -n 1 -L 1 pip install --timeout 60 --no-cache-dir && \
    git clone -b main --single-branch https://github.com/facebookresearch/demucs && \
    cd demucs && python3 -m pip install -e . && \
    python3 -m demucs.separate -d cpu test.mp3 && \
    rm -r separated
