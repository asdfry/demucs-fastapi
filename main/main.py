import datetime
import os
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from uuid import uuid4

import httpx
from fastapi import Body, FastAPI, File, UploadFile, status
from fastapi.responses import JSONResponse
from google.cloud import firestore

firestore_client = firestore.Client()
collection = firestore_client.collection(os.environ.get("COLLECTION_NAME"))
app = FastAPI()


def create_token():
    token = str(uuid4())
    ids = [doc.id for doc in collection.stream()]  # 현재 Firestore에 저장되어 있는 ID 리스트
    while token in ids:  # 새 token이 중복되지 않을 때 까지 반복
        token = str(uuid4())
    return token


async def request_separate(upload_file=None, filename=None, token=None, fileurl=None):
    async with httpx.AsyncClient() as client:
        if fileurl:
            await client.post(
                url=os.environ.get("SEP_API_URL"),
                data={"fileurl": fileurl, "token": token},
                timeout=0.1,
            )
        else:
            await client.post(
                url=os.environ.get("SEP_API_URL"),
                files={"upload_file": upload_file},
                data={"filename": filename, "token": token},
                timeout=0.1,
            )


def second_to_duration(sec) -> str:
    sec = int(sec)
    hours, remainder = divmod(sec, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{str(hours).zfill(2)}:{str(minutes).zfill(2)}:{str(seconds).zfill(2)}"


@app.post("/job_file", status_code=201)
async def create_job_file(upload_file: UploadFile = File(...)):

    # Firestore 데이터 생성
    token = create_token()
    collection.document(token).set(
        {
            "create_time": datetime.datetime.utcnow(),
            "status": "wait",
            "filename": upload_file.filename,
        }
    )

    try:  # 비동기 요청
        await request_separate(upload_file=upload_file.file, filename=upload_file.filename, token=token)
    except httpx.ReadTimeout:
        return {"status": 201, "message": "created", "token": token}


@app.post("/job_url", status_code=201)
async def create_job_url(body=Body(...)):

    if "url" in body:
        url = body["url"]
    else:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"status": 400, "message": "'url' not in body"}
        )

    try:
        urlopen(url)  # 오디오 파일 복사 (filename 예시: /tmp/tmpo613nsz5)

    except HTTPError:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": 400, "message": "HTTPError"})

    except URLError:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": 400, "message": "URLError"})

    except Exception as e:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": 400, "message": str(e)})

    # Firestore 데이터 생성
    token = create_token()
    collection.document(token).set(
        {
            "create_time": datetime.datetime.utcnow(),
            "status": "wait",
        }
    )

    try:  # 비동기 요청
        await request_separate(fileurl=url, token=token)
    except httpx.ReadTimeout:
        return {"status": 201, "message": "created", "token": token}


@app.post("/result", status_code=200)
def get_result(body=Body(...)):
    token = body["token"]
    doc = collection.document(token).get().to_dict()

    if not doc["status"] == "done":  # 상태가 완료가 아닌 경우 상태만 출력
        return {"status": 200, "message": doc["status"]}
    else:  # 상태가 완료인 경우 상태와 다운로드 링크까지 출력
        return {
            "status": 200,
            "message": doc["status"],
            "data": {"accompaniment": doc["path"][0], "vocals": doc["path"][1]},
        }


@app.get("/all-result", status_code=200)
def get_all_result():
    docs = []
    for doc in collection.stream():
        dict_temp = doc.to_dict()
        docs.append(
            {
                "date": dict_temp["create_time"],
                "token": doc.id,
                "filename": dict_temp["filename"],
                "status": dict_temp["status"],
            }
        )
        if dict_temp["status"] == "done":  # 완료된 작업인 경우 정보 추가
            docs[-1]["accompaniment"] = dict_temp["path"][0]
            docs[-1]["vocal"] = dict_temp["path"][1]
            docs[-1]["length"] = dict_temp["duration"]
            docs[-1]["process_time"] = dict_temp["process_time"]
    docs = sorted(docs, key=lambda x: x["date"])
    dict_return = {idx: doc for idx, doc in enumerate(docs)}
    return dict_return
