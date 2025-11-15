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

    # Normalize Google Drive URL
    drive_match = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if not drive_match:
        raise HTTPException(status_code=400, detail="Invalid Google Drive URL")
    
    file_id = drive_match.group(1)
    direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    logger.debug(f"Using direct download URL: {direct_url}")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })

    try:
        # Step 1: Get the file page (to get cookies + confirm token)
        response = session.get(direct_url, stream=True, allow_redirects=True)
        response.raise_for_status()

        # Check if it's the virus scan page
        if "text/html" in response.headers.get("Content-Type", ""):
            logger.debug("Virus scan page detected. Extracting confirm token...")
            confirm_match = re.search(r'confirm=([0-9A-Za-z_]+)', response.text)
            if not confirm_match:
                raise HTTPException(status_code=400, detail="Virus scan page detected but no confirm token found.")
            
            confirm_token = confirm_match.group(1)
            download_url = f"{direct_url}&confirm={confirm_token}"
            logger.debug(f"Using confirm token: {confirm_token}")

            # Step 2: Download with confirm token
            response = session.get(download_url, stream=True)
            response.raise_for_status()

            # Final check: still HTML?
            if "text/html" in response.headers.get("Content-Type", ""):
                raise HTTPException(status_code=400, detail="Failed to bypass virus scan. Try downloading the file in browser first.")

        # Final content type
        content_type = response.headers.get("Content-Type", "")
        if "octet-stream" not in content_type and "audio" not in content_type and "video" not in content_type:
            logger.warning(f"Unexpected content-type: {content_type}")

    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=400, detail=f"Download failed: {str(e)}")

    # Save to temp file
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
        logger.debug(f"File downloaded: {tmp_file.name} ({os.path.getsize(tmp_file.name)} bytes)")
        return tmp_file.name
    except Exception as e:
        if os.path.exists(tmp_file.name):
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