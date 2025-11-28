from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import requests
import os
import uuid
import base64

app = FastAPI()

class TrimRequest(BaseModel):
    video_url: str
    start_time: float = 0
    end_time: float = 7

@app.post("/trim")
async def trim_video(request: TrimRequest):
    video_id = None
    input_path = None
    output_path = None
    
    try:
        video_id = str(uuid.uuid4())
        input_path = f"/tmp/{video_id}_input.mp4"
        output_path = f"/tmp/{video_id}_output.mp4"
        
        print(f"Downloading video from: {request.video_url}")
        response = requests.get(request.video_url, timeout=60)
        response.raise_for_status()
        
        with open(input_path, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded video: {len(response.content)} bytes")
        
        print(f"Trimming video from {request.start_time}s to {request.end_time}s")
        result = subprocess.run([
            'ffmpeg', '-i', input_path,
            '-ss', str(request.start_time),
            '-t', str(request.end_time - request.start_time),
            '-c', 'copy',
            '-y',
            output_path
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")
            raise Exception(f"FFmpeg failed: {result.stderr}")
        
        print("Video trimmed successfully")
        
        if not os.path.exists(output_path):
            raise Exception("Output file was not created")
        
        file_size = os.path.getsize(output_path)
        print(f"Output file size: {file_size} bytes")
        
        if file_size == 0:
            raise Exception("Output file is empty")
        
        print("Uploading to 0x0.st...")
        with open(output_path, 'rb') as f:
            files = {'file': ('trimmed.mp4', f, 'video/mp4')}
            upload_response = requests.post(
                'https://0x0.st',
                files=files,
                timeout=120
            )
            upload_response.raise_for_status()
            video_url = upload_response.text.strip()
        
        print(f"Video uploaded successfully: {video_url}")
        
        return {
            "success": True,
            "video_url": video_url,
            "message": "Video trimmed and uploaded successfully"
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
            print(f"Cleaned up input file")
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
            print(f"Cleaned up output file")

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)