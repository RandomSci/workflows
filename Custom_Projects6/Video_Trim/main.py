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
    try:
        # Fixed indentation here!
        video_id = str(uuid.uuid4())
        input_path = f"/tmp/{video_id}_input.mp4"
        output_path = f"/tmp/{video_id}_output.mp4"
        
        # Download video
        response = requests.get(request.video_url, timeout=30)
        response.raise_for_status()
        with open(input_path, 'wb') as f:
            f.write(response.content)
        
        # Trim with ffmpeg
        subprocess.run([
            'ffmpeg', '-i', input_path,
            '-ss', str(request.start_time),
            '-t', str(request.end_time - request.start_time),
            '-c', 'copy',
            output_path
        ], check=True, capture_output=True)
        
        # Read trimmed video
        with open(output_path, 'rb') as f:
            trimmed_data = f.read()
        
        # Clean up
        os.remove(input_path)
        os.remove(output_path)
        
        # Return base64
        video_base64 = base64.b64encode(trimmed_data).decode('utf-8')
        
        return {
            "success": True,
            "video_base64": video_base64,
            "message": "Video trimmed successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)