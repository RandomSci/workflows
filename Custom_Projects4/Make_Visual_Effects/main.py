from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
import subprocess
import tempfile
import logging
import io

app = FastAPI(title="Audio Visualizer Streaming API")

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("main")

@app.post("/visualizer")
async def visualizer(file: UploadFile = File(...)):
    logger.debug(f"Received file: {file.filename}")

    # Read binary data from file
    file_data = await file.read()
    logger.debug(f"Received {len(file_data)} bytes of audio data")

    # Write it to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_audio_file:
        tmp_audio_file.write(file_data)
        tmp_audio_path = tmp_audio_file.name

    try:
        # Validate audio file
        if not validate_audio_file(tmp_audio_path):
            raise HTTPException(status_code=400, detail="No audio stream found")

        # Generate video using FFmpeg
        vis_cmd = [
            "ffmpeg", "-y", "-i", tmp_audio_path,
            "-filter_complex", "[0:a]showwaves=s=640x360:mode=line:colors=white[col];[col]format=yuv420p[out]",
            "-map", "[out]", "-c:v", "libx264", "-preset", "ultrafast",
            "-movflags", "frag_keyframe+empty_moov", "-f", "mp4", "pipe:1"
        ]
        
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
                try:
                    os.remove(tmp_audio_path)
                except Exception as e:
                    logger.error(f"Error cleaning up temp file: {e}")

        return StreamingResponse(
            video_stream(),
            media_type="video/mp4",
            headers={"Content-Disposition": 'attachment; filename="visualizer.mp4"'}
        )
    except Exception as e:
        logger.error(f"Error generating visualizer: {e}")
        raise HTTPException(status_code=500, detail="Error generating visualizer")

def validate_audio_file(filepath: str) -> bool:
    # Validate audio file using ffprobe (for audio stream presence)
    cmd = ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", filepath]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return bool(result.stdout.strip())
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return False
