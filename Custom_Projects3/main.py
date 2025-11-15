from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import subprocess
import shlex

app = FastAPI(title="YouTube Audio Downloader Streaming API")

class VideoRequest(BaseModel):
    url: str

@app.post("/download")
async def download_audio(req: VideoRequest):
    video_url = req.url
    if not video_url:
        raise HTTPException(status_code=400, detail="URL is required")

    cmd = f'yt-dlp -f bestaudio -x --audio-format mp3 -o - {shlex.quote(video_url)}'

    try:
        process = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start download: {str(e)}")

    def iter_audio():
        try:
            while True:
                chunk = process.stdout.read(1024 * 1024) 
                if not chunk:
                    break
                yield chunk
        finally:
            process.stdout.close()
            process.stderr.close()
            process.terminate()

    return StreamingResponse(
        iter_audio(),
        media_type="audio/mpeg",
        headers={"Content-Disposition": 'attachment; filename="audio.mp3"'}
    )
