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

# Define the request body model
class AudioRequest(BaseModel):
    audio_url: str

# Function to download the audio file from the provided URL (e.g., Google Drive)
def download_file(url: str) -> str:
    logger.debug(f"Downloading audio from URL: {url}")

    # If the URL is from Google Drive, we extract the file ID
    drive_match = re.match(r"https://drive\.google\.com/uc\?id=([a-zA-Z0-9_-]+)", url)
    if drive_match:
        file_id = drive_match.group(1)
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        logger.debug(f"Detected Google Drive file, updated URL: {url}")

    try:
        resp = requests.get(url, stream=True)
        resp.raise_for_status()  # Will raise an error if the download fails
    except Exception as e:
        logger.error(f"Failed to download audio: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to download audio: {str(e)}")

    # Save the downloaded audio to a temporary file
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")  # Save as .webm to ensure we handle various formats
    for chunk in resp.iter_content(chunk_size=1024*1024):
        if chunk:
            tmp_file.write(chunk)
    tmp_file_path = tmp_file.name
    tmp_file.close()

    logger.debug(f"Audio saved to temporary file: {tmp_file_path}")
    return tmp_file_path

@app.post("/visualizer")
async def visualizer(request: AudioRequest):
    # Extract the audio URL from the request body
    audio_url = request.audio_url
    if not audio_url:
        raise HTTPException(status_code=400, detail="Audio URL is required")

    # Download the audio file
    tmp_file_path = download_file(audio_url)

    # Define the temporary file path for PCM audio
    pcm_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name

    # Define FFmpeg command to extract and convert audio to raw PCM
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", tmp_file_path,      # Input audio file (may be WebM, Opus, etc.)
        "-ac", "1",                # Mono audio channel
        "-ar", "44100",            # Audio sample rate
        "-vn",                     # No video output
        "-f", "wav",               # Convert to WAV format for visualization
        pcm_audio_path            # Output PCM WAV file
    ]

    logger.debug(f"Running FFmpeg to convert audio to PCM: {' '.join(ffmpeg_cmd)}")

    try:
        # Run the FFmpeg process
        subprocess.run(ffmpeg_cmd, check=True)
    except Exception as e:
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
        raise HTTPException(status_code=500, detail=f"Failed to convert audio to PCM: {str(e)}")

    # Now generate the visualizer video from the PCM audio
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", pcm_audio_path,                    # Input the PCM WAV file
        "-ac", "1",                               # Mono audio channel
        "-ar", "44100",                           # Audio sample rate
        "-filter_complex",                        
        "showwaves=s=1080x1080:mode=line:colors=white",  # Waveform visualization
        "-pix_fmt", "yuv420p",                    # Pixel format for video compatibility
        "-c:v", "libx264",                        # Video codec
        "-preset", "veryfast",                    # Encoding speed
        "-movflags", "frag_keyframe+empty_moov",  # Flag for smooth streaming
        "-f", "mp4",                              # Output format (MP4)
        "pipe:1"                                  # Output to stdout (streaming)
    ]

    logger.debug(f"Running FFmpeg command to generate visualizer: {' '.join(ffmpeg_cmd)}")

    try:
        # Run the FFmpeg process for video generation
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except Exception as e:
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
        if os.path.exists(pcm_audio_path):
            os.remove(pcm_audio_path)
        raise HTTPException(status_code=500, detail=f"Failed to start visualizer: {str(e)}")

    # Function to stream the video chunks back to the client
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
                os.remove(tmp_file_path)  # Clean up the temporary files
            if os.path.exists(pcm_audio_path):
                os.remove(pcm_audio_path)
            logger.debug("Temporary audio file removed.")

    # Return the streaming video as a response
    return StreamingResponse(
        iter_video(),
        media_type="video/mp4",  # Video format
        headers={"Content-Disposition": 'attachment; filename="visualizer.mp4"'}
    )
