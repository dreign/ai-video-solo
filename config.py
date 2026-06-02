"""配置文件 - 存放 API 密钥等配置"""
import os

# DeepSeek API 配置
DEEPSEEK_API_KEY = "sk-f553a65fbdd64652b4de3783b2833025"
DEEPSEEK_API_BASE = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"

# 火山引擎 Ark API 配置（doubao-seedream 图片生成）
ARK_API_KEY = "f95e0a82-5e68-4b13-a196-053aeba3c221"
ARK_IMAGE_MODEL = "doubao-seedream-4-5-251128"
ARK_IMAGE_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/images/generations"

# ComfyUI 配置
COMFYUI_HOST = "http://127.0.0.1:8000"
COMFYUI_OUTPUT_DIR = r"C:\Users\Administrator\Documents\ComfyUI\output"

# 项目基础路径（基于当前文件所在目录动态计算）
SOLO_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.join(SOLO_DIR, "projects")
PROJECTS_INDEX = os.path.join(SOLO_DIR, "projects.json")

# 工作流文件路径（已复制到 solo 目录下）
VIDEO_WORKFLOW_PATH = os.path.join(SOLO_DIR, "video_ltx2_3_i2v_api.json")

# Flask 服务配置
FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5000
FLASK_DEBUG = True