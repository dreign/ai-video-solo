#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Solo 视频生成工具 - 一键启动脚本
解决 Flask debug 模式进程状态误判问题，使用单进程稳定运行
"""

import os
import sys
import subprocess
import time

def check_python_version():
    if sys.version_info < (3, 10):
        print("[错误] 请安装 Python 3.10 或更高版本")
        print(f"当前版本: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        return False
    print(f"[OK] Python 版本: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True

def install_dependencies():
    print("\n[1/2] 检查并安装依赖...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
            check=True,
            capture_output=True,
            text=True
        )
        print("[OK] 依赖安装完成")
    except subprocess.CalledProcessError as e:
        print(f"[警告] 依赖安装可能有问题")
        print("继续启动服务...")

def start_server():
    print("\n[2/2] 启动服务...")
    print("=" * 60)
    print("      Solo 视频生成工具 - 服务已启动")
    print("=" * 60)
    print(f"访问地址: http://127.0.0.1:5000")
    print(f"服务进程: Python {sys.executable}")
    print("=" * 60)
    print("按 Ctrl+C 停止服务")
    print()
    
    env = os.environ.copy()
    env['FLASK_DEBUG'] = 'false'
    
    subprocess.run(
        [sys.executable, "-c", '''
import sys
sys.path.insert(0, '.')
from app import app
from config import FLASK_HOST, FLASK_PORT

print(f"[INFO] Flask 配置: host={FLASK_HOST}, port={FLASK_PORT}")
app.run(
    host=FLASK_HOST, 
    port=FLASK_PORT, 
    debug=False,
    use_reloader=False,
    threaded=True
)
'''],
        env=env,
        check=True
    )

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    print("=" * 60)
    print("    Solo 视频生成工具 - 一键启动")
    print("=" * 60)
    
    if not check_python_version():
        input("按 Enter 键退出...")
        sys.exit(1)
    
    install_dependencies()
    start_server()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] 服务已停止")
    except Exception as e:
        print(f"\n[错误] 启动失败: {e}")
        input("按 Enter 键退出...")
        sys.exit(1)