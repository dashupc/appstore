import os
import sys
import subprocess
import json
import requests
import time
from flask import Flask, request, jsonify

# --- 配置 ---
CLIENT_HOST = '127.0.0.1'
CLIENT_PORT = 9001  # 客户端监听的端口，PWA 前端将向此端口发送请求
TEMP_DIR = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), 'AppStoreDownloads')

# 确保临时下载目录存在
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)
    
app = Flask(__name__)

# --- 权限和系统操作 ---

def is_admin():
    """检查当前进程是否以管理员权限运行 (Windows Only)"""
    try:
        # Windows API 调用，用于检查权限
        return os.getuid() == 0  # 这是一个简化检查，Windows下更准确的方法是 ctypes
    except AttributeError:
        # Windows: 尝试用 ctypes
        import ctypes
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

def elevate_privileges():
    """使用 runas 命令重启程序并请求管理员权限 (Windows Only)"""
    if not is_admin():
        print("需要管理员权限才能运行。正在尝试提升权限...")
        import ctypes
        # 使用 shell32.ShellExecuteW 以 runas 动词启动自身
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, __file__, None, 1)
        sys.exit(0) # 退出当前非管理员进程
    else:
        print("客户端已在管理员模式下运行。")


def download_file(url, local_path):
    """下载文件到本地路径"""
    print(f"开始下载: {url}")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status() # 检查HTTP错误
        
        with open(local_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        print(f"下载完成: {local_path}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"下载失败: {e}")
        return False

def execute_silent_install(installer_path, silent_args):
    """执行静默安装命令"""
    # 构造完整的命令行
    command = [installer_path] + silent_args.split() # 将参数字符串分割成列表
    
    print(f"执行命令: {command}")
    
    try:
        # 使用 subprocess.run 执行安装程序，并等待其完成
        # 注意：这里假设客户端已经是以管理员权限运行的！
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        
        print(f"静默安装成功！")
        print(f"stdout: {result.stdout}")
        return True, "安装成功"
    except subprocess.CalledProcessError as e:
        error_msg = f"安装失败 (返回码 {e.returncode}): {e.stderr}"
        print(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"执行安装时发生未知错误: {e}"
        print(error_msg)
        return False, error_msg

# --- 路由：接收 PWA 的安装请求 ---

@app.route('/install', methods=['POST'])
def handle_install_request():
    """接收来自 PWA 的 JSON 请求"""
    if not is_admin():
        return jsonify({"status": "error", "message": "客户端未以管理员身份运行，无法执行安装。"}), 403

    try:
        data = request.json
        if not data or 'url' not in data or 'args' not in data:
            return jsonify({"status": "error", "message": "请求参数缺失 (需要 url 和 args)"}), 400

        download_url = data['url']
        silent_args = data['args']
        app_name = data.get('name', 'Unknown App')

        # 1. 下载文件
        file_name = os.path.basename(download_url)
        local_installer_path = os.path.join(TEMP_DIR, file_name)
        
        if not download_file(download_url, local_installer_path):
             return jsonify({"status": "error", "message": f"文件下载失败: {download_url}"}), 500

        # 2. 执行静默安装
        success, message = execute_silent_install(local_installer_path, silent_args)
        
        if success:
            # 可选：安装成功后删除安装包
            # os.remove(local_installer_path) 
            return jsonify({"status": "success", "message": f"{app_name} 安装成功"}), 200
        else:
            return jsonify({"status": "failure", "message": message}), 500

    except Exception as e:
        print(f"处理安装请求时发生致命错误: {e}")
        return jsonify({"status": "error", "message": f"服务器内部错误: {e}"}), 500


# --- 主程序入口 ---

if __name__ == '__main__':
    # 尝试提升权限
    elevate_privileges()
    
    print(f"桌面客户端启动，正在监听 {CLIENT_HOST}:{CLIENT_PORT}")
    print(f"临时下载目录: {TEMP_DIR}")
    
    # 启动 Flask 客户端服务器
    # 注意：关闭 debug=True 在生产环境是必须的
    app.run(host=CLIENT_HOST, port=CLIENT_PORT, debug=False)