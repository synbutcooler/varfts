import os
import logging
import time
from flask import Flask, request, jsonify
from PIL import Image
import requests
from io import BytesIO

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
app = Flask(__name__)

def fetch_image_from_source(src):
    if src.isdigit() or src.lower().startswith("rbxassetid://"):
        asset_id = src.replace("rbxassetid://", "")
        src = f"https://www.roblox.com/asset-thumbnail/image?assetId={asset_id}&width=420&height=420&format=png"

    resp = requests.get(src, timeout=20, allow_redirects=True, headers={
        "User-Agent": "Mozilla/5.0"
    })
    if resp.status_code != 200:
        raise Exception(f"Failed to fetch image: HTTP {resp.status_code}")

    image = Image.open(BytesIO(resp.content))
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA")

    if image.mode == "RGBA":
        bg = Image.new("RGB", image.size, (255, 255, 255))
        bg.paste(image, mask=image.split()[-1])
        image = bg

    return image.resize((32, 32), Image.LANCZOS)

@app.route('/')
def home():
    logger.info("Home endpoint accessed")
    return jsonify({
        "message": "Welcome to the Image Converter API!",
        "status": "deployed",
        "timestamp": time.time()
    }), 200

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()}), 200

@app.route('/convert-image', methods=['GET'])
def convert_image():
    start_time = time.time()
    image_url = request.args.get('url')
    if not image_url:
        logger.warning("No URL provided")
        return jsonify({'error': 'No URL provided'}), 400

    try:
        image = fetch_image_from_source(image_url)
        if image.mode != "RGB":
            if image.mode in ("RGBA", "LA"):
                bg = Image.new("RGB", image.size, (255, 255, 255))
                bg.paste(image, mask=image.split()[-1])
                image = bg
            else:
                image = image.convert("RGB")
        image = image.resize((32, 32), Image.LANCZOS)
        pixels = []
        for y in range(image.height):
            for x in range(image.width):
                r, g, b = image.getpixel((x, y))
                pixels.append({'R': r, 'G': g, 'B': b})

        processing_time = time.time() - start_time
        logger.info(f"Image processed successfully in {processing_time:.2f} seconds")

        return jsonify({
            'pixels': pixels,
            'processing_time': processing_time
        })

    except Exception as e:
        logger.error(str(e))
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting application on port {port}")
    app.run(host='0.0.0.0', port=port)
