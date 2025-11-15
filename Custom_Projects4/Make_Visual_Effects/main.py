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
    audio_url: str

def download_file(url: str) -> str:
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

    suffix = ".webm"
    if "mp3" in content_type: suffix = ".mp3"
    elif "wav" in content_type: suffix = ".wav"
    elif "mp4" in content_type: suffix = ".mp4"

    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp_file.write(first_chunk)
        for chunk in response.iter_content(chunk_size=1024*1024):
            if chunk:
                tmp_file.write(chunk)
        tmp_file.close()
        size = os.path.getsize(tmp_file.name)
        if size == 0:
            os.unlink(tmp_file.name)
            raise HTTPException(status_code=400, detail="Downloaded file is 0 bytes")
        logger.debug(f"Downloaded: {tmp_file.name} ({size} bytes)")
        return tmp_file.name
    except Exception as e:
        if os.path.exists(tmp_file.name):
            os.unlink(tmp_file.name)
        raise HTTPException(status_code=500, detail=f"Save failed: {e}")

def validate_audio_file(filepath: str) -> bool:
    cmd = ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", filepath]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return bool(result.stdout.strip())
    except:
        return False

@app.post("/visualizer")
async def visualizer(request: AudioRequest):
    audio_url = request.audio_url.strip()
    if not audio_url:
        raise HTTPException(status_code=400, detail="Audio URL required")

    downloaded_file = None
    pcm_audio_path = None

    try:
        # === DOWNLOAD ===
        downloaded_file = download_file(audio_url)
        if not validate_audio_file(downloaded_file):
            raise HTTPException(status_code=400, detail="No audio stream")

        # === CONVERT TO WAV ===
        pcm_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        pcm_audio_path = pcm_file.name
        pcm_file.close()

        convert_cmd = [
            "ffmpeg", "-y", "-i", downloaded_file,
            "-vn", "-ac", "1", "-ar", "44100", "-f", "wav", pcm_audio_path
        ]
        logger.debug(f"Convert: {' '.join(convert_cmd)}")
        result = subprocess.run(convert_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Convert failed: {result.stderr}")
            raise HTTPException(status_code=500, detail="Audio conversion failed")

        if not os.path.exists(pcm_audio_path) or os.path.getsize(pcm_audio_path) == 0:
            raise HTTPException(status_code=500, detail="WAV file missing or empty")

        # === GENERATE VISUALIZER ===
        vis_cmd = [
            "ffmpeg", "-y", "-i", pcm_audio_path,
            "-filter_complex", "showwaves=s=1080x1080:mode=line:colors=white",
            "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast",
            "-movflags", "frag_keyframe+empty_moov", "-f", "mp4", "pipe:1"
        ]
        logger.debug(f"Visualizer: {' '.join(vis_cmd)}")
        process = subprocess.Popen(vis_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # === STREAM + CLEANUP AFTER STREAM ENDS ===
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
                for path in [downloaded_file, pcm_audio_path]:
                    if path and os.path.exists(path):
                        try:
                            os.unlink(path)
                            logger.debug(f"Cleaned up: {path}")
                        except:
                            pass

        return StreamingResponse(
            video_stream(),
            media_type="video/mp4",
            headers={"Content-Disposition": 'attachment; filename="visualizer.mp4"'}
        )

    except HTTPException:
        # Cleanup on error
        for path in [downloaded_file, pcm_audio_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except:
                    pass
        raise
    except Exception as e:
        logger.exception("Unexpected error")
        for path in [downloaded_file, pcm_audio_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except:
                    pass
        raise HTTPException(status_code=500, detail=str(e))