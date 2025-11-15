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
    file_id_match = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if not file_id_match:
        raise HTTPException(status_code=400, detail="Invalid Google Drive URL")
    file_id = file_id_match.group(1)
    direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    logger.debug(f"Direct URL: {direct_url}")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })

    try:
        response = session.get(direct_url, stream=True, allow_redirects=True, timeout=30)
        response.raise_for_status()

        if "text/html" in response.headers.get("Content-Type", ""):
            confirm_match = re.search(r'confirm=([0-9A-Za-z_]+)', response.text)
            if not confirm_match:
                raise HTTPException(status_code=400, detail="Virus scan page: no confirm token")
            token = confirm_match.group(1)
            response = session.get(f"{direct_url}&confirm={token}", stream=True, timeout=60)
            response.raise_for_status()
            if "text/html" in response.headers.get("Content-Type", ""):
                raise HTTPException(status_code=400, detail="Failed to bypass virus scan")

        content_type = response.headers.get("Content-Type", "").lower()
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=400, detail=f"Download failed: {str(e)}")

    suffix = ".webm"
    if "mp3" in content_type: suffix = ".mp3"
    elif "wav" in content_type: suffix = ".wav"
    elif "mp4" in content_type: suffix = ".mp4"

    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        for chunk in response.iter_content(chunk_size=1024*1024):
            if chunk:
                tmp_file.write(chunk)
        tmp_file.close()
        logger.debug(f"Downloaded: {tmp_file.name} ({os.path.getsize(tmp_file.name)} bytes)")
        return tmp_file.name
    except Exception as e:
        os.unlink(tmp_file.name)
        raise HTTPException(status_code=500, detail=f"Save failed: {e}")

def validate_audio_file(filepath: str) -> bool:
    cmd = ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", filepath]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return bool(result.stdout.strip())
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        logger.error("ffprobe not found")
        raise HTTPException(status_code=500, detail="FFmpeg not installed")

@app.post("/visualizer")
async def visualizer(request: AudioRequest):
    audio_url = request.audio_url.strip()
    if not audio_url:
        raise HTTPException(status_code=400, detail="Audio URL required")

    # Keep file handles to prevent deletion
    downloaded_file = None
    pcm_file_obj = None
    pcm_audio_path = None

    try:
        # === DOWNLOAD ===
        downloaded_file = download_file(audio_url)

        # === VALIDATE ===
        if not validate_audio_file(downloaded_file):
            raise HTTPException(status_code=400, detail="No audio stream")

        # === CONVERT TO WAV (keep file open) ===
        pcm_file_obj = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        pcm_audio_path = pcm_file_obj.name
        pcm_file_obj.close()  # Close handle but keep file

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
            raise HTTPException(status_code=500, detail="WAV file empty or missing")

        # === GENERATE VISUALIZER ===
        vis_cmd = [
            "ffmpeg", "-y", "-i", pcm_audio_path,
            "-filter_complex", "showwaves=s=1080x1080:mode=line:colors=white",
            "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast",
            "-movflags", "frag_keyframe+empty_moov", "-f", "mp4", "pipe:1"
        ]
        logger.debug(f"Visualizer: {' '.join(vis_cmd)}")
        process = subprocess.Popen(vis_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

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

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # === CLEANUP: Only after streaming! ===
        for path in [downloaded_file, pcm_audio_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                    logger.debug(f"Deleted: {path}")
                except:
                    pass