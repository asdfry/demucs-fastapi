from threading import Thread
from uuid import uuid4

import json
import requests
from google.cloud import firestore
from fastapi import Body, FastAPI, File, UploadFile

firestore_client = firestore.Client()
collection = firestore_client.collection("klleon")
app = FastAPI()


def request_separate(upload_file, filename, token):
    requests.post(
        url="http://separate:7000/separate",
        files={"upload_file": upload_file},
        data={"filename": filename, "token": token},
    )


@app.post("/job", status_code=201)
def create_job(upload_file: UploadFile = File(...)):
    token = str(uuid4())
    ids = [doc.id for doc in collection.stream()]  # 현재 Firestore에 저장되어 있는 ID 리스트
    while token in ids:  # 새 token이 중복되지 않을 때 까지 반복
        token = str(uuid4())
    collection.document(token).set({"status": "wait"})  # Firestore에 데이터 생성
    Thread(target=request_separate, args=[upload_file.file, upload_file.filename, token]).start()  # 쓰레드를 통해 separate API 호출
    return {"status": 201, "message": "created", "token": token}


@app.get("/result", status_code=200)
def get_result(body=Body(...)):
    token = json.loads(body.decode())["token"]
    doc = collection.document(token).get().to_dict()
    if not doc["status"] == "done":  # 상태가 완료가 아닌 경우 상태만 출력
        return {"status": 200, "message": doc["status"]}
    else:  # 상태가 완료인 경우 상태와 다운로드 링크까지 출력
        return {
            "status": 200,
            "message": doc["status"],
            "data": {"accompaniment": doc["path"][0], "vocals": doc["path"][1]},
        }
