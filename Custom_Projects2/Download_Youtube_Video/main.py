import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import subprocess
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
    if not os.path.exists(COOKIES_FILE):
        raise HTTPException(status_code=500, detail="Cookies file not found.")

    cmd = [
        "yt-dlp",
        "--cookies", COOKIES_FILE,
        "--extractor-args", "youtube:player_client=default",
        "-f", "bestvideo+bestaudio/best",
        "-o", "-",  
        video_url
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    async def stream_generator():
        try:
            while True:
                chunk = await process.stdout.read(1024*1024) 
                if not chunk:
                    break
                yield chunk
            await process.wait()
        except Exception:
            process.kill()
            raise

    return StreamingResponse(stream_generator(), media_type="video/mp4")
