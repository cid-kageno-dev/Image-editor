import os
import base64
import io
from flask import Flask, render_template, request, flash
from google import genai
from google.genai import types
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = "super_secret_key"  # Change this for production

# Configure Gemini Client
# "Nano Banana" is officially the 'gemini-2.5-flash-image' model
MODEL_ID = "gemini-2.5-flash-image"

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

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
        action = request.form.get("action")
        prompt_text = request.form.get("prompt")
        
        try:
            if action == "generate":
                # --- MODE 1: Text-to-Image (Generator) ---
                if not prompt_text:
                    flash("Please enter a prompt!", "error")
                else:
                    response = client.models.generate_image(
                        model=MODEL_ID,
                        prompt=prompt_text,
                        config=types.GenerateImageConfig(
                            number_of_images=1,
                            aspect_ratio="1:1" # Options: 1:1, 3:4, 4:3, 16:9, 9:16
                        )
                    )
                    # The response contains the image object directly
                    if response.generated_images:
                        generated_image = process_image_to_base64(response.generated_images[0].image)

            elif action == "edit":
                # --- MODE 2: Image+Text-to-Image (Editor) ---
                uploaded_file = request.files.get("init_image")
                
                if not uploaded_file or uploaded_file.filename == '':
                    flash("Please upload an image to edit!", "error")
                elif not prompt_text:
                    flash("Please describe the edit (e.g., 'Make it snow')!", "error")
                else:
                    # Open the uploaded image with PIL
                    input_image = Image.open(uploaded_file).convert("RGB")
                    
                    # Gemini 2.5 Flash Image uses the prompt to guide the edit of the input image
                    # Note: We pass the image as a separate argument or part of the inputs depending on the SDK version.
                    # In the latest google-genai SDK for images, editing is often a prompt variation.
                    # However, strictly speaking, `generate_images` usually takes text. 
                    # For editing, we use the `edit_image` method if available, or pass image in contents.
                    
                    # Current Best Practice for Edit with Gemini 2.5 Flash Image:
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
            flash(f"API Error: {str(e)}", "error")
            print(f"Error: {e}")

    return render_template("index.html", generated_image=generated_image, prompt=prompt_text)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
