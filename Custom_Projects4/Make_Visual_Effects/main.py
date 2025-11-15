from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
import subprocess
import requests
import tempfile
import os

app = FastAPI(title="Audio Visualizer Streaming API")

@app.get("/visualizer")
async def visualizer(audio_url: str = Query(..., description="Public URL to your audio file")):
    if not audio_url:
        raise HTTPException(status_code=400, detail="Audio URL is required")
    
    try:
        resp = requests.get(audio_url, stream=True)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download audio: {str(e)}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
        for chunk in resp.iter_content(chunk_size=1024*1024):
            if chunk:
                tmp_file.write(chunk)
        tmp_file_path = tmp_file.name

    ffmpeg_cmd = [
        "ffmpeg",
        "-i", tmp_file_path,
        "-filter_complex",
        "aformat=channel_layouts=mono,showwaves=s=1080x1080:mode=circle:colors=white",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-movflags", "frag_keyframe+empty_moov",
        "-f", "mp4",
        "pipe:1"
    ]

    try:
        process = subprocess.Popen(
            ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except Exception as e:
        os.remove(tmp_file_path)
        raise HTTPException(status_code=500, detail=f"Failed to start visualizer: {str(e)}")

    def iter_video():
        try:
            while True:
                chunk = process.stdout.read(1024*1024)
                if not chunk:
                    break
                yield chunk
            process.wait()  
        finally:
            process.stdout.close()
            process.stderr.close()
            os.remove(tmp_file_path)

    return StreamingResponse(
        iter_video(),
        media_type="video/mp4",
        headers={"Content-Disposition": 'attachment; filename="visualizer.mp4"'}
    )
