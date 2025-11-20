from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import edge_tts
import asyncio
import os
import tempfile
import uuid
import time
import random

app = FastAPI(title="EchoNova TTS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TTSRequest(BaseModel):
    text: str
    voice: str = "en-US-JennyNeural"
    rate: str = "+12%"

# Voice rotation to avoid pattern detection
VOICE_ALTERNATES = [
    "en-US-JennyNeural",
    "en-US-AriaNeural", 
    "en-US-SaraNeural",
]

@app.get("/")
async def root():
    return {
        "service": "EchoNova TTS API",
        "status": "running",
        "version": "2.0.0"
    }

@app.post("/generate")
async def generate_tts(request: TTSRequest):
    max_retries = 5
    base_delay = 3
    
    for attempt in range(max_retries):
        try:
            temp_dir = "/tmp"
            os.makedirs(temp_dir, exist_ok=True)
            
            temp_file = os.path.join(temp_dir, f"{uuid.uuid4()}.mp3")
            
            # Use requested voice, but rotate on retry
            voice_to_use = request.voice
            if attempt > 0:
                voice_to_use = random.choice(VOICE_ALTERNATES)
            
            # Add random delay to seem more human (0-2 seconds)
            human_delay = random.uniform(0, 2)
            await asyncio.sleep(human_delay)
            
            communicate = edge_tts.Communicate(
                request.text, 
                voice_to_use, 
                rate=request.rate,
                # Proxy settings can be added here if needed later
            )
            
            await communicate.save(temp_file)
            
            if not os.path.exists(temp_file):
                raise Exception("File not created")
                
            file_size = os.path.getsize(temp_file)
            
            if file_size < 1000:
                raise Exception("File too small")
            
            return FileResponse(
                temp_file, 
                media_type="audio/mpeg",
                filename="tts.mp3"
            )
            
        except Exception as e:
            if attempt < max_retries - 1:
                # Exponential backoff with jitter
                retry_delay = base_delay * (2 ** attempt) + random.uniform(0, 3)
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                print(f"Retrying in {retry_delay:.1f} seconds...")
                await asyncio.sleep(retry_delay)
                continue
            else:
                raise HTTPException(
                    status_code=500, 
                    detail=f"TTS generation failed after {max_retries} attempts: {str(e)}"
                )

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)