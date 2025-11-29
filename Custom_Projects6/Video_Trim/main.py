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
    fade_duration: float = 0.5  

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
        response = requests.get(request.video_url, timeout=120)  
        response.raise_for_status()
        
        with open(input_path, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded: {len(response.content)} bytes")
        
        print(f"Trimming: {request.start_time}s to {request.end_time}s with {request.fade_duration}s fade")
        
        fade_start = request.end_time - request.start_time - request.fade_duration
        
        result = subprocess.run([
            'ffmpeg', '-i', input_path,
            '-ss', str(request.start_time),
            '-t', str(request.end_time - request.start_time),
            '-vf', f'fade=t=out:st={fade_start}:d={request.fade_duration}',
            '-af', f'afade=t=out:st={fade_start}:d={request.fade_duration}', 
            '-c:v', 'libx264',
            '-c:a', 'aac',      
            '-preset', 'ultrafast',
            '-y',
            output_path
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            raise Exception(f"FFmpeg failed: {result.stderr}")
        
        if not os.path.exists(output_path):
            raise Exception("Output file not created")
        
        file_size = os.path.getsize(output_path)
        print(f"Trimmed with fade: {file_size} bytes")
        
        # Upload to tmpfiles.org with 300s timeout
        print("Uploading to tmpfiles.org...")
        with open(output_path, 'rb') as f:
            files = {'file': ('video.mp4', f, 'video/mp4')}
            upload_response = requests.post(
                'https://tmpfiles.org/api/v1/upload',
                files=files,
                timeout=300  
            )
            upload_response.raise_for_status()
        
        upload_data = upload_response.json()
        print(f"Upload response: {upload_data}")
        
        # tmpfiles.org returns: {"status": "success", "data": {"url": "https://tmpfiles.org/xxxxx"}}
        # We need to change tmpfiles.org/xxxxx to tmpfiles.org/dl/xxxxx for direct download
        if upload_data.get('status') == 'success':
            original_url = upload_data['data']['url']
            # Convert: https://tmpfiles.org/xxxxx → https://tmpfiles.org/dl/xxxxx
            file_url = original_url.replace('tmpfiles.org/', 'tmpfiles.org/dl/')
            print(f"Uploaded successfully: {file_url}")
            
            return {
                "success": True,
                "video_url": file_url,
                "message": "Video trimmed with smooth fade and uploaded successfully"
            }
        else:
            raise Exception(f"Upload failed: {upload_data}")
        
    except requests.exceptions.Timeout as e:
        print(f"Timeout error: {str(e)}")
        raise HTTPException(status_code=504, detail=f"Request timed out: {str(e)}")
    except requests.exceptions.RequestException as e:
        print(f"Request error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
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

@app.get("/")
async def root():
    return {
        "status": "Video trim service running",
        "version": "2.0",
        "timeout": "300s upload, 120s download"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)  
