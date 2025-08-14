import os
import logging
import time
import re
from flask import Flask, request, jsonify
from PIL import Image, ImageEnhance
import requests
from io import BytesIO

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
app = Flask(__name__)

ROBLOX_ASSET_URL = "https://assetdelivery.roblox.com/v1/asset/?id={}"
ROBLOX_THUMBNAIL_URL = "https://thumbnails.roblox.com/v1/assets?assetIds={}&returnPolicy=PlaceHolder&size=420x420&format=Png&isCircular=false"

SUPPORTED_FORMATS = {
    'JPEG', 'JPG', 'PNG', 'GIF', 'BMP', 'TIFF', 'WEBP', 'ICO'
}

def is_roblox_asset_id(url_or_id):
    """Check if the input is a Roblox asset ID"""
    if isinstance(url_or_id, str):
        return url_or_id.isdigit()
    return False

def get_roblox_image_url(asset_id):
    """Get the actual image URL from Roblox asset ID"""
    try:
        thumbnail_url = ROBLOX_THUMBNAIL_URL.format(asset_id)
        response = requests.get(thumbnail_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                image_url = data['data'][0].get('imageUrl')
                if image_url:
                    return image_url
        
        asset_url = ROBLOX_ASSET_URL.format(asset_id)
        return asset_url
        
    except Exception as e:
        logger.warning(f"Failed to get Roblox thumbnail, using direct asset URL: {str(e)}")
        return ROBLOX_ASSET_URL.format(asset_id)

def enhance_image_quality(image):
    """Apply quality enhancements before resizing"""
    if image.mode != 'RGB':
        if image.mode == 'RGBA':
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
        else:
            image = image.convert('RGB')
    
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(1.2)
    
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.1)
    
    return image

def resize_with_quality(image, target_size):
    """Resize image with high quality resampling"""
    original_size = image.size
    
    if original_size[0] < target_size[0] or original_size[1] < target_size[1]:
        image = image.resize(
            (max(original_size[0], target_size[0] * 2), 
             max(original_size[1], target_size[1] * 2)), 
            Image.Resampling.LANCZOS
        )
    
    image = image.resize(target_size, Image.Resampling.LANCZOS)
    return image

@app.route('/')
def home():
    logger.info("Home endpoint accessed")
    return jsonify({
        "message": "Welcome to the Enhanced Image Converter API!",
        "status": "deployed",
        "timestamp": time.time(),
        "features": [
            "High-quality image conversion",
            "Multiple format support (PNG, JPEG, GIF, BMP, TIFF, WEBP, ICO)",
            "Roblox asset ID support",
            "Configurable output dimensions",
            "Enhanced pixel processing"
        ]
    }), 200

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()}), 200

@app.route('/convert-image', methods=['GET'])
def convert_image():
    start_time = time.time()
    logger.info("Convert image endpoint accessed")
    
    image_input = request.args.get('url') or request.args.get('id')
    width = int(request.args.get('width', 32))
    height = int(request.args.get('height', 32))
    
    if width > 512 or height > 512:
        return jsonify({'error': 'Maximum dimensions are 512x512'}), 400
    
    if not image_input:
        logger.warning("No URL or ID provided in request")
        return jsonify({'error': 'No URL or asset ID provided in query parameters (use ?url= or ?id=)'}), 400
    
    try:
        if is_roblox_asset_id(image_input):
            logger.info(f"Processing Roblox asset ID: {image_input}")
            image_url = get_roblox_image_url(image_input)
            logger.info(f"Resolved to URL: {image_url}")
        else:
            image_url = image_input
            logger.info(f"Processing image from URL: {image_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site'
        }
        
        domain = image_url.split('/')[2] if len(image_url.split('/')) > 2 else ''
        
        if 'stockcake.com' in domain.lower():
            headers['Referer'] = 'https://stockcake.com/'
        elif 'imgur.com' in domain.lower():
            headers['Referer'] = 'https://imgur.com/'
        elif 'discord' in domain.lower():
            headers['Referer'] = 'https://discord.com/'
        elif 'pinterest' in domain.lower():
            headers['Referer'] = 'https://www.pinterest.com/'
        else:
            headers['Referer'] = f"https://{domain}/"
        
        response = requests.get(image_url, timeout=20, headers=headers, stream=True, allow_redirects=True)
        
        if response.status_code == 403:
            logger.warning("403 Forbidden - trying alternative approach")
            alt_headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
                'Referer': 'https://www.google.com/',
                'Accept': 'image/*,*/*'
            }
            response = requests.get(image_url, timeout=20, headers=alt_headers, allow_redirects=True)
        
        if response.status_code == 429:
            logger.warning("Rate limited - waiting before retry")
            time.sleep(2)
            response = requests.get(image_url, timeout=20, headers=headers, allow_redirects=True)
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch image: HTTP {response.status_code}")
            return jsonify({
                'error': f'Failed to fetch image: HTTP {response.status_code}',
                'url_tested': image_url,
                'suggestion': 'Try a different image URL or check if the image is publicly accessible'
            }), 500
        
        if len(response.content) == 0:
            return jsonify({'error': 'Empty image file received'}), 500
        
        content_type = response.headers.get('content-type', '').lower()
        if content_type and not any(img_type in content_type for img_type in ['image/', 'application/octet-stream']):
            return jsonify({'error': f'URL does not point to an image (content-type: {content_type})'}), 400
        
        try:
            image = Image.open(BytesIO(response.content))
            original_format = image.format
            logger.info(f"Opened image: {image.size}, format: {original_format}")
        except Exception as e:
            logger.error(f"Failed to open image: {str(e)}")
            return jsonify({
                'error': f'Failed to open image: {str(e)}',
                'suggestion': 'The URL might not point to a valid image file'
            }), 500
        
        if original_format not in SUPPORTED_FORMATS and original_format:
            logger.warning(f"Potentially unsupported format: {original_format}")
        
        image = enhance_image_quality(image)
        image = resize_with_quality(image, (width, height))
        
        pixels = []
        try:
            for y in range(image.height):
                for x in range(image.width):
                    pixel = image.getpixel((x, y))
                    
                    if isinstance(pixel, tuple):
                        if len(pixel) >= 3:
                            r, g, b = pixel[:3]
                        elif len(pixel) == 1:
                            r = g = b = pixel[0]
                        else:
                            r = g = b = pixel if isinstance(pixel, (int, float)) else 0
                    else:
                        r = g = b = pixel if isinstance(pixel, (int, float)) else 0
                    
                    r = max(0, min(255, int(r)))
                    g = max(0, min(255, int(g)))
                    b = max(0, min(255, int(b)))
                    
                    pixels.append({'R': r, 'G': g, 'B': b})
                
        except Exception as e:
            logger.error(f"Error processing pixels: {str(e)}")
            return jsonify({'error': f'Error processing pixels: {str(e)}'}), 500
        
        processing_time = time.time() - start_time
        logger.info(f"Image processed successfully in {processing_time:.2f} seconds")
        
        return jsonify({
            'pixels': pixels,
            'width': width,
            'height': height,
            'total_pixels': len(pixels),
            'processing_time': processing_time,
            'original_format': original_format,
            'success': True
        })
        
    except requests.exceptions.Timeout:
        logger.error("Request timed out")
        return jsonify({'error': 'Request timed out fetching the image (20s limit)'}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return jsonify({'error': f'Network error: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

@app.route('/formats')
def supported_formats():
    return jsonify({
        'supported_formats': list(SUPPORTED_FORMATS),
        'roblox_support': True,
        'max_dimensions': '512x512',
        'default_size': '32x32'
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting enhanced application on port {port}")
    app.run(host='0.0.0.0', port=port)
