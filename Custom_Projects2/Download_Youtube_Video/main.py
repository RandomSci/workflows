import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
import shlex
import uuid

app = FastAPI(title="YouTube Downloader API with Cookies")

COOKIES_FILE = "/app/cookies.txt"

if not os.path.exists(COOKIES_FILE):
    raise RuntimeError("cookies.txt not found at /app/cookies.txt")

class VideoRequest(BaseModel):
    url: str

@app.post("/download")
async def download_video(req: VideoRequest, request: Request):
    video_url = req.url
    if not video_url:
        raise HTTPException(status_code=400, detail="URL is required")

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
                chunk = await process.stdout.read(2 * 1024 * 1024) 
                if not chunk:
                    break
                yield chunk

                if await request.is_disconnected():
                    process.kill()
                    break

            await process.wait()

            if process.returncode != 0:
                stderr = await process.stderr.read()
                raise HTTPException(
                    status_code=500,
                    detail=f"yt-dlp failed: {stderr.decode(errors='ignore')}"
                )

        except Exception:
            process.kill()
            raise

    filename = f"{uuid.uuid4()}.mp4"
    return StreamingResponse(
        stream_generator(),
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
