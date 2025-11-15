from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import subprocess
import shlex

app = FastAPI(title="YouTube Downloader Streaming API")

class VideoRequest(BaseModel):
    url: str

@app.post("/download")
async def download_video(req: VideoRequest):
    video_url = req.url
    if not video_url:
        raise HTTPException(status_code=400, detail="URL is required")

    # yt-dlp command to write to stdout in mp4 format
    cmd = f'yt-dlp -f "bestvideo+bestaudio/best" -o - {shlex.quote(video_url)}'
    
    try:
        # Run yt-dlp as subprocess, stdout=PIPE streams to response
        process = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start download: {str(e)}")

    # Stream stdout to client
    def iter_video():
        try:
            while True:
                chunk = process.stdout.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                yield chunk
        finally:
            process.stdout.close()
            process.stderr.close()
            process.terminate()

    return StreamingResponse(
        iter_video(),
        media_type="video/mp4",
        headers={"Content-Disposition": 'attachment; filename="video.mp4"'}
    )
