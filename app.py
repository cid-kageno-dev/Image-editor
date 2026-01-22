import os
import io
import base64
import time
import random
import sys

# --- SAFETY CHECK: IMPORT LIBRARIES ---
try:
    import requests
    from flask import Flask, render_template, request, flash
    # We need Image, PIL.Image class itself, and resampling for high quality resizing
    from PIL import Image, ImageDraw, ImageFont
    from dotenv import load_dotenv
    from huggingface_hub import InferenceClient
except ImportError as e:
    print(f"❌ CRITICAL ERROR: Missing library. {e}")
    print("👉 Did you update requirements.txt? You need: flask, requests, pillow, huggingface_hub, python-dotenv")
    sys.exit(1)

load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = "super_secret_key"

# --- CONFIGURATION ---
MODEL_GENERATE = "black-forest-labs/FLUX.1-dev"
MODEL_EDIT = "timbrooks/instruct-pix2pix"
POLLINATIONS_URL = "https://image.pollinations.ai/prompt/"
HF_API_URL = f"https://router.huggingface.co/hf-inference/models/{MODEL_GENERATE}"

# --- NEW FUNCTION: ADD IMAGE LOGO WATERMARK ---
def add_watermark_to_image(pil_image):
    """Adds a transparent logo image to the bottom right corner."""
    # 1. Convert base image to RGBA for alpha compositing
    pil_image = pil_image.convert("RGBA")
    base_width, base_height = pil_image.size

    # 2. Find path to the logo in the 'static' folder
    logo_path = os.path.join(app.root_path, 'static', 'watermark_logo.png')
    
    try:
        # Load logo and ensure it's RGBA
        logo = Image.open(logo_path).convert("RGBA")
    except FileNotFoundError:
        print(f"⚠️ Warning: Logo not found at {logo_path}. Returning non-watermarked image.")
        return pil_image

    # 3. Resize logo dynamically
    # We want the logo to be about 12% of the image's total height
    target_height = int(base_height * 0.12)
    # Ensure it doesn't get too tiny on small images
    target_height = max(target_height, 30) 
    
    # Calculate width to maintain aspect ratio
    aspect_ratio = logo.width / logo.height
    target_width = int(target_height * aspect_ratio)
    
    # Perform high-quality resize
    logo = logo.resize((target_width, target_height), Image.Resampling.LANCZOS)

    # 4. Calculate Position (Bottom Right with 2% padding)
    padding = int(base_height * 0.02)
    x = base_width - logo.width - padding
    y = base_height - logo.height - padding

    # 5. Paste the logo
    # Using the logo itself as the 'mask' ensures transparent areas remain transparent
    pil_image.paste(logo, (x, y), mask=logo)

    return pil_image

# --- EXISTING HELPER FUNCTIONS ---
def get_random_hf_key():
    all_keys = []
    for env_var_name, value in os.environ.items():
        if env_var_name.startswith("HF_API_KEY"):
            if value and value.strip():
                all_keys.append(value.strip())
    
    if not all_keys:
        return None
    return random.choice(all_keys)

def process_image(pil_image):
    buffered = io.BytesIO()
    pil_image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return img_str

def fallback_pollinations(prompt):
    import urllib.parse
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"{POLLINATIONS_URL}{encoded_prompt}?nologo=true"
    response = requests.get(url)
    if response.status_code == 200:
        return Image.open(io.BytesIO(response.content))
    else:
        raise Exception(f"Pollinations Error {response.status_code}")

def query_huggingface_with_retry(prompt):
    for i in range(3):
        current_key = get_random_hf_key()
        if not current_key:
            raise Exception("MISSING_KEYS")

        headers = {"Authorization": f"Bearer {current_key}"}
        payload = {"inputs": prompt}
        
        try:
            print(f"🔄 Attempt {i+1}/3 with key ...{current_key[-4:]}")
            response = requests.post(HF_API_URL, headers=headers, json=payload)
            
            if response.status_code == 200:
                return response.content
            elif response.status_code == 503:
                time.sleep(5)
                continue
            elif response.status_code == 429:
                print("⚠️ Rate limit. Switching keys...")
                continue
            else:
                print(f"⚠️ HF Error: {response.text}")
        except Exception as e:
            print(f"Connection Error: {e}")
            
    raise Exception("All retries failed.")

# --- MAIN ROUTE ---
@app.route("/", methods=["GET", "POST"])
def index():
    generated_image = None
    prompt_text = ""
    backend_used = ""

    try:
        if request.method == "POST":
            prompt_text = request.form.get("prompt")
            action = request.form.get("action")
            
            if not prompt_text:
                flash("Please enter a prompt!", "error")
            else:
                # --- ACTION: GENERATE ---
                if action == "generate":
                    try:
                        image_bytes = query_huggingface_with_retry(prompt_text)
                        image = Image.open(io.BytesIO(image_bytes))
                        
                        # 👉 ADD LOGO WATERMARK
                        image = add_watermark_to_image(image)
                        
                        generated_image = process_image(image)
                        backend_used = "Hugging Face (FLUX.1)"
                        
                    except Exception as e:
                        if "MISSING_KEYS" in str(e):
                            flash("❌ No API Keys found! Add HF_API_KEY to Environment.", "error")
                        else:
                            # Try Fallback
                            try:
                                print("🍌 Switching to Pollinations...")
                                image = fallback_pollinations(prompt_text)

                                # 👉 ADD LOGO WATERMARK TO FALLBACK
                                image = add_watermark_to_image(image)

                                generated_image = process_image(image)
                                backend_used = "Pollinations.ai (Fallback)"
                                flash("Primary busy. Used Fallback.", "info")
                            except Exception as e_poll:
                                flash(f"Failed. Error: {e_poll}", "error")

                # --- ACTION: EDIT ---
                elif action == "edit":
                    uploaded_file = request.files.get("init_image")
                    if not uploaded_file:
                        flash("Upload an image!", "error")
                    else:
                        current_key = get_random_hf_key()
                        if not current_key:
                             flash("❌ Editing requires an API Key.", "error")
                        else:
                            client = InferenceClient(token=current_key)
                            input_image = Image.open(uploaded_file).convert("RGB")
                            
                            image = client.image_to_image(
                                prompt=prompt_text, 
                                image=input_image, 
                                model=MODEL_EDIT,
                                guidance_scale=7.5, image_guidance_scale=1.5
                            )

                            # 👉 ADD LOGO WATERMARK TO EDIT
                            image = add_watermark_to_image(image)

                            generated_image = process_image(image)
                            backend_used = "Hugging Face (InstructPix2Pix)"

    except Exception as e:
        print(f"CRITICAL APP CRASH AVOIDED: {e}")
        flash(f"System Error: {str(e)}", "error")

    return render_template("index.html", generated_image=generated_image, prompt=prompt_text, backend=backend_used)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
    
