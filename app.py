import os
import io
import base64
import time
import random
import sys
import urllib.parse
import socket
from io import BytesIO

# --- SAFETY CHECK: IMPORT LIBRARIES ---
try:
    import requests
    # Check for SOCKS support
    try:
        import socks
    except ImportError:
        print("❌ CRITICAL ERROR: 'pysocks' is missing. pip install pysocks")
        sys.exit(1)

    from flask import Flask, render_template, request, flash
    from PIL import Image, ImageDraw, ImageFont
    from dotenv import load_dotenv
    from huggingface_hub import InferenceClient
    from stem import Signal
    from stem.control import Controller
except ImportError as e:
    print(f"❌ CRITICAL ERROR: Missing library. {e}")
    sys.exit(1)

load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_nano_banana_key")

# --- CONFIGURATION ---
MODEL_GENERATE = "black-forest-labs/FLUX.1-dev"
MODEL_EDIT = "timbrooks/instruct-pix2pix"
HF_API_URL = f"https://router.huggingface.co/hf-inference/models/{MODEL_GENERATE}"

# --- TOR CONFIGURATION (AUTO-DETECT) ---
def get_tor_ports():
    """Detects if Tor is running on port 9050 (Service) or 9150 (Browser)."""
    # On Render, we explicitly start it on 9050 in start.sh, so we prioritize that.
    for port in [9050, 9150]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) == 0:
                print(f"✅ Tor detected on port {port}")
                return port, port + 1
    return None, None

TOR_PROXY_PORT, TOR_CONTROL_PORT = get_tor_ports()

if TOR_PROXY_PORT:
    TOR_PROXY = {
        'http': f'socks5h://127.0.0.1:{TOR_PROXY_PORT}',
        'https': f'socks5h://127.0.0.1:{TOR_PROXY_PORT}'
    }
else:
    print("⚠️ WARNING: Tor not detected. Fallback mode will fail.")
    TOR_PROXY = None

TOR_CONTROL_PASSWORD = None 

# --- HELPER: RENEW TOR IP ---
def renew_tor_ip():
    """Signal Tor for a NEWNYM (new circuit/exit IP)."""
    if not TOR_CONTROL_PORT:
        return

    try:
        with Controller.from_port(port=TOR_CONTROL_PORT) as controller:
            controller.authenticate()  # Cookie authentication
            controller.signal(Signal.NEWNYM)
            # Reduced sleep time for speed
            time.sleep(0.5) 
            print(f"🔥 Tor IP Rotated")
    except Exception as e:
        print(f"⚠️ Tor Control Error: {e}. continuing with current IP...")

# --- HELPER: IMAGE PROCESSING ---
def process_image(pil_image):
    buffered = io.BytesIO()
    pil_image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def add_watermark_to_image(pil_image):
    try:
        pil_image = pil_image.convert("RGBA")
        base_width, base_height = pil_image.size
        logo_path = os.path.join(app.root_path, 'static', 'watermark_logo.png')
        
        logo = Image.open(logo_path).convert("RGBA")

        target_height = max(int(base_height * 0.12), 30)
        aspect_ratio = logo.width / logo.height
        target_width = int(target_height * aspect_ratio)
        
        logo = logo.resize((target_width, target_height), Image.Resampling.LANCZOS)

        padding = int(base_height * 0.02)
        x = base_width - logo.width - padding
        y = base_height - logo.height - padding

        pil_image.paste(logo, (x, y), mask=logo)
        return pil_image
    except Exception:
        return pil_image 

def get_random_hf_key():
    all_keys = [v for k, v in os.environ.items() if k.startswith("HF_API_KEY") and v.strip()]
    return random.choice(all_keys) if all_keys else None

# --- BACKEND 1: HUGGING FACE ---
def query_huggingface_with_retry(prompt):
    for i in range(3):
        current_key = get_random_hf_key()
        if not current_key: raise Exception("MISSING_KEYS")

        headers = {"Authorization": f"Bearer {current_key}"}
        try:
            print(f"🔄 HF Attempt {i+1}/3...")
            response = requests.post(HF_API_URL, headers=headers, json={"inputs": prompt}, timeout=45)
            
            if response.status_code == 200: return response.content
            elif response.status_code == 503: 
                time.sleep(1) # Fast retry
                continue
            elif response.status_code == 429: continue
        except Exception as e:
            print(f"❌ HF Conn Error: {e}")
            
    raise Exception("HF_FAILED")

# --- BACKEND 2: POLLINATIONS (TOR FALLBACK) ---
def fallback_pollinations(prompt):
    if not TOR_PROXY: raise Exception("Tor not found")
    
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?nologo=true&private=true&safe=false"

    for attempt in range(5):
        renew_tor_ip()
        try:
            print(f"🍆 Pollinations (Tor) Attempt {attempt+1}...")
            # increased timeout for Tor latency
            response = requests.get(url, proxies=TOR_PROXY, timeout=45) 

            if response.status_code == 200:
                if len(response.content) < 4000: 
                    # Fast retry for fake images
                    time.sleep(0.5)
                    continue
                return Image.open(BytesIO(response.content))
        except Exception as e:
            print(f"❌ Tor Error: {e}")
        
        # Fast retry sleep
        time.sleep(0.5) 

    raise Exception("POLLINATIONS_FAILED")

# --- ROUTES ---
@app.route("/", methods=["GET", "POST"])
def index():
    generated_image = None
    prompt_text = ""
    backend_used = ""

    if request.method == "POST":
        prompt_text = request.form.get("prompt")
        action = request.form.get("action")
        
        if prompt_text:
            try:
                if action == "generate":
                    try:
                        img_bytes = query_huggingface_with_retry(prompt_text)
                        image = Image.open(io.BytesIO(img_bytes))
                        backend_used = "Hugging Face (FLUX.1)"
                    except:
                        try:
                            image = fallback_pollinations(prompt_text)
                            backend_used = "Pollinations (Tor)"
                            flash("Primary busy. Switched to Tor Fallback.", "info")
                        except Exception as e:
                            flash(f"Generation Failed: {e}", "error")
                            image = None

                elif action == "edit":
                    f = request.files.get("init_image")
                    key = get_random_hf_key()
                    if f and key:
                        client = InferenceClient(token=key)
                        image = client.image_to_image(prompt=prompt_text, image=Image.open(f).convert("RGB"), model=MODEL_EDIT)
                        backend_used = "HF InstructPix2Pix"
                    else:
                        flash("Missing Image or API Key for Edit", "error")
                        image = None

                if image:
                    image = add_watermark_to_image(image)
                    generated_image = process_image(image)

            except Exception as e:
                flash(f"System Error: {e}", "error")

    return render_template("index.html", generated_image=generated_image, prompt=prompt_text, backend=backend_used)

if __name__ == "__main__":
    if not os.path.exists('static'): os.makedirs('static')
    app.run(debug=True, port=5000)
                      
