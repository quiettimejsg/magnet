from flask import Flask, request, jsonify, send_from_directory, send_file
import subprocess
import os
import threading
import time
import signal
import sys

app = Flask(__name__)

# 下载文件保存目录
DOWNLOAD_DIR = "./downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# 存储下载进程
download_processes = {}

def get_updated_trackers():
    """获取更新的 tracker 列表"""
    trackers = [
        "http://tracker.opentrackr.org:1337/announce",
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://open.stealth.si:80/announce",
        "udp://tracker.openbittorrent.com:80/announce",
        "udp://exodus.desync.com:6969/announce",
        "udp://tracker.torrent.eu.org:451/announce",
        "udp://tracker.moeking.me:6969/announce",
        "udp://ipv4.tracker.harry.lu:80/announce",
        "udp://open.demonii.si:1337/announce",
        "udp://tracker.pomf.se:80/announce",
        "udp://tracker.tiny-vps.com:6969/announce",
        "udp://tracker.openbittorrent.com:6969/announce",
        "udp://bt1.archive.org:6969/announce",
        "udp://bt2.archive.org:6969/announce",
        "udp://tracker.dler.org:6969/announce"
    ]
    return ",".join(trackers)

@app.route('/add_magnet', methods=['POST'])
def add_magnet():
    magnet = request.form.get('magnet')
    if not magnet:
        return jsonify({"error": "No magnet link provided"}), 400

    if not magnet.startswith('magnet:'):
        return jsonify({"error": "Invalid magnet link"}), 400

    # 改进的 aria2c 命令
    cmd = [
        "aria2c",
        "--dir=" + DOWNLOAD_DIR,
        "--seed-time=0",
        "--max-upload-limit=1K",
        "--enable-dht=true",
        "--enable-dht6=true",
        "--enable-peer-exchange=true",
        "--bt-enable-lpd=true",
        "--bt-tracker=" + get_updated_trackers(),
        "--listen-port=6881-6999",
        "--dht-listen-port=6881-6999",
        "--bt-max-peers=100",
        "--bt-request-peer-speed-limit=50K",
        "--max-concurrent-downloads=5",
        "--max-connection-per-server=10",
        "--min-split-size=10M",
        "--split=10",
        "--timeout=60",
        "--retry-wait=30",
        "--max-tries=5",
        "--continue=true",
        "--allow-overwrite=true",
        "--auto-file-renaming=false",
        "--summary-interval=0",
        "--bt-stop-timeout=0",
        magnet
    ]

    try:
        # 后台执行（非阻塞）
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # 存储进程以便后续监控
        download_processes[magnet] = process
        
        return jsonify({"message": "Download started!", "magnet": magnet})
    except Exception as e:
        return jsonify({"error": f"Failed to start download: {str(e)}"}), 500

@app.route('/files', methods=['GET'])
def list_files():
    try:
        files = []
        for item in os.listdir(DOWNLOAD_DIR):
            item_path = os.path.join(DOWNLOAD_DIR, item)
            if os.path.isfile(item_path):
                size = os.path.getsize(item_path)
                files.append({
                    "name": item,
                    "size": size,
                    "size_mb": round(size / (1024 * 1024), 2)
                })
        return jsonify({"files": files})
    except Exception as e:
        return jsonify({"error": f"Failed to list files: {str(e)}"}), 500

@app.route('/download/<path:filename>', methods=['GET'])
def download_file(filename):
    try:
        return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)
    except Exception as e:
        return jsonify({"error": f"Failed to download file: {str(e)}"}), 500

@app.route('/status', methods=['GET'])
def download_status():
    """检查下载状态"""
    active_downloads = []
    for magnet, process in list(download_processes.items()):
        if process.poll() is None:  # 进程仍在运行
            active_downloads.append(magnet)
        else:
            # 进程已结束，移除
            download_processes.pop(magnet, None)
    
    return jsonify({
        "active_downloads": len(active_downloads),
        "downloads": active_downloads
    })

@app.route('/test', methods=['GET'])
def test_aria2():
    """测试 aria2c 是否正常工作"""
    try:
        result = subprocess.run(
            ["aria2c", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return jsonify({
            "aria2c_available": True,
            "version": result.stdout.split('\n')[0] if result.stdout else "Unknown"
        })
    except Exception as e:
        return jsonify({
            "aria2c_available": False,
            "error": str(e)
        })

@app.route('/')
def index():
    return send_file("index.html")

def signal_handler(sig, frame):
    print('Shutting down...')
    # 终止所有下载进程
    for process in download_processes.values():
        if process.poll() is None:
            process.terminate()
    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    print(f"Server starting... Download directory: {os.path.abspath(DOWNLOAD_DIR)}")
    print("Visit http://localhost:5000 to access the web interface")
    app.run(host='0.0.0.0', port=5000, debug=True)