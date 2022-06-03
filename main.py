import os
import shutil
from fastapi import FastAPI, File, UploadFile

os.system("cd demucs")
app = FastAPI()

@app.post("/separate")
async def separate(upload_file: UploadFile = File(...)):
    upload_file_path = f"demucs/uploaded_file/{upload_file.filename}"
    with open(upload_file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    os.system(f"python3 -m demucs.separate --two-stems=vocals -d cpu {upload_file_path}")
    print(os.system(f"ls separated/mdx_extra_q/{upload_file.filename}"))
