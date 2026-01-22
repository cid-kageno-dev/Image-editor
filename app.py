import os
import base64
import io
import sys # Added for debug exit
from flask import Flask, render_template, request, flash
from google import genai
from google.genai import types
from PIL import Image
from dotenv import load_dotenv

# 1. Force load .env file (helps if it's in a different folder)
load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = "super_secret_key"

# 2. DEBUG: Check API Key immediately
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ CRITICAL ERROR: GEMINI_API_KEY not found in environment variables.")
    print("👉 Check your .env file or Render Environment settings.")
    # For local testing ONLY, you can uncomment the line below and paste your key:
    # api_key = "AIzaSy..." 
    
    # If we are on Render, we don't want to crash, but the app won't work
else:
    print(f"✅ API Key found: {api_key[:5]}********")

# Configure Gemini Client
MODEL_ID = "gemini-2.5-flash-image"

# Initialize Client with error handling
try:
    if api_key:
        client = genai.Client(api_key=api_key)
    else:
        # Create a dummy client to prevent startup crash, 
        # but it will fail when you try to generate images.
        client = None 
except Exception as e:
    print(f"Error initializing client: {e}")
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
        # Check if client is ready
        if not client:
            flash("Server Error: API Key missing. Check server logs.", "error")
            return render_template("index.html", generated_image=None, prompt="")

        action = request.form.get("action")
        prompt_text = request.form.get("prompt")
        
        try:
            if action == "generate":
                if not prompt_text:
                    flash("Please enter a prompt!", "error")
                else:
                    print(f"Generating with prompt: {prompt_text}")
                    response = client.models.generate_image(
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
                uploaded_file = request.files.get("init_image")
                
                if not uploaded_file or uploaded_file.filename == '':
                    flash("Please upload an image to edit!", "error")
                elif not prompt_text:
                    flash("Please describe the edit!", "error")
                else:
                    print(f"Editing image with prompt: {prompt_text}")
                    input_image = Image.open(uploaded_file).convert("RGB")
                    
                    response = client.models.edit_image(
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
            # Print the full error to the terminal so you can see it
            print(f"API CALL FAILED: {e}")
            flash(f"API Error: {str(e)}", "error")

    return render_template("index.html", generated_image=generated_image, prompt=prompt_text)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
    
