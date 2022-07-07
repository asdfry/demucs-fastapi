import datetime
import os
from threading import Thread
from urllib.request import urlretrieve
from urllib.error import HTTPError, URLError
from uuid import uuid4

import audioread
import requests
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


def request_separate(upload_file, filename, token):
    requests.post(
        url=os.environ.get("SEP_API_URL"),
        files={"upload_file": upload_file},
        data={"filename": filename, "token": token},
    )


def second_to_duration(sec) -> str:
    sec = int(sec)
    hours, remainder = divmod(sec, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{str(hours).zfill(2)}:{str(minutes).zfill(2)}:{str(seconds).zfill(2)}"


@app.post("/job_file", status_code=201)
def create_job_file(upload_file: UploadFile = File(...)):

    # Firestore 데이터 생성
    token = create_token()
    collection.document(token).set(
        {
            "create_time": datetime.datetime.utcnow(),
            "status": "wait",
            "filename": upload_file.filename,
        }
    )

    Thread(  # 쓰레드를 통해 separate API 호출
        target=request_separate, args=[upload_file.file, upload_file.filename, token]
    ).start()

    return {"status": 201, "message": "created", "token": token}


@app.post("/job_url", status_code=201)
def create_job_url(body=Body(...)):

    if "url" in body:
        url = body["url"]
    else:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"status": 400, "message": "'url' not in body"}
        )

    try:
        filename, _ = urlretrieve(url)  # 오디오 파일 복사 (filename 예시: /tmp/tmpo613nsz5)
        filename_wt_slash = filename.split("/")[-1]

        with audioread.audio_open(filename) as f:  # 오디오 정보 확인
            duration = f.duration

        # Firestore 데이터 생성
        token = create_token()
        collection.document(token).set(
            {
                "create_time": datetime.datetime.utcnow(),
                "status": "wait",
                "filename": filename_wt_slash,
                "duration": second_to_duration(duration),
            }
        )
        audio_file = open(filename, "rb")

        Thread(target=request_separate, args=[audio_file, filename_wt_slash, token]).start()  # 쓰레드를 통해 separate API 호출
        os.system(f"rm {filename}")  # 복사한 오디오 파일 삭제

        return {"status": 201, "message": "created", "token": token}

    except HTTPError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"status": 400, "message": "HTTPError"}
        )

    except URLError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"status": 400, "message": "URLError"}
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"status": 400, "message": str(e)}
        )


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
    dict_return = {}
    for idx, doc in enumerate(collection.stream()):
        dict_temp = doc.to_dict()
        dict_return[idx] = {
            "date": dict_temp["create_time"],
            "token": doc.id,
            "filename": dict_temp["filename"],
            "status": dict_temp["status"]
        }
        if dict_temp["status"] == "done":  # 완료된 작업인 경우 정보 추가
            dict_return[idx]["accompaniment"] = dict_temp["path"][0]
            dict_return[idx]["vocal"] = dict_temp["path"][1]
            dict_return[idx]["length"] = dict_temp["duration"]
            dict_return[idx]["process_time"] = dict_temp["process_time"]

    return dict_return
