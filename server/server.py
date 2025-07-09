from flask import Flask, request, jsonify, send_from_directory, send_file
import subprocess
import os

app = Flask(__name__)

# 下载文件保存目录
DOWNLOAD_DIR = "./downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@app.route('/add_magnet', methods=['POST'])
def add_magnet():
    magnet = request.form.get('magnet')
    if not magnet:
        return jsonify({"error": "No magnet link provided"}), 400

    # aria2c 命令
    cmd = [
        "aria2c",
        "--dir=" + DOWNLOAD_DIR,
        "--seed-time=0",
        "--max-upload-limit=1K",
        "--enable-dht=true",
        "--enable-dht6=true",
        "--enable-peer-exchange=true",
        "--bt-enable-lpd=true",
        "--bt-tracker=http://tracker.opentrackr.org:1337/announce,udp://tracker.opentrackr.org:1337/announce,udp://open.stealth.si:80/announce,udp://tracker.openbittorrent.com:80/announce,udp://tracker.leechers-paradise.org:6969/announce,udp://tracker.internetwarriors.net:1337/announce,udp://tracker.coppersurfer.tk:6969/announce",
        "--listen-port=6943",
        "--dht-listen-port=6974",
        magnet
    ]

    # 后台执行（非阻塞）
    subprocess.Popen(cmd)

    return jsonify({"message": "Download started!"})

@app.route('/files', methods=['GET'])
def list_files():
    files = os.listdir(DOWNLOAD_DIR)
    return jsonify({"files": files})

@app.route('/download/<path:filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

@app.route('/')
def index():
    return send_file("index.html")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)