import os
import io
import base64
import requests
import urllib.parse
from flask import Flask, render_template, request, flash
from PIL import Image
from dotenv import load_dotenv

load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = "super_secret_key"

# --- CONFIGURATION ---
# 1. Primary: Hugging Face (High Quality, Rate Limited)
HF_API_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-dev"
HF_API_KEY = os.getenv("HF_API_KEY")

# 2. Fallback: Pollinations.ai (Free, Unlimited, No Key)
POLLINATIONS_URL = "https://image.pollinations.ai/prompt/"

def process_image(image_bytes):
    """Helper to convert bytes to base64 for HTML display"""
    return base64.b64encode(image_bytes).decode("utf-8")

def query_huggingface(prompt):
    """Attempts to generate using Hugging Face"""
    if not HF_API_KEY:
        raise Exception("HF_API_KEY missing")
    
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": prompt}
    response = requests.post(HF_API_URL, headers=headers, json=payload)
    
    # If HF returns an error (like 503 loading or 429 rate limit), raise exception to trigger fallback
    if response.status_code != 200:
        raise Exception(f"HF Status {response.status_code}: {response.text}")
        
    return response.content

def query_pollinations(prompt):
    """Fallback generator using Pollinations.ai"""
    # Safe URL encoding for the prompt
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"{POLLINATIONS_URL}{encoded_prompt}?nologo=true"
    
    response = requests.get(url)
    if response.status_code == 200:
        return response.content
    else:
        raise Exception(f"Pollinations Status {response.status_code}")

@app.route("/", methods=["GET", "POST"])
def index():
    generated_image = None
    prompt_text = ""
    backend_used = ""

    if request.method == "POST":
        prompt_text = request.form.get("prompt")
        
        if not prompt_text:
            flash("Please enter a prompt!", "error")
        else:
            # --- ATTEMPT 1: PRIMARY (Hugging Face) ---
            try:
                print(f"🚀 Trying Primary (Hugging Face) for: {prompt_text}")
                image_bytes = query_huggingface(prompt_text)
                
                # Verify it's a real image
                Image.open(io.BytesIO(image_bytes)) 
                generated_image = process_image(image_bytes)
                backend_used = "Hugging Face (FLUX.1)"
                
            except Exception as e_primary:
                print(f"⚠️ Primary Failed: {e_primary}")
                
                # --- ATTEMPT 2: FALLBACK (Pollinations) ---
                try:
                    print(f"🍌 Switching to Fallback (Pollinations)...")
                    image_bytes = query_pollinations(prompt_text)
                    
                    # Verify it's a real image
                    Image.open(io.BytesIO(image_bytes))
                    generated_image = process_image(image_bytes)
                    backend_used = "Pollinations.ai (Fallback)"
                    flash(f"Primary server busy. Generated using {backend_used}.", "info")
                    
                except Exception as e_fallback:
                    print(f"❌ Fallback Failed: {e_fallback}")
                    flash(f"All generators failed. HF Error: {e_primary} | Fallback Error: {e_fallback}", "error")

    return render_template("index.html", generated_image=generated_image, prompt=prompt_text, backend=backend_used)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
    
