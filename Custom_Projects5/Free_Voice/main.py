from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import edge_tts
import asyncio
import os
import tempfile
import uuid
from pathlib import Path

app = FastAPI(title="EchoNova TTS API", version="1.0.0")

class TTSRequest(BaseModel):
    text: str
    voice: str = "en-US-JennyNeural"
    rate: str = "+12%"

@app.get("/")
async def root():
    return {
        "service": "EchoNova TTS API",
        "status": "running",
        "version": "1.0.0",
        "available_voices": [
            "en-US-JennyNeural (Young Female - Default)",
            "en-US-AriaNeural (Female - Professional)", 
            "en-US-SaraNeural (Female - Natural)",
            "en-US-GuyNeural (Male - Friendly)",
            "en-US-DavisNeural (Male - Deep)",
            "en-US-JaneNeural (Female - Casual)"
        ],
        "example_rates": ["+0%", "+5%", "+10%", "+12%", "+15%", "+20%"]
    }

@app.post("/generate")
async def generate_tts(request: TTSRequest):
    try:
        temp_dir = "/tmp"
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_file = os.path.join(temp_dir, f"{uuid.uuid4()}.mp3")
        
        communicate = edge_tts.Communicate(
            request.text, 
            request.voice, 
            rate=request.rate
        )
        
        await communicate.save(temp_file)
        
        if not os.path.exists(temp_file):
            raise HTTPException(status_code=500, detail="Failed to generate audio")
        
        file_size = os.path.getsize(temp_file)
        
        if file_size < 1000:
            raise HTTPException(status_code=500, detail="Generated audio file too small")
        
        return FileResponse(
            temp_file, 
            media_type="audio/mpeg",
            filename="echonova_tts.mp3",
            headers={
                "Content-Length": str(file_size)
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "EchoNova TTS"
    }

@app.get("/voices")
async def list_voices():
    voices = await edge_tts.list_voices()
    english_voices = [
        {
            "name": v["ShortName"],
            "gender": v["Gender"],
            "locale": v["Locale"]
        }
        for v in voices if v["Locale"].startswith("en-")
    ]
    return {"voices": english_voices}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)