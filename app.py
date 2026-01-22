import os
import io
import base64
import requests
import urllib.parse
import time
import random
from flask import Flask, render_template, request, flash
from PIL import Image
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = "super_secret_key"

# --- CONFIGURATION ---
# 1. Models
MODEL_GENERATE = "black-forest-labs/FLUX.1-dev"
MODEL_EDIT = "timbrooks/instruct-pix2pix"
POLLINATIONS_URL = "https://image.pollinations.ai/prompt/"

# 2. Hugging Face API URL (Router)
HF_API_URL = f"https://router.huggingface.co/hf-inference/models/{MODEL_GENERATE}"

def get_random_hf_key():
    """
    Automatically finds ALL environment variables starting with 'HF_API_KEY'
    (e.g., HF_API_KEY1, HF_API_KEY2, HF_API_KEY_BACKUP) and picks one at random.
    """
    all_keys = []
    
    # Scan all environment variables
    for env_var_name, value in os.environ.items():
        if env_var_name.startswith("HF_API_KEY"):
            # Only add if the value is not empty
            if value and value.strip():
                all_keys.append(value.strip())
    
    if not all_keys:
        return None
    
    # Pick a random key from the list
    selected_key = random.choice(all_keys)
    return selected_key

def process_image(pil_image):
    """Convert PIL Image to Base64 for HTML"""
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

def query_huggingface_with_retry(prompt):
    """
    Attempts to generate using Hugging Face with:
    1. Key Rotation (Pick random key per try)
    2. Smart Retry (Wait if model is loading)
    """
    # Try up to 3 times
    for i in range(3):
        # 1. Get a fresh key for this attempt
        current_key = get_random_hf_key()
        if not current_key:
            raise Exception("No HF_API_KEYs found in .env file.")

        headers = {"Authorization": f"Bearer {current_key}"}
        payload = {"inputs": prompt}
        
        try:
            print(f"🔄 Attempt {i+1}/3 using key ending in ...{current_key[-4:]}")
            response = requests.post(HF_API_URL, headers=headers, json=payload)
            
            # SUCCESS
            if response.status_code == 200:
                return response.content
            
            # MODEL LOADING (Wait and retry)
            elif response.status_code == 503:
                print(f"💤 Model loading... Waiting 5s...")
                time.sleep(5)
                continue
                
            # RATE LIMIT (Just continue, loop will pick a new key next time!)
            elif response.status_code == 429:
                print(f"⚠️ Rate limit (429) on this key. Switching keys...")
                continue
                
            else:
                print(f"⚠️ HF Error {response.status_code}: {response.text}")

        except Exception as e:
            print(f"Connection Error: {e}")
            
    raise Exception("Max retries reached. All keys busy or models down.")

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
                        # Use our new Retry+Rotation function
                        image_bytes = query_huggingface_with_retry(prompt_text)
                        
                        # Verify Image
                        image = Image.open(io.BytesIO(image_bytes))
                        generated_image = process_image(image)
                        backend_used = "Hugging Face (FLUX.1)"
                        
                    except Exception as e_hf:
                        print(f"⚠️ Primary Failed: {e_hf}")
                        
                        # Fallback: Pollinations
                        try:
                            print(f"🍌 Switching to Fallback (Pollinations)...")
                            image = fallback_pollinations(prompt_text)
                            generated_image = process_image(image)
                            backend_used = "Pollinations.ai (Fallback)"
                            flash(f"Primary busy. Used Fallback.", "info")
                        except Exception as e_poll:
                            flash(f"All generators failed. Error: {e_poll}", "error")

                # --- ACTION: EDIT ---
                elif action == "edit":
                    uploaded_file = request.files.get("init_image")
                    if not uploaded_file or uploaded_file.filename == '':
                        flash("Upload an image to edit!", "error")
                    else:
                        try:
                            print(f"✏️ Editing with HF ({MODEL_EDIT})...")
                            
                            # 1. Pick a random key for the editor too!
                            current_key = get_random_hf_key()
                            if not current_key:
                                raise Exception("No HF_API_KEYs found.")
                                
                            print(f"🔑 Using key ending in ...{current_key[-4:]}")
                            
                            # 2. Initialize Client with that specific key
                            client = InferenceClient(token=current_key)
                            
                            input_image = Image.open(uploaded_file).convert("RGB")
                            
                            # 3. Call API
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
                            flash(f"Edit failed (Try again, free tier is busy): {e_edit}", "error")

            except Exception as e:
                flash(f"System Error: {e}", "error")

    return render_template("index.html", generated_image=generated_image, prompt=prompt_text, backend=backend_used)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
    
