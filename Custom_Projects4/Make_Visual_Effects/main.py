from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import subprocess
import requests
import tempfile
import os
from pydantic import BaseModel
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("main")

app = FastAPI(title="Audio Visualizer Streaming API")

class AudioRequest(BaseModel):
    audio_url: str

@app.post("/visualizer")
async def visualizer(request: AudioRequest):
    audio_url = request.audio_url
    logger.debug(f"Received request: audio_url='{audio_url}'")
    
    if not audio_url:
        raise HTTPException(status_code=400, detail="Audio URL is required")
    
    try:
        logger.debug("Starting to download the audio file...")
        resp = requests.get(audio_url, stream=True)
        resp.raise_for_status()
        logger.debug(f"Audio file download successful. Status code: {resp.status_code}")
    except Exception as e:
        logger.error(f"Failed to download audio: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to download audio: {str(e)}")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".audio") as tmp_file:
            logger.debug("Writing audio to temporary file...")
            for chunk in resp.iter_content(chunk_size=1024*1024):
                if chunk:
                    tmp_file.write(chunk)
            tmp_file_path = tmp_file.name
        logger.debug(f"Audio saved to temporary file: {tmp_file_path}")
    except Exception as e:
        logger.error(f"Failed to save audio: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save audio: {str(e)}")

    ffmpeg_cmd = [
        "ffmpeg",
        "-i", tmp_file_path,
        "-map", "0:a:0",
        "-filter_complex",
        "aformat=channel_layouts=mono,showwaves=s=1080x1080:mode=line:colors=white",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-movflags", "frag_keyframe+empty_moov",
        "-f", "mp4",
        "pipe:1"
    ]
    logger.debug(f"Running ffmpeg command: {' '.join(ffmpeg_cmd)}")

    try:
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.debug("FFmpeg process started successfully.")
    except Exception as e:
        logger.error(f"Failed to start FFmpeg: {e}")
        os.remove(tmp_file_path)
        raise HTTPException(status_code=500, detail=f"Failed to start visualizer: {str(e)}")

    def iter_video():
        try:
            logger.debug("Starting to stream video chunks...")
            while True:
                chunk = process.stdout.read(1024*1024)
                if not chunk:
                    logger.debug("End of video stream reached.")
                    break
                yield chunk
            process.wait()
        finally:
            logger.debug("Cleaning up resources...")
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
