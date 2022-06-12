import os
import shutil
import time
from glob import glob

from fastapi import FastAPI, File, Form, UploadFile
from google.cloud import firestore, storage

storage_client = storage.Client()
bucket = storage_client.bucket("klleon-output")
firestore_client = firestore.Client()
collection = firestore_client.collection("klleon")
app = FastAPI()


@app.post("/separate")
def separate(upload_file: UploadFile = File(...), filename: str = Form(...), token: str = Form(...)):

    start_time = time.time()
    filename_only = filename.split(".")[0]

    with open(filename, "wb") as buffer:  # 오디오 파일 복사
        shutil.copyfileobj(upload_file.file, buffer)

    collection.document(token).set({"status": "progress"})  # 상태 변경
    os.system(f"python3 -m demucs.separate --two-stems=vocals -d cpu '{filename}'")  # 음원 분리 실행
    output_files = glob(f"/separated/mdx_extra_q/{filename_only}/*")  # 결과 파일 리스트

    if output_files:
        urls = []  # 다운로드 링크를 담을 리스트
        for output_file in output_files:
            blob = bucket.blob(f"{token}-{filename_only}_{output_file.split('/')[-1]}")  # 객체 이름 설정
            blob.upload_from_filename(output_file)  # 객체 생성
            blob.make_public()  # 객체 공개화
            urls.append(blob.public_url)  # 다운로드 링크 추가

        collection.document(token).set(  # 상태 변경 및 다운로드 링크 추가
            {"status": "done", "path": urls, "time": round((time.time() - start_time), 3)}
        )
        os.system(f"rm '{filename}' && rm -rf /separated")
    else:
        collection.document(token).set(  # 상태 변경
            {"status": "fail", "time": round((time.time() - start_time), 3)}
        )
