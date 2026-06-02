"""统一日志模块"""
import json
import logging
import os
import sys
from datetime import datetime
from config import SOLO_DIR

LOG_FILE = os.path.join(SOLO_DIR, "app.log")

# 根 logger 配置
logger = logging.getLogger("solo")
logger.setLevel(logging.DEBUG)

# 控制台 handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_fmt = logging.Formatter(
    "[%(asctime)s] [%(levelname)-5s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
console_handler.setFormatter(console_fmt)
logger.addHandler(console_handler)

# 文件 handler
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_fmt = logging.Formatter(
    "[%(asctime)s] [%(levelname)-5s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
file_handler.setFormatter(file_fmt)
logger.addHandler(file_handler)


def log_step(step_name: str, status: str = "开始", detail: str = ""):
    """记录主要步骤"""
    sep = "=" * 60
    msg = f"{sep}\n  >>> [{status}] {step_name}"
    if detail:
        msg += f"\n  --- {detail}"
    logger.info(msg)


def log_llm_call(model: str, purpose: str, prompt_len: int, response_len: int, duration: float = 0):
    """记录大模型调用"""
    logger.info(
        f"[LLM] {purpose} | model={model} | "
        f"prompt={prompt_len}chars | response={response_len}chars | "
        f"duration={duration:.1f}s"
    )


def log_llm_response(purpose: str, response: str):
    """记录大模型返回内容（缩略）"""
    preview = response[:300] + "..." if len(response) > 300 else response
    logger.debug(f"[LLM Response] {purpose}:\n{preview}")


def log_llm_full_io(purpose: str, system_prompt: str, user_prompt: str, response: str, model: str = ""):
    """记录大模型完整出入参"""
    sep = "-" * 60
    logger.info(
        f"[LLM Full IO] {purpose} | model={model}\n"
        f"{sep}\n"
        f"  >>> 入参 - System Prompt ({len(system_prompt)} chars):\n{system_prompt}\n"
        f"{sep}\n"
        f"  >>> 入参 - User Prompt ({len(user_prompt)} chars):\n{user_prompt}\n"
        f"{sep}\n"
        f"  >>> 出参 - Response ({len(response)} chars):\n{response}\n"
        f"{sep}"
    )


def log_api_call(api_name: str, method: str, url: str, status_code: int = 0, duration: float = 0, detail: str = ""):
    """记录 API 调用"""
    msg = f"[API] {method} {url} | status={status_code} | duration={duration:.1f}s"
    if detail:
        msg += f" | {detail}"
    logger.info(msg)


def log_api_full_io(api_name: str, method: str, url: str, request_body: dict, response_body: str, status_code: int = 0):
    """记录 API 完整出入参"""
    sep = "-" * 60
    try:
        req_str = json.dumps(request_body, ensure_ascii=False, indent=2)
    except Exception:
        req_str = str(request_body)
    logger.info(
        f"[API Full IO] {api_name} | {method} {url} | status={status_code}\n"
        f"{sep}\n"
        f"  >>> 入参 - Request Body:\n{req_str}\n"
        f"{sep}\n"
        f"  >>> 出参 - Response Body:\n{response_body}\n"
        f"{sep}"
    )


def log_image_gen(purpose: str, model: str, prompt_len: int, output_path: str = "", duration: float = 0):
    """记录图片生成"""
    logger.info(
        f"[IMAGE] {purpose} | model={model} | "
        f"prompt={prompt_len}chars | output={output_path} | "
        f"duration={duration:.1f}s"
    )


def log_video_gen(scene_id: str, image_path: str, duration: int, prompt_id: str = "", elapsed: float = 0):
    """记录视频生成"""
    logger.info(
        f"[VIDEO] scene={scene_id} | image={image_path} | "
        f"duration={duration}s | prompt_id={prompt_id} | "
        f"elapsed={elapsed:.1f}s"
    )


def log_error(module: str, error: str, detail: str = ""):
    """记录错误"""
    msg = f"[ERROR] {module}: {error}"
    if detail:
        msg += f"\n  Detail: {detail}"
    logger.error(msg)


def log_warn(module: str, message: str):
    """记录警告"""
    logger.warning(f"[WARN] {module}: {message}")


def log_info(message: str):
    """记录普通信息"""
    logger.info(message)


def log_debug(message: str):
    """记录调试信息"""
    logger.debug(message)