from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import requests
import os
import uuid

app = FastAPI()

class TrimRequest(BaseModel):
    video_url: str
    start_time: float = 0
    end_time: float = 7

@app.post("/trim")
async def trim_video(request: TrimRequest):
    try:
        video_id = str(uuid.uuid4())
        input_path = f"/tmp/{video_id}_input.mp4"
        output_path = f"/tmp/{video_id}_output.mp4"
        
        response = requests.get(request.video_url, timeout=30)
        response.raise_for_status()
        with open(input_path, 'wb') as f:
            f.write(response.content)
        
        subprocess.run([
            'ffmpeg', '-i', input_path,
            '-ss', str(request.start_time),
            '-t', str(request.end_time - request.start_time),
            '-c', 'copy',
            output_path
        ], check=True, capture_output=True)
        
        with open(output_path, 'rb') as f:
            files = {'file': f}
            upload_response = requests.post('https://file.io', files=files)
            upload_data = upload_response.json()
        
        os.remove(input_path)
        os.remove(output_path)
        
        return {
            "success": True,
            "video_url": upload_data['link'],
            "message": "Video trimmed and uploaded successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)