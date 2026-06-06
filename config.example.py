"""配置文件示例 - 复制为 config.py 并填入实际密钥"""
import os

# ===== 文本处理（LLM） =====
# 引擎: "deepseek"（DeepSeek 官方 API）| "ark"（豆包 Ark DeepSeek）| "agnes"（Agnes AI）
TEXT_ENGINE = "deepseek"

# DeepSeek 官方 API
DEEPSEEK_API_KEY = "your-deepseek-api-key"
DEEPSEEK_API_BASE = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"

# 豆包 Ark DeepSeek（备选，使用 ARK_API_KEY 鉴权）
ARK_TEXT_MODEL = "deepseek-v4-flash-260425"
ARK_TEXT_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/responses"

# Agnes AI API
AGNES_API_KEY = "sk-sC9PAfKo5dfdv7gV5gDGzQHKT9k4IxQNFNMbOQDCMN6l35Ap"
AGNES_API_BASE = "https://apihub.agnes-ai.com/v1"
AGNES_TEXT_MODEL = "agnes-2.0-flash"

# ===== 图片处理 =====
# 引擎: "doubao"（豆包Seedream）| "comfyui"（Z-Image-Turbo）| "agnes"（Agnes AI）
IMAGE_ENGINE = "doubao"

# 火山引擎 Ark API（图片）
ARK_API_KEY = "your-ark-api-key"
ARK_IMAGE_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
# 可用模型: doubao-seedream-4-5-251128 | doubao-seedream-5-0-260128
ARK_IMAGE_MODEL = "doubao-seedream-4-5-251128"

# Agnes AI 图像 API
AGNES_IMAGE_MODEL = "agnes-image-2.1-flash"
AGNES_IMAGE_ENDPOINT = "https://apihub.agnes-ai.com/v1/images/generations"

# ComfyUI 文生图工作流（备选方案）
COMFYUI_IMAGE_WORKFLOW = "image_z_image_turbo_api.json"

# ===== 视频处理 =====
# 引擎: "comfyui"（LTX I2V）| "doubao"（Seedance）| "agnes"（Agnes AI）
VIDEO_ENGINE = "comfyui"

# ComfyUI
COMFYUI_HOST = "http://127.0.0.1:8000"
COMFYUI_OUTPUT_DIR = r"C:\Users\Administrator\Documents\ComfyUI\output"
COMFYUI_VIDEO_WORKFLOW = "video_ltx2_3_i2v_api.json"

# 火山引擎 Seedance（备选方案）
ARK_VIDEO_MODEL = "doubao-seedance-2-0-fast-260128"
ARK_VIDEO_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/video/generations"

# Agnes AI 视频 API
AGNES_VIDEO_MODEL = "agnes-video-v2.0"
AGNES_VIDEO_ENDPOINT = "https://apihub.agnes-ai.com/v1/videos"

# ===== 项目基础路径 =====
SOLO_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.join(SOLO_DIR, "projects")
PROJECTS_INDEX = os.path.join(SOLO_DIR, "projects.json")

# 工作流文件路径
VIDEO_WORKFLOW_PATH = os.path.join(SOLO_DIR, COMFYUI_VIDEO_WORKFLOW)
IMAGE_Z_IMAGE_TURBO_WORKFLOW_PATH = os.path.join(SOLO_DIR, COMFYUI_IMAGE_WORKFLOW)

# Flask 服务配置
FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5000
FLASK_DEBUG = True