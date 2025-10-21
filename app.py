from flask import Flask, render_template, send_from_directory
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/sw.js')
def sw():
    return send_from_directory('.', 'sw.js')

@app.route('/<int:image_id>.jpg')
def serve_image(image_id):
    if 1 <= image_id <= 5:
        response = send_from_directory('.', f'{image_id}.jpg')
        # Add cache headers for large images
        response.headers['Cache-Control'] = 'public, max-age=31536000'  # Cache for 1 year
        response.headers['Expires'] = '31536000'  # Expires in 1 year
        return response
    else:
        return "Image not found", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
