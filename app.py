import os
import base64
import io
import sys
from flask import Flask, render_template, request, flash
from google import genai
from google.genai import types
from PIL import Image
from dotenv import load_dotenv

# 1. Force load .env file (useful for local development)
load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = "super_secret_key"  # Change this for production

# --- CONFIGURATION ---
# The official model ID for Nano Banana
MODEL_ID = "gemini-2.5-flash-image"

# --- CLIENT INITIALIZATION & DEBUGGING ---
api_key = os.getenv("GEMINI_API_KEY")

# Check if API Key exists and print status to console/logs
if not api_key:
    print("❌ CRITICAL ERROR: GEMINI_API_KEY not found in environment variables.")
    print("👉 If local: Check your .env file.")
    print("👉 If on Render: Check 'Environment' tab in Dashboard.")
    client = None
else:
    # Print masked key to logs to confirm it loaded
    print(f"✅ API Key found: {api_key[:5]}********")
    
    # Initialize Client
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"❌ Error initializing Google GenAI Client: {e}")
        client = None

def process_image_to_base64(pil_image):
    """Helper to convert PIL Image to Base64 string for HTML display"""
    buffered = io.BytesIO()
    pil_image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return img_str

@app.route("/", methods=["GET", "POST"])
def index():
    generated_image = None
    prompt_text = ""
    
    if request.method == "POST":
        # Safety Check: Ensure client is ready
        if not client:
            flash("Server Error: API Key missing or invalid. Check server logs.", "error")
            return render_template("index.html", generated_image=None, prompt="")

        action = request.form.get("action")
        prompt_text = request.form.get("prompt")
        
        try:
            if action == "generate":
                # --- MODE 1: Text-to-Image (Generator) ---
                if not prompt_text:
                    flash("Please enter a prompt!", "error")
                else:
                    print(f"Generating with prompt: {prompt_text}")
                    
                    # CORRECTED METHOD: generate_images (Plural)
                    response = client.models.generate_images(
                        model=MODEL_ID,
                        prompt=prompt_text,
                        config=types.GenerateImageConfig(
                            number_of_images=1,
                            aspect_ratio="1:1"
                        )
                    )
                    
                    if response.generated_images:
                        generated_image = process_image_to_base64(response.generated_images[0].image)

            elif action == "edit":
                # --- MODE 2: Image+Text-to-Image (Editor) ---
                uploaded_file = request.files.get("init_image")
                
                if not uploaded_file or uploaded_file.filename == '':
                    flash("Please upload an image to edit!", "error")
                elif not prompt_text:
                    flash("Please describe the edit!", "error")
                else:
                    print(f"Editing image with prompt: {prompt_text}")
                    input_image = Image.open(uploaded_file).convert("RGB")
                    
                    # CORRECTED METHOD: edit_images (Plural)
                    response = client.models.edit_images(
                        model=MODEL_ID,
                        prompt=prompt_text,
                        image=input_image,
                        config=types.EditImageConfig(
                            number_of_images=1,
                        )
                    )
                    
                    if response.generated_images:
                        generated_image = process_image_to_base64(response.generated_images[0].image)

        except Exception as e:
            # Print full error to logs for debugging
            print(f"API CALL FAILED: {e}")
            flash(f"API Error: {str(e)}", "error")

    return render_template("index.html", generated_image=generated_image, prompt=prompt_text)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
    
