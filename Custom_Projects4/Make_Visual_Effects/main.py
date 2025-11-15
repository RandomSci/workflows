from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import subprocess
import tempfile
import os
import logging
from pydantic import BaseModel
import requests
import re

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("main")

app = FastAPI(title="Audio Visualizer Streaming API")

class AudioRequest(BaseModel):
    audio_url: str  # Can be direct or Google Drive link

def download_file(url: str) -> str:
    """
    Downloads a file and returns its temporary path.
    Supports Google Drive links (publicly shared) automatically.
    """
    logger.debug(f"Downloading audio from URL: {url}")

    drive_match = re.match(r"https://drive\.google\.com/uc\?id=([a-zA-Z0-9_-]+)", url)
    if drive_match:
        file_id = drive_match.group(1)
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        logger.debug(f"Detected Google Drive file, updated URL: {url}")

    try:
        resp = requests.get(url, stream=True)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to download audio: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to download audio: {str(e)}")

    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".audio")
    for chunk in resp.iter_content(chunk_size=1024*1024):
        if chunk:
            tmp_file.write(chunk)
    tmp_file_path = tmp_file.name
    tmp_file.close()

    logger.debug(f"Audio saved to temporary file: {tmp_file_path}")
    return tmp_file_path

@app.post("/visualizer")
async def visualizer(request: AudioRequest):
    audio_url = request.audio_url
    if not audio_url:
        raise HTTPException(status_code=400, detail="Audio URL is required")

    tmp_file_path = download_file(audio_url)

    ffmpeg_cmd = [
        "ffmpeg",
        "-i", tmp_file_path,
        "-ac", "1",               
        "-ar", "44100",           
        "-f", "wav",             
        "-filter_complex",        
        "showwaves=s=1080x1080:mode=line:colors=white",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",        
        "-preset", "veryfast",    
        "-movflags", "frag_keyframe+empty_moov",  
        "-f", "mp4",             
        "pipe:1"                 
    ]

    logger.debug(f"Running FFmpeg command: {' '.join(ffmpeg_cmd)}")

    try:
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except Exception as e:
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
        raise HTTPException(status_code=500, detail=f"Failed to start visualizer: {str(e)}")

    def iter_video():
        try:
            logger.debug("Streaming video chunks...")
            while True:
                chunk = process.stdout.read(1024*1024)
                if not chunk:
                    logger.debug("End of video stream reached.")
                    break
                yield chunk
            process.wait()
            stderr_output = process.stderr.read().decode()
            if stderr_output:
                logger.error(f"FFmpeg stderr:\n{stderr_output}")
        finally:
            process.stdout.close()
            process.stderr.close()
            if os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)
            logger.debug("Temporary audio file removed.")

    return StreamingResponse(
        iter_video(),
        media_type="video/mp4",
        headers={"Content-Disposition": 'attachment; filename="visualizer.mp4"'}
    )
