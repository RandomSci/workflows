from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess
import uuid
import os

app = FastAPI(title="YouTube Downloader API with Cookies")

COOKIES_FILE = "/app/cookies.txt"
DOWNLOAD_DIR = "/app/downloads"

# Ensure download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class VideoRequest(BaseModel):
    url: str

@app.post("/download")
async def download_video(req: VideoRequest):
    video_url = req.url

    if not video_url:
        raise HTTPException(status_code=400, detail="URL is required")

    if not os.path.exists(COOKIES_FILE):
        raise HTTPException(status_code=500, detail="Cookies file not found.")

    output_filename = f"{uuid.uuid4()}.mp4"
    output_path = os.path.join(DOWNLOAD_DIR, output_filename)

    cmd = [
        "yt-dlp",
        "--cookies", COOKIES_FILE,
        "--extractor-args", "youtube:player_client=default",
        "-o", output_path,
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

    if not os.path.exists(output_path):
        raise HTTPException(status_code=500, detail="Video download failed or file missing.")

    return FileResponse(path=output_path, filename=output_filename, media_type="video/mp4")
