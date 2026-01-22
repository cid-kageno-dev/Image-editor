import os
import base64
import io
from flask import Flask, render_template, request, flash
from google import genai
from google.genai import types
from PIL import Image
from dotenv import load_dotenv

load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = "super_secret_key"

# --- THE ONLY MODEL THAT WORKS FOR FREE IMAGES ---
# Do not change this to "gemini-2.5-flash" (Text only)
# Do not change this to "imagen-3.0" (You don't have access)
MODEL_ID = "gemini-2.0-flash-exp"

api_key = os.getenv("GEMINI_API_KEY")
client = None

if api_key:
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"Error: {e}")

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
            flash("API Key missing!", "error")
            return render_template("index.html", generated_image=None, prompt="")

        action = request.form.get("action")
        prompt_text = request.form.get("prompt")
        
        try:
            if action == "generate":
                if not prompt_text:
                    flash("Enter a prompt!", "error")
                else:
                    print(f"🎨 Generating with {MODEL_ID}...")
                    
                    # Gemini 2.0 EXP uses 'generate_content', NOT 'generate_images'
                    response = client.models.generate_content(
                        model=MODEL_ID,
                        contents=prompt_text,
                        config=types.GenerateContentConfig(
                            response_modalities=["IMAGE"]
                        )
                    )
                    
                    if response.generated_images:
                        generated_image = process_image_to_base64(response.generated_images[0].image)
                    else:
                        flash("Model returned no image.", "error")

            elif action == "edit":
                 flash("Editing is temporarily disabled to fix the Generator first.", "error")

        except Exception as e:
            error_msg = str(e)
            print(f"API ERROR: {error_msg}")
            
            # CUSTOM ERROR MESSAGES
            if "404" in error_msg:
                flash(f"❌ Your API Key cannot access '{MODEL_ID}'.", "error")
                flash("💡 SOLUTION: Go to Google AI Studio > Settings > Billing and add a card (Free tier still needs verification).", "error")
            elif "400" in error_msg:
                flash(f"❌ Model '{MODEL_ID}' rejected the request.", "error")
            else:
                flash(f"Error: {error_msg}", "error")

    return render_template("index.html", generated_image=generated_image, prompt=prompt_text)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
    
