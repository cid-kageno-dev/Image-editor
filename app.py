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
# We will try the experimental model first. 
# It is often the only one that allows images on free accounts.
MODEL_ID = "gemini-2.0-flash-exp"

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
    error_message = None
    
    if request.method == "POST":
        if not client:
            flash("Server Error: API Key missing.", "error")
            return render_template("index.html", generated_image=None, prompt="")

        action = request.form.get("action")
        prompt_text = request.form.get("prompt")
        
        try:
            if action == "generate":
                if not prompt_text:
                    flash("Please enter a prompt!", "error")
                else:
                    print(f"🎨 Generating with {MODEL_ID}: {prompt_text}")
                    
                    # --- TRY GENERATING WITH GEMINI 2.0 EXP ---
                    try:
                        response = client.models.generate_content(
                            model=MODEL_ID,
                            contents=prompt_text,
                            config=types.GenerateContentConfig(
                                response_modalities=["IMAGE"]
                            )
                        )
                        
                        # Handle Response
                        if response.generated_images:
                            generated_image = process_image_to_base64(response.generated_images[0].image)
                        else:
                            flash("Model accepted the prompt but returned no image.", "error")

                    except Exception as inner_e:
                        # If the specific model fails, we catch it here nicely
                        error_msg = str(inner_e)
                        if "404" in error_msg:
                            flash(f"❌ Your API Key does not have access to {MODEL_ID}.", "error")
                            flash("👉 Check Google AI Studio to enable 'Imagen 3' or 'Gemini Exp'.", "error")
                        else:
                            flash(f"API Error: {error_msg}", "error")

            elif action == "edit":
                uploaded_file = request.files.get("init_image")
                if not uploaded_file:
                    flash("Please upload an image!", "error")
                else:
                    # Note: Editing is not supported on all text models.
                    flash("Image editing requires Imagen 3, which is missing from your account.", "error")

        except Exception as e:
            print(f"CRITICAL FAILURE: {e}")
            flash(f"System Error: {str(e)}", "error")

    return render_template("index.html", generated_image=generated_image, prompt=prompt_text)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
    
