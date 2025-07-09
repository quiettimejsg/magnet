from flask import Flask, request, jsonify, send_from_directory, send_file
import subprocess
import os
import threading
import time
import json
import re
import signal
import sys
from datetime import datetime

app = Flask(__name__)

# 下载文件保存目录
DOWNLOAD_DIR = "./downloads"
ARIA2_SESSION_DIR = "./aria2_sessions"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(ARIA2_SESSION_DIR, exist_ok=True)

# 存储下载任务信息
download_tasks = {}
aria2_process = None

def start_aria2_daemon():
    """启动 aria2c RPC 服务"""
    global aria2_process
    
    # 检查是否已经运行
    if aria2_process and aria2_process.poll() is None:
        return True
    
    try:
        # aria2c RPC 配置
        cmd = [
            "aria2c",
            "--enable-rpc",
            "--rpc-listen-all",
            "--rpc-listen-port=6800",
            "--rpc-secret=mysecret",
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
            "--summary-interval=1",
            "--log-level=info",
            "--console-log-level=info"
        ]
        
        aria2_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 等待服务启动
        time.sleep(2)
        print("Aria2 RPC daemon started successfully")
        return True
        
    except Exception as e:
        print(f"Failed to start aria2c daemon: {e}")
        return False

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

def call_aria2_rpc(method, params=None):
    """调用 aria2 RPC 接口"""
    import json
    import urllib.request
    import urllib.parse
    
    if params is None:
        params = []
    
    # 添加 secret token
    params.insert(0, "token:mysecret")
    
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": method,
        "params": params
    }
    
    try:
        req = urllib.request.Request(
            "http://localhost:6800/jsonrpc",
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('result')
    except Exception as e:
        print(f"RPC call failed: {e}")
        return None

@app.route('/add_magnet', methods=['POST'])
def add_magnet():
    magnet = request.form.get('magnet')
    if not magnet:
        return jsonify({"error": "No magnet link provided"}), 400

    if not magnet.startswith('magnet:'):
        return jsonify({"error": "Invalid magnet link"}), 400

    # 确保 aria2c daemon 正在运行
    if not start_aria2_daemon():
        return jsonify({"error": "Failed to start aria2c daemon"}), 500

    try:
        # 通过 RPC 添加下载任务
        result = call_aria2_rpc("aria2.addUri", [[magnet]])
        
        if result:
            # 存储任务信息
            task_id = result
            download_tasks[task_id] = {
                "magnet": magnet,
                "start_time": datetime.now().isoformat(),
                "status": "active"
            }
            return jsonify({"message": "Download started!", "task_id": task_id})
        else:
            return jsonify({"error": "Failed to add download task"}), 500
            
    except Exception as e:
        return jsonify({"error": f"Failed to start download: {str(e)}"}), 500

@app.route('/progress', methods=['GET'])
def get_progress():
    """获取所有下载任务的进度"""
    try:
        # 获取活动下载
        active_downloads = call_aria2_rpc("aria2.tellActive")
        # 获取等待中的下载
        waiting_downloads = call_aria2_rpc("aria2.tellWaiting", [0, 100])
        # 获取已停止的下载
        stopped_downloads = call_aria2_rpc("aria2.tellStopped", [0, 100])
        
        all_downloads = []
        
        # 处理活动下载
        if active_downloads:
            for download in active_downloads:
                progress_info = parse_download_info(download)
                all_downloads.append(progress_info)
        
        # 处理等待中的下载
        if waiting_downloads:
            for download in waiting_downloads:
                progress_info = parse_download_info(download)
                all_downloads.append(progress_info)
        
        # 处理已停止的下载
        if stopped_downloads:
            for download in stopped_downloads:
                progress_info = parse_download_info(download)
                all_downloads.append(progress_info)
        
        return jsonify({"downloads": all_downloads})
        
    except Exception as e:
        return jsonify({"error": f"Failed to get progress: {str(e)}"}), 500

def parse_download_info(download):
    """解析下载信息"""
    try:
        total_length = int(download.get('totalLength', 0))
        completed_length = int(download.get('completedLength', 0))
        download_speed = int(download.get('downloadSpeed', 0))
        
        # 计算进度百分比
        if total_length > 0:
            progress = (completed_length / total_length) * 100
        else:
            progress = 0
        
        # 格式化文件大小
        def format_size(size):
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        
        # 格式化速度
        def format_speed(speed):
            return format_size(speed) + "/s"
        
        # 估算剩余时间
        eta = "未知"
        if download_speed > 0 and total_length > completed_length:
            remaining_time = (total_length - completed_length) / download_speed
            if remaining_time < 60:
                eta = f"{int(remaining_time)}秒"
            elif remaining_time < 3600:
                eta = f"{int(remaining_time/60)}分钟"
            else:
                eta = f"{int(remaining_time/3600)}小时{int((remaining_time%3600)/60)}分钟"
        
        return {
            "gid": download.get('gid'),
            "status": download.get('status'),
            "file_name": download.get('files', [{}])[0].get('path', '未知文件').split('/')[-1] if download.get('files') else '未知文件',
            "total_length": total_length,
            "completed_length": completed_length,
            "progress": round(progress, 1),
            "download_speed": download_speed,
            "formatted_total": format_size(total_length),
            "formatted_completed": format_size(completed_length),
            "formatted_speed": format_speed(download_speed),
            "eta": eta,
            "num_seeders": download.get('numSeeders', 0),
            "connections": download.get('connections', 0)
        }
    except Exception as e:
        print(f"Error parsing download info: {e}")
        return {
            "gid": download.get('gid', 'unknown'),
            "status": download.get('status', 'error'),
            "file_name": "解析错误",
            "progress": 0,
            "error": str(e)
        }

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

@app.route('/pause/<gid>', methods=['POST'])
def pause_download(gid):
    """暂停下载"""
    try:
        result = call_aria2_rpc("aria2.pause", [gid])
        if result:
            return jsonify({"message": "Download paused", "gid": gid})
        else:
            return jsonify({"error": "Failed to pause download"}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to pause download: {str(e)}"}), 500

@app.route('/resume/<gid>', methods=['POST'])
def resume_download(gid):
    """恢复下载"""
    try:
        result = call_aria2_rpc("aria2.unpause", [gid])
        if result:
            return jsonify({"message": "Download resumed", "gid": gid})
        else:
            return jsonify({"error": "Failed to resume download"}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to resume download: {str(e)}"}), 500

@app.route('/remove/<gid>', methods=['POST'])
def remove_download(gid):
    """删除下载任务"""
    try:
        # 先尝试暂停
        call_aria2_rpc("aria2.pause", [gid])
        # 然后删除
        result = call_aria2_rpc("aria2.remove", [gid])
        if result:
            return jsonify({"message": "Download removed", "gid": gid})
        else:
            return jsonify({"error": "Failed to remove download"}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to remove download: {str(e)}"}), 500

@app.route('/test', methods=['GET'])
def test_aria2():
    """测试 aria2c 是否正常工作"""
    try:
        # 测试 aria2c 版本
        result = subprocess.run(
            ["aria2c", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # 测试 RPC 连接
        rpc_status = False
        if start_aria2_daemon():
            version_info = call_aria2_rpc("aria2.getVersion")
            rpc_status = version_info is not None
        
        return jsonify({
            "aria2c_available": True,
            "version": result.stdout.split('\n')[0] if result.stdout else "Unknown",
            "rpc_status": rpc_status
        })
    except Exception as e:
        return jsonify({
            "aria2c_available": False,
            "error": str(e),
            "rpc_status": False
        })

@app.route('/')
def index():
    return send_file("index.html")

def signal_handler(sig, frame):
    print('Shutting down...')
    global aria2_process
    if aria2_process and aria2_process.poll() is None:
        aria2_process.terminate()
    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    print(f"Server starting... Download directory: {os.path.abspath(DOWNLOAD_DIR)}")
    print("Starting aria2c daemon...")
    start_aria2_daemon()
    print("Visit http://localhost:5000 to access the web interface")
    app.run(host='0.0.0.0', port=5000, debug=True)