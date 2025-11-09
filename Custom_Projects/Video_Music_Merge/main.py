from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks
from fastapi.responses import FileResponse
import subprocess
import os
import tempfile
import uuid
from pathlib import Path
import shutil

app = FastAPI(title="Video Editor API")

def cleanup(temp_dir: Path):
    """Cleanup temp directory"""
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"🧹 Cleaned up {temp_dir}")
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")

@app.post("/combine-video-audio")
async def combine_video_audio(
    background_tasks: BackgroundTasks,
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
        
        video_content = await video.read()
        audio_content = await audio.read()
        
        print(f"✅ Video: {video.filename} - {len(video_content)} bytes")
        print(f"✅ Audio: {audio.filename} - {len(audio_content)} bytes")
        
        if video_content == audio_content:
            print("⚠️ WARNING: Video and audio files are IDENTICAL!")
            return {"error": "Video and audio files are the same. Check your n8n workflow!"}
        
        with open(video_path, "wb") as f:
            f.write(video_content)
        
        with open(audio_path, "wb") as f:
            f.write(audio_content)
        
        print(f"✅ Files saved to {temp_dir}")
        
        print("🔍 Getting video duration...")
        duration_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        duration_output = subprocess.check_output(duration_cmd).decode().strip()
        print(f"📹 Video duration: {duration_output} seconds")
        
        duration = float(duration_output)
        fade_start = max(0, duration - fade_duration)
        
        print(f"🎬 Fade will start at: {fade_start} seconds")
        
        print("⚙️ Starting FFmpeg processing...")
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path), 
            "-i", str(audio_path),
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
        
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ FFmpeg stderr: {result.stderr}")
            background_tasks.add_task(cleanup, temp_dir)
            return {"error": f"FFmpeg failed: {result.stderr}"}
        
        print("✅ FFmpeg processing complete!")
        
        if not output_path.exists():
            print("❌ Output file not created!")
            background_tasks.add_task(cleanup, temp_dir)
            return {"error": "Output file was not created"}
        
        output_size = output_path.stat().st_size
        print(f"✅ Output file size: {output_size} bytes")
        
        if output_size < 10000:  
            print("⚠️ Output file is suspiciously small!")
        
        background_tasks.add_task(cleanup, temp_dir)
        
        return FileResponse(
            output_path,
            media_type="video/mp4",
            filename="processed_video.mp4"
        )
    
    except Exception as e:
        print(f"❌ General error: {str(e)}")
        background_tasks.add_task(cleanup, temp_dir)
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