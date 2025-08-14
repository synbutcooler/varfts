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
    logger.info("Convert image endpoint accessed")
    
    image_url = request.args.get('url')
    if not image_url:
        logger.warning("No URL provided in request")
        return jsonify({'error': 'No URL provided in query parameters'}), 400
    
    logger.info(f"Processing image from URL: {image_url}")
    
    try:
        response = requests.get(image_url, timeout=15)

        if response.status_code != 200:
            logger.error(f"Failed to fetch image: HTTP {response.status_code}")
            return jsonify({'error': f'Failed to fetch image: HTTP {response.status_code}'}), 500

        try:
            image = Image.open(BytesIO(response.content))
        except Exception as e:
            logger.error(f"Failed to open image: {str(e)}")
            return jsonify({'error': f'Failed to open image: {str(e)}'}), 500

        image = image.resize((32, 32))

        pixels = []
        try:
            for y in range(image.height):
                for x in range(image.width):
                    pixel = image.getpixel((x, y))
                    if len(pixel) >= 3:
                        r, g, b = pixel[:3]
                    else:
                        r = g = b = pixel if isinstance(pixel, int) else pixel[0]
                    pixels.append({'R': r, 'G': g, 'B': b})
        except Exception as e:
            logger.error(f"Error processing pixels: {str(e)}")
            return jsonify({'error': f'Error processing pixels: {str(e)}'}), 500
        
        processing_time = time.time() - start_time
        logger.info(f"Image processed successfully in {processing_time:.2f} seconds")
        
        return jsonify({
            'pixels': pixels,
            'processing_time': processing_time
        })
    except requests.exceptions.Timeout:
        logger.error("Request timed out")
        return jsonify({'error': 'Request timed out fetching the image'}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return jsonify({'error': f'Request error: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting application on port {port}")
    app.run(host='0.0.0.0', port=port)
