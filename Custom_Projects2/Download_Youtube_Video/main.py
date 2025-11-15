from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import subprocess
import uuid
import os
import shutil

app = FastAPI(title="YouTube Downloader API with Background Tasks")

DOWNLOAD_DIR = "/app/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class VideoRequest(BaseModel):
    url: str

jobs = {}

def download_video_job(video_url: str, output_path: str, job_id: str):
    try:
        cmd = [
            "yt-dlp",
            "-f", "bestvideo+bestaudio/best",
            "-o", output_path,
            video_url
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        jobs[job_id]["status"] = "completed"
    except subprocess.CalledProcessError as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = e.stderr.decode("utf-8", errors="ignore")

@app.post("/download")
async def create_download(req: VideoRequest, background_tasks: BackgroundTasks):
    if not req.url:
        raise HTTPException(status_code=400, detail="URL is required")

    job_id = str(uuid.uuid4())
    output_filename = f"{job_id}.mp4"
    output_path = os.path.join(DOWNLOAD_DIR, output_filename)

    jobs[job_id] = {"status": "pending", "file": output_filename}

    background_tasks.add_task(download_video_job, req.url, output_path, job_id)

    return {"status": "queued", "job_id": job_id}

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job ID not found")
    return jobs[job_id]

@app.get("/file/{job_id}")
async def get_file(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job ID not found")
    job = jobs[job_id]
    if job["status"] != "completed":
        return JSONResponse(status_code=400, content={"status": job["status"]})
    file_path = os.path.join(DOWNLOAD_DIR, job["file"])
    if not os.path.exists(file_path):
        raise HTTPException(status_code=500, detail="File missing")
    response = FileResponse(path=file_path, filename=job["file"], media_type="video/mp4")
    return response
