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
        
        print(f"Downloading: {request.video_url}")
        response = requests.get(request.video_url, timeout=60)
        response.raise_for_status()
        
        with open(input_path, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded: {len(response.content)} bytes")
        
        print(f"Trimming: {request.start_time}s to {request.end_time}s")
        result = subprocess.run([
            'ffmpeg', '-i', input_path,
            '-ss', str(request.start_time),
            '-t', str(request.end_time - request.start_time),
            '-c', 'copy',
            '-y',
            output_path
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            raise Exception(f"FFmpeg failed: {result.stderr}")
        
        if not os.path.exists(output_path):
            raise Exception("Output file not created")
        
        file_size = os.path.getsize(output_path)
        print(f"Trimmed: {file_size} bytes")
        
        with open(output_path, 'rb') as f:
            video_data = f.read()
            video_base64 = base64.b64encode(video_data).decode('utf-8')
            data_uri = f"data:video/mp4;base64,{video_base64}"
        
        print(f"Returning base64 ({len(video_base64)} chars)")
        
        return {
            "success": True,
            "video_url": data_uri,  
            "message": "Video trimmed successfully"
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        if output_path and os.path.exists(output_path):
            os.remove(output_path)

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)