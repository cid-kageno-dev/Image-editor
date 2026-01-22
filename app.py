import os
import io
import base64
import requests
import urllib.parse
from flask import Flask, render_template, request, flash
from PIL import Image
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = "super_secret_key"

# --- CONFIGURATION ---
HF_TOKEN = os.getenv("HF_API_KEY")

# Models
MODEL_GENERATE = "black-forest-labs/FLUX.1-dev"
MODEL_EDIT = "timbrooks/instruct-pix2pix" 
POLLINATIONS_URL = "https://image.pollinations.ai/prompt/"

# Initialize Client (Safe even if token is missing, will error later)
client = InferenceClient(token=HF_TOKEN)

def process_image(pil_image):
    """Convert PIL Image to Base64"""
    buffered = io.BytesIO()
    pil_image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return img_str

def fallback_pollinations(prompt):
    """Fallback generator using Pollinations.ai"""
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"{POLLINATIONS_URL}{encoded_prompt}?nologo=true"
    response = requests.get(url)
    if response.status_code == 200:
        return Image.open(io.BytesIO(response.content))
    else:
        raise Exception(f"Pollinations Error {response.status_code}")

@app.route("/", methods=["GET", "POST"])
def index():
    generated_image = None
    prompt_text = ""
    backend_used = ""

    if request.method == "POST":
        prompt_text = request.form.get("prompt")
        action = request.form.get("action")
        
        if not prompt_text:
            flash("Please enter a prompt!", "error")
        else:
            try:
                # --- ACTION: GENERATE ---
                if action == "generate":
                    try:
                        print(f"🎨 Generating with HF ({MODEL_GENERATE})...")
                        # Primary: Hugging Face
                        image = client.text_to_image(prompt_text, model=MODEL_GENERATE)
                        generated_image = process_image(image)
                        backend_used = "Hugging Face (FLUX.1)"
                        
                    except Exception as e_hf:
                        print(f"⚠️ HF Gen Failed: {e_hf}")
                        # Fallback: Pollinations
                        try:
                            print(f"🍌 Switching to Pollinations...")
                            image = fallback_pollinations(prompt_text)
                            generated_image = process_image(image)
                            backend_used = "Pollinations.ai (Fallback)"
                            flash("Primary server busy. Used Fallback.", "info")
                        except Exception as e_poll:
                            flash(f"All generators failed. {e_poll}", "error")

                # --- ACTION: EDIT ---
                elif action == "edit":
                    uploaded_file = request.files.get("init_image")
                    if not uploaded_file or uploaded_file.filename == '':
                        flash("Upload an image to edit!", "error")
                    else:
                        try:
                            print(f"✏️ Editing with HF ({MODEL_EDIT})...")
                            input_image = Image.open(uploaded_file).convert("RGB")
                            
                            # Use Image-to-Image (InstructPix2Pix)
                            # Note: image_to_image works best for this model pipeline
                            image = client.image_to_image(
                                prompt=prompt_text,
                                image=input_image,
                                model=MODEL_EDIT,
                                guidance_scale=7.5, 
                                image_guidance_scale=1.5
                            )
                            generated_image = process_image(image)
                            backend_used = "Hugging Face (InstructPix2Pix)"
                            
                        except Exception as e_edit:
                            print(f"❌ Edit Failed: {e_edit}")
                            flash(f"Editing failed. The free server might be overloaded. Error: {e_edit}", "error")

            except Exception as e:
                flash(f"System Error: {e}", "error")

    return render_template("index.html", generated_image=generated_image, prompt=prompt_text, backend=backend_used)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
    
