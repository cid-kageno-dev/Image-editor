import os
import io
import base64
import requests
from flask import Flask, render_template, request, flash
from PIL import Image
from dotenv import load_dotenv

load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = "super_secret_key"

# --- CONFIGURATION ---
# UPDATED URL: Using the new 'router' domain required by Hugging Face
API_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-dev"
HF_API_KEY = os.getenv("HF_API_KEY")

def query_huggingface(prompt):
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": prompt}
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.content

def process_image(image_bytes):
    return base64.b64encode(image_bytes).decode("utf-8")

@app.route("/", methods=["GET", "POST"])
def index():
    generated_image = None
    prompt_text = ""

    if request.method == "POST":
        prompt_text = request.form.get("prompt")
        
        if not HF_API_KEY:
            flash("Error: HF_API_KEY is missing in .env", "error")
        elif not prompt_text:
            flash("Please enter a prompt!", "error")
        else:
            try:
                print(f"🎨 Generating: {prompt_text}")
                image_bytes = query_huggingface(prompt_text)
                
                # Check if we got a valid image back
                try:
                    Image.open(io.BytesIO(image_bytes)) 
                    generated_image = process_image(image_bytes)
                except Exception:
                    # If PIL fails, it's likely an error message from the API
                    error_json = image_bytes.decode('utf-8')
                    flash(f"API Error: {error_json}", "error")
                    
            except Exception as e:
                flash(f"System Error: {str(e)}", "error")

    return render_template("index.html", generated_image=generated_image, prompt=prompt_text)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
    
