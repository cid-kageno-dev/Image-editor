import os
import base64
import io
import sys
from flask import Flask, render_template, request, flash
from google import genai
from google.genai import types
from PIL import Image
from dotenv import load_dotenv

# 1. Force load .env file
load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = "super_secret_key"

# --- CONFIGURATION ---
MODEL_ID = "gemini-2.5-flash-image"

# --- CLIENT INITIALIZATION ---
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ CRITICAL ERROR: GEMINI_API_KEY not found.")
    client = None
else:
    print(f"✅ API Key found: {api_key[:5]}********")
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"❌ Error initializing Client: {e}")
        client = None

def process_image_to_base64(pil_image):
    buffered = io.BytesIO()
    pil_image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return img_str

@app.route("/", methods=["GET", "POST"])
def index():
    generated_image = None
    prompt_text = ""
    
    if request.method == "POST":
        if not client:
            flash("Server Error: API Key missing.", "error")
            return render_template("index.html", generated_image=None, prompt="")

        action = request.form.get("action")
        prompt_text = request.form.get("prompt")
        
        try:
            if action == "generate":
                # --- MODE 1: GENERATOR (Text-to-Image) ---
                if not prompt_text:
                    flash("Please enter a prompt!", "error")
                else:
                    print(f"Generating: {prompt_text}")
                    
                    # FIX 1: Use plural 'generate_images' and 'GenerateImagesConfig'
                    response = client.models.generate_images(
                        model=MODEL_ID,
                        prompt=prompt_text,
                        config=types.GenerateImagesConfig(
                            number_of_images=1,
                            aspect_ratio="1:1"
                        )
                    )
                    
                    if response.generated_images:
                        generated_image = process_image_to_base64(response.generated_images[0].image)

            elif action == "edit":
                # --- MODE 2: EDITOR (Image-to-Image) ---
                uploaded_file = request.files.get("init_image")
                
                if not uploaded_file or uploaded_file.filename == '':
                    flash("Please upload an image to edit!", "error")
                elif not prompt_text:
                    flash("Please describe the edit!", "error")
                else:
                    print(f"Editing: {prompt_text}")
                    input_image = Image.open(uploaded_file).convert("RGB")
                    
                    # FIX 2: Use plural 'edit_images' and 'EditImagesConfig'
                    response = client.models.edit_images(
                        model=MODEL_ID,
                        prompt=prompt_text,
                        image=input_image,
                        config=types.EditImagesConfig(
                            number_of_images=1,
                        )
                    )
                    
                    if response.generated_images:
                        generated_image = process_image_to_base64(response.generated_images[0].image)

        except Exception as e:
            print(f"API CALL FAILED: {e}")
            flash(f"API Error: {str(e)}", "error")

    return render_template("index.html", generated_image=generated_image, prompt=prompt_text)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
    
