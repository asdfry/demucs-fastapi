import os
import shutil
import time
from glob import glob

import audioread
from fastapi import FastAPI, File, Form, UploadFile
from google.cloud import firestore, storage

storage_client = storage.Client()
bucket = storage_client.bucket(os.environ.get("BUCKET_NAME"))
firestore_client = firestore.Client()
collection = firestore_client.collection(os.environ.get("COLLECTION_NAME"))
app = FastAPI()


def second_to_duration(sec) -> str:
    sec = int(sec)
    hours, remainder = divmod(sec, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{str(hours).zfill(2)}:{str(minutes).zfill(2)}:{str(seconds).zfill(2)}"


@app.post("/separate")
def separate(upload_file: UploadFile = File(...), filename: str = Form(...), token: str = Form(...)):

    start_time = time.time()
    filename_only = filename.split(".")[0]

    with open(filename, "wb") as buffer:  # 오디오 파일 복사
        shutil.copyfileobj(upload_file.file, buffer)

    # Firestore 데이터 업데이트
    if not "duration" in collection.document(token).get().to_dict():  # duration 정보가 없는 경우 (upload_file을 file로 받은 경우)
        with audioread.audio_open(filename) as f:  # 오디오 정보 확인
            duration = f.duration
        collection.document(token).update({"status": "progress", "duration": second_to_duration(duration)})
    else:
        collection.document(token).update({"status": "progress"})


    os.system(f"python3 -m demucs.separate --two-stems=vocals -d cpu '{filename}'")  # 음원 분리 실행
    output_files = glob(f"/separated/mdx_extra_q/{filename_only}/*")  # 결과 파일 리스트

    if output_files:
        urls = []  # 다운로드 링크를 담을 리스트
        for output_file in output_files:
            blob = bucket.blob(f"{token}_{filename_only}_{output_file.split('/')[-1]}")  # 객체 이름 설정
            blob.upload_from_filename(output_file)  # 객체 생성
            blob.make_public()  # 객체 공개화
            urls.append(blob.public_url)  # 다운로드 링크 추가

        collection.document(token).update(  # Firestore 데이터 업데이트 및 다운로드 링크 추가
            {"status": "done", "path": urls, "process_time": round((time.time() - start_time), 3)}
        )
        os.system(f"rm '{filename}' && rm -rf /separated")
    else:
        collection.document(token).update(  # Firestore 데이터 업데이트
            {"status": "fail", "process_time": round((time.time() - start_time), 3)}
        )
