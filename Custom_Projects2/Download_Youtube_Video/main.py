from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import uuid
import os

app = FastAPI(title="YouTube Downloader API")

class VideoRequest(BaseModel):
    url: str

@app.post("/download")
async def download_video(req: VideoRequest):
    video_url = req.url

    if not video_url:
        raise HTTPException(status_code=400, detail="URL is required")

    output_filename = f"{uuid.uuid4()}.mp4"

    cmd = [
        "yt-dlp",
        "-o", output_filename,
        "-f", "bestvideo+bestaudio/best",
        video_url
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Download failed: {e.stderr.decode('utf-8', errors='ignore')}"
        )

    return {
        "status": "success",
        "file": output_filename,
        "path": os.path.abspath(output_filename)
    }
