from http.server import BaseHTTPRequestHandler
import json
import edge_tts
import asyncio
import io

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        body = json.loads(post_data)
        
        text = body.get("text", "")
        voice = body.get("voice", "en-US-JennyNeural")
        rate = body.get("rate", "+12%")
        
        async def generate():
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            audio_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]
            return audio_bytes
        
        audio = asyncio.run(generate())
        
        self.send_response(200)
        self.send_header('Content-Type', 'audio/mpeg')
        self.send_header('Content-Length', str(len(audio)))
        self.end_headers()
        self.wfile.write(audio)
        
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = {"service": "EchoNova TTS", "status": "running"}
        self.wfile.write(json.dumps(response).encode())