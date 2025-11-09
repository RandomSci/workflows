from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import FileResponse
import subprocess
import os
import tempfile
import uuid
from pathlib import Path
import shutil

app = FastAPI(title="Video Editor API")

@app.post("/combine-video-audio")
async def combine_video_audio(
    video: UploadFile = File(...),
    audio: UploadFile = File(...),
    audio_volume: float = Form(0.15),
    fade_duration: float = Form(1.0)
):
    """
    Combines video with background music, adds fade out transition
    """
    job_id = str(uuid.uuid4())
    temp_dir = Path(tempfile.gettempdir()) / job_id
    temp_dir.mkdir(exist_ok=True)
    
    try:
        video_path = temp_dir / "input_video.mp4"
        audio_path = temp_dir / "background_music.mp3"
        output_path = temp_dir / "output_video.mp4"
        
        with open(video_path, "wb") as f:
            f.write(await video.read())
        
        with open(audio_path, "wb") as f:
            f.write(await audio.read())
        
        duration_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        duration = float(subprocess.check_output(duration_cmd).decode().strip())
        fade_start = max(0, duration - fade_duration)
        
        ffmpeg_cmd = [
            "ffmpeg", "-i", str(video_path), "-i", str(audio_path),
            "-filter_complex",
            f"[0:v]fade=t=out:st={fade_start}:d={fade_duration}[v];"
            f"[0:a]afade=t=out:st={fade_start}:d={fade_duration}[a0];"
            f"[1:a]volume={audio_volume},afade=t=out:st={fade_start}:d={fade_duration}[a1];"
            f"[a0][a1]amix=inputs=2:duration=first[aout]",
            "-map", "[v]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(output_path)
        ]
        
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
        
        return FileResponse(
            output_path,
            media_type="video/mp4",
            filename="processed_video.mp4",
            background=lambda: shutil.rmtree(temp_dir, ignore_errors=True)
        )
    
    except subprocess.CalledProcessError as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return {"error": f"FFmpeg error: {e.stderr.decode()}"}
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return {"error": str(e)}

@app.get("/health")
async def health():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        ffmpeg_status = "installed"
    except:
        ffmpeg_status = "not found"
    
    return {
        "status": "healthy",
        "ffmpeg": ffmpeg_status
    }

@app.get("/")
async def root():
    return {
        "message": "Video Editor API - Money Tree to Money Forest 🌳💰",
        "endpoints": {
            "/combine-video-audio": "POST - Combine video with background music + fade",
            "/health": "GET - Health check"
        }
    }