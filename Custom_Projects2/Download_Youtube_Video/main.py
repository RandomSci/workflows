from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess
import uuid
import os

app = FastAPI(title="YouTube Downloader API with Cookies")

COOKIES_FILE = "/app/cookies.txt"

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
        "--cookies", COOKIES_FILE,
        "--extractor-args", "youtube:player_client=default",
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

    if not os.path.exists(output_filename):
        raise HTTPException(status_code=500, detail="Video download failed or file missing.")

    return FileResponse(path=output_filename, filename=output_filename, media_type="video/mp4")
