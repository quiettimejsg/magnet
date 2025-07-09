from flask import Flask, request, jsonify, send_from_directory
import subprocess
import os

app = Flask(__name__)

# 下载文件存放目录
DOWNLOAD_DIR = "./server/download/files"  # ⚠️ 改成你想要的路径

# 确保目录存在
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@app.route('/add_magnet', methods=['POST'])
def add_magnet():
    magnet = request.form.get('magnet')
    if not magnet:
        return jsonify({"error": "No magnet link provided"}), 400
    
    # 用 aria2c 下载到 DOWNLOAD_DIR
    cmd = [
        "aria2c",
        "--dir=" + DOWNLOAD_DIR,
        "--seed-time=0",
        "--max-upload-limit=1K",
        magnet
    ]
    subprocess.Popen(cmd)

    return jsonify({"message": "Download started!"})

@app.route('/files', methods=['GET'])
def list_files():
    files = os.listdir(DOWNLOAD_DIR)
    return jsonify({"files": files})

@app.route('/download/<path:filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

from flask import send_file

@app.route('/')
def index():
    return send_file('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)