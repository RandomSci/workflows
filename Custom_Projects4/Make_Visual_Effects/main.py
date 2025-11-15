from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import subprocess
import tempfile
import os
import logging
from pydantic import BaseModel
import requests
import re
import shutil

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("main")

app = FastAPI(title="Audio Visualizer Streaming API")

class AudioRequest(BaseModel):
    audio_url: str

def download_file(url: str) -> str:
    logger.debug(f"Downloading from URL: {url}")

    drive_match = re.match(r"https://drive\.google\.com/uc\?id=([a-zA-Z0-9_-]+)", url)
    if drive_match:
        file_id = drive_match.group(1)
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        logger.debug(f"Google Drive file detected, using URL: {url}")

    session = requests.Session()
    try:
        resp = session.get(url, stream=True, allow_redirects=True)
        resp.raise_for_status()

        if "text/html" in resp.headers.get("Content-Type", ""):
            confirm_match = re.search(r'confirm=([a-zA-Z0-9]+)', resp.text)
            if confirm_match:
                confirm_token = confirm_match.group(1)
                download_url = f"{url}&confirm={confirm_token}"
                logger.debug(f"Using confirm token: {confirm_token}")
                resp = session.get(download_url, stream=True)
                resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "text/html" in content_type or "octet-stream" not in content_type:
            if "googleusercontent.com" not in resp.url:
                logger.error("Downloaded HTML instead of file (likely virus scan page)")
                raise HTTPException(status_code=400, detail="Failed to download: Google Drive virus scan page detected. Use a shared link with 'anyone with link' access.")

    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=400, detail=f"Download failed: {str(e)}")

    suffix = ".webm" if "webm" in content_type else ".mp4" if "mp4" in content_type else ".bin"
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        for chunk in resp.iter_content(chunk_size=1024*1024):
            if chunk:
                tmp_file.write(chunk)
        tmp_file.close()
        logger.debug(f"File downloaded to: {tmp_file.name}")
        return tmp_file.name
    except Exception as e:
        os.unlink(tmp_file.name)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

def validate_audio_file(filepath: str) -> bool:
    """Check if file has at least one audio stream using ffprobe"""
    ffprobe_cmd = [
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=index", "-of", "csv=p=0", filepath
    ]
    try:
        result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, check=True)
        return bool(result.stdout.strip())
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        logger.error("ffprobe not found. Install ffmpeg.")
        return False

@app.post("/visualizer")
async def visualizer(request: AudioRequest):
    audio_url = request.audio_url.strip()
    if not audio_url:
        raise HTTPException(status_code=400, detail="Audio URL is required")

    tmp_file_path = None
    pcm_audio_path = None

    try:
        tmp_file_path = download_file(audio_url)

        if not validate_audio_file(tmp_file_path):
            logger.error("No audio stream found in file")
            raise HTTPException(status_code=400, detail="File has no audio stream or is corrupted.")

        pcm_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        convert_cmd = [
            "ffmpeg", "-y", 
            "-i", tmp_file_path,
            "-vn",           
            "-ac", "1",      
            "-ar", "44100", 
            "-f", "wav",
            pcm_audio_path
        ]
        logger.debug(f"Converting: {' '.join(convert_cmd)}")
        result = subprocess.run(convert_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg conversion failed: {result.stderr}")
            raise HTTPException(status_code=500, detail="Audio conversion failed")

        vis_cmd = [
            "ffmpeg", "-y",
            "-i", pcm_audio_path,
            "-filter_complex", "showwaves=s=1080x1080:mode=line:colors=white:s=1080x1080",
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-movflags", "frag_keyframe+empty_moov",
            "-f", "mp4",
            "pipe:1"
        ]

        logger.debug(f"Generating visualizer: {' '.join(vis_cmd)}")
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
                    logger.error(f"FFmpeg visualizer error: {err}")
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
        for path in [tmp_file_path, pcm_audio_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except:
                    pass