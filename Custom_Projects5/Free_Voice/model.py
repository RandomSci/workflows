import urllib.request
import os

def download_file(url, filename):
    print(f"📥 Downloading {filename}...")
    urllib.request.urlretrieve(url, filename)
    print(f"✅ Downloaded: {filename}")

base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/kristin/medium/"

files = [
    ("en_US-kristin-medium.onnx", base_url + "en_US-kristin-medium.onnx"),
    ("en_US-kristin-medium.onnx.json", base_url + "en_US-kristin-medium.onnx.json")
]

print("🎙️ Downloading Kristin voice (young female, natural)...\n")

for filename, url in files:
    download_file(url, filename)

print("\n✅ Kristin voice downloaded!")
print("🎤 This is a younger-sounding female voice, much better for drama content")