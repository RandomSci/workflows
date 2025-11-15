import io
import subprocess
import tempfile
import requests
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("main")

app = FastAPI(title="Audio Visualizer Streaming API")

class AudioRequest(BaseModel):
    audio_url: str

def download_file(url: str) -> io.BytesIO:
    logger.debug(f"Downloading from URL: {url}")

    # Use webContentLink directly
    if "uc?id=" in url and "export=download" not in url:
        direct_url = url + "&export=download"
    else:
        direct_url = url

    logger.debug(f"Final download URL: {direct_url}")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })

    try:
        response = session.get(direct_url, stream=True, allow_redirects=True, timeout=60)
        response.raise_for_status()

        # Check first chunk
        first_chunk = next(response.iter_content(1024), b"")
        if not first_chunk:
            raise HTTPException(status_code=400, detail="File is empty or blocked")

        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" in content_type:
            raise HTTPException(status_code=400, detail="Received HTML. File not accessible.")

    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=400, detail=f"Download failed: {str(e)}")

    file_data = io.BytesIO()
    for chunk in response.iter_content(chunk_size=1024*1024):
        if chunk:
            file_data.write(chunk)
    file_data.seek(0)
    logger.debug(f"Downloaded file data: {file_data.getbuffer().nbytes} bytes")
    return file_data

def validate_audio_file(file_data: io.BytesIO) -> bool:
    cmd = ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", "-"]
    try:
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate(input=file_data.read())
        if process.returncode != 0:
            logger.error(f"Validation failed: {stderr.decode()}")
            return False
        return bool(stdout.strip())
    except Exception as e:
        logger.error(f"Validation failed: {str(e)}")
        return False

@app.post("/visualizer")
async def visualizer(request: AudioRequest):
    audio_url = request.audio_url.strip()
    if not audio_url:
        raise HTTPException(status_code=400, detail="Audio URL required")

    file_data = None

    try:
        file_data = download_file(audio_url)
        if not validate_audio_file(file_data):
            raise HTTPException(status_code=400, detail="No audio stream")

        # Generate the audio spectrum directly from in-memory data
        vis_cmd = [
            "ffmpeg", "-y", "-f", "wav", "-i", "pipe:0", 
            "-filter_complex", "[0:a]showwaves=s=640x360:mode=line:colors=white[col];[col]format=yuv420p[out]", 
            "-map", "[out]", "-c:v", "libx264", "-preset", "ultrafast", "-movflags", "frag_keyframe+empty_moov", 
            "-f", "mp4", "pipe:1"
        ]
        process = subprocess.Popen(vis_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Stream the video directly
        def video_stream():
            try:
                while True:
                    data = process.stdout.read(1024 * 1024)
                    if not data:
                        break
                    yield data
                process.wait()
                if process.returncode != 0:
                    err = process.stderr.read().decode()
                    logger.error(f"Visualizer error: {err}")
            finally:
                process.stdout.close()
                process.stderr.close()

        return StreamingResponse(
            video_stream(),
            media_type="video/mp4",
            headers={"Content-Disposition": 'attachment; filename="visualizer.mp4"'}
        )

    except Exception as e:
        logger.exception("Unexpected error")
        raise HTTPException(status_code=500, detail=str(e))
