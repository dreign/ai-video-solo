"""ComfyUI 视频生成客户端"""
import json
import os
import shutil
import time
from pathlib import Path
import requests
from config import COMFYUI_HOST, COMFYUI_OUTPUT_DIR, VIDEO_WORKFLOW_PATH, IMAGE_Z_IMAGE_TURBO_WORKFLOW_PATH
from logger import log_step, log_video_gen, log_api_call, log_api_full_io, log_error, log_debug, log_warn, log_info


def load_workflow(path: str) -> dict:
    """加载 ComfyUI 工作流 JSON"""
    log_debug(f"加载工作流: {path}")
    with open(path, "r", encoding="utf-8") as f:
        workflow = json.load(f)
    log_debug(f"工作流节点数: {len(workflow)}")
    return workflow


def upload_image_to_comfyui(image_path: str) -> str:
    """上传图片到 ComfyUI"""
    t0 = time.time()
    image_name = Path(image_path).name
    url = f"{COMFYUI_HOST}/upload/image"
    log_debug(f"上传图片到 ComfyUI: {image_path}")

    try:
        with open(image_path, "rb") as f:
            files = {"image": (image_name, f)}
            data = {"overwrite": "true"}
            response = requests.post(url, files=files, data=data, timeout=30)
    except Exception as e:
        log_error("ComfyUI", f"上传图片失败(网络): {str(e)}")
        raise

    log_api_call(api_name="ComfyUI", method="POST", url=url, status_code=response.status_code, duration=time.time() - t0)

    if response.status_code == 200:
        log_debug(f"图片上传成功: {image_name}")
        return image_name
    log_error("ComfyUI", f"上传图片失败", response.text[:500])
    raise Exception(f"上传图片失败: {response.text}")


def queue_prompt(prompt_dict: dict) -> str:
    """提交工作流到 ComfyUI 队列"""
    t0 = time.time()
    url = f"{COMFYUI_HOST}/prompt"
    log_debug(f"提交工作流到 ComfyUI，节点数: {len(prompt_dict)}")

    try:
        response = requests.post(url, json={"prompt": prompt_dict}, timeout=30)
    except Exception as e:
        log_error("ComfyUI", f"提交工作流失败(网络): {str(e)}")
        raise

    log_api_call(api_name="ComfyUI", method="POST", url=url, status_code=response.status_code, duration=time.time() - t0)

    if response.status_code == 200:
        prompt_id = response.json()["prompt_id"]
        log_api_full_io(
            api_name="ComfyUI",
            method="POST",
            url=url,
            request_body={"prompt": prompt_dict},
            response_body=response.text,
            status_code=response.status_code,
        )
        log_info(f"工作流已提交，prompt_id={prompt_id}")
        return prompt_id

    log_error("ComfyUI", "提交工作流失败", response.text[:500])
    raise Exception(f"提交工作流失败: {response.text}")


def get_history(prompt_id: str) -> dict:
    """获取工作流执行历史"""
    url = f"{COMFYUI_HOST}/history/{prompt_id}"
    response = requests.get(url, timeout=10)
    return response.json()


def wait_for_completion(prompt_id: str, timeout: int = 1800) -> dict:
    """等待工作流执行完成"""
    log_info(f"等待 ComfyUI 工作流完成，prompt_id={prompt_id}，超时={timeout}s")
    start_time = time.time()
    last_log_time = start_time

    while time.time() - start_time < timeout:
        try:
            history = get_history(prompt_id)
            if prompt_id in history:
                status = history[prompt_id].get("status", {})
                if status.get("completed", False):
                    elapsed = time.time() - start_time
                    log_info(f"工作流执行完成，prompt_id={prompt_id}，耗时={elapsed:.1f}s")
                    return history[prompt_id]
                if status.get("error", None):
                    log_error("ComfyUI", f"工作流执行错误", str(status["error"]))
                    raise Exception(f"执行错误: {status['error']}")

            # 每30秒输出一次等待状态
            if time.time() - last_log_time > 30:
                elapsed = time.time() - start_time
                log_info(f"工作流执行中... prompt_id={prompt_id}，已等待={elapsed:.0f}s")
                last_log_time = time.time()

        except Exception as e:
            if "执行错误" in str(e):
                raise
            log_warn("ComfyUI", f"检查状态异常: {str(e)}")

        time.sleep(5)

    log_error("ComfyUI", f"工作流执行超时 ({timeout}s)")
    raise TimeoutError(f"工作流执行超时 ({timeout}s)")


def get_latest_output(ext_patterns: list) -> Path:
    """获取 ComfyUI 输出目录中最新的输出文件"""
    comfy_output = Path(COMFYUI_OUTPUT_DIR)
    if not comfy_output.exists():
        log_warn("ComfyUI", f"输出目录不存在: {COMFYUI_OUTPUT_DIR}")
        return None
    files = []
    for ext in ext_patterns:
        files.extend(comfy_output.glob(f"*{ext}"))
    if not files:
        log_warn("ComfyUI", "输出目录中无匹配文件")
        return None
    latest = max(files, key=lambda x: x.stat().st_mtime)
    log_debug(f"最新输出文件: {latest}")
    return latest


def modify_video_workflow(workflow: dict, image_name: str, prompt: str, duration: int, output_prefix: str) -> dict:
    """修改 I2V 工作流参数"""
    log_debug(f"修改 I2V 工作流: image={image_name}, duration={duration}s, prefix={output_prefix}")
    log_debug(f"视频提示词长度: {len(prompt)} chars")

    modified = json.loads(json.dumps(workflow))

    changes = []

    # 设置输入图片
    if "269" in modified and modified["269"].get("class_type") == "LoadImage":
        old_img = modified["269"]["inputs"].get("image", "")
        modified["269"]["inputs"]["image"] = image_name
        changes.append(f"LoadImage: '{old_img}' -> '{image_name}'")

    # 设置正面提示词
    if "320:319" in modified and modified["320:319"].get("class_type") == "PrimitiveStringMultiline":
        modified["320:319"]["inputs"]["value"] = prompt
        changes.append(f"PositivePrompt: length={len(prompt)}")

    # 设置时长
    if "320:301" in modified and modified["320:301"].get("class_type") == "PrimitiveInt":
        old_dur = modified["320:301"]["inputs"].get("value", "")
        modified["320:301"]["inputs"]["value"] = duration
        changes.append(f"Duration: {old_dur} -> {duration}")

    # 设置输出前缀
    if "75" in modified and modified["75"].get("class_type") == "SaveVideo":
        old_prefix = modified["75"]["inputs"].get("filename_prefix", "")
        modified["75"]["inputs"]["filename_prefix"] = output_prefix
        changes.append(f"SaveVideo prefix: '{old_prefix}' -> '{output_prefix}'")

    log_debug(f"工作流修改完成: {', '.join(changes)}")
    return modified


def generate_video(
    image_path: str,
    prompt: str,
    duration: int,
    output_dir: str,
    scene_id: str,
) -> str:
    """
    生成视频

    Args:
        image_path: 首帧图片路径
        prompt: 视频提示词
        duration: 视频时长（秒）
        output_dir: 输出目录
        scene_id: 分镜ID

    Returns:
        生成的视频文件路径
    """
    t0 = time.time()
    log_step("视频生成", "开始", f"scene_id={scene_id} | image={image_path} | duration={duration}s | prompt_len={len(prompt)}")

    # 上传图片
    image_name = upload_image_to_comfyui(image_path)

    # 加载并修改工作流
    workflow = load_workflow(VIDEO_WORKFLOW_PATH)
    output_prefix = f"solo_video_{scene_id}"
    modified_workflow = modify_video_workflow(workflow, image_name, prompt, duration, output_prefix)

    # 提交任务
    prompt_id = queue_prompt(modified_workflow)
    log_video_gen(scene_id=scene_id, image_path=image_path, duration=duration, prompt_id=prompt_id)

    # 等待完成
    wait_for_completion(prompt_id)

    # 获取输出
    latest_video = get_latest_output([".mp4", ".webm", ".avi", ".mkv"])
    if latest_video:
        os.makedirs(output_dir, exist_ok=True)
        dest_path = os.path.join(output_dir, f"scene_{scene_id}{latest_video.suffix}")
        shutil.copy2(latest_video, dest_path)
        elapsed = time.time() - t0
        file_size = os.path.getsize(dest_path)
        log_step("视频生成", "完成", f"scene_id={scene_id} | output={dest_path} | size={file_size}bytes | elapsed={elapsed:.1f}s")
        return dest_path

    log_error("ComfyUI", "未找到生成的视频文件")
    raise Exception("未找到生成的视频文件")


# ============ Z-Image-Turbo 文生图 ============

def modify_z_image_workflow(workflow: dict, prompt: str, width: int, height: int, output_prefix: str) -> dict:
    """修改 Z-Image-Turbo 文生图工作流参数"""
    log_debug(f"修改 Z-Image 工作流: {width}x{height}, prefix={output_prefix}")

    import random as _random
    modified = json.loads(json.dumps(workflow))

    changes = []

    # 设置正面提示词 (CLIPTextEncode)
    if "57:27" in modified and modified["57:27"].get("class_type") == "CLIPTextEncode":
        modified["57:27"]["inputs"]["text"] = prompt
        changes.append(f"PositivePrompt: length={len(prompt)}")

    # 设置图片尺寸 (EmptySD3LatentImage)
    if "57:13" in modified and modified["57:13"].get("class_type") == "EmptySD3LatentImage":
        modified["57:13"]["inputs"]["width"] = width
        modified["57:13"]["inputs"]["height"] = height
        changes.append(f"Size: {width}x{height}")

    # 设置随机种子 (KSampler)
    if "57:3" in modified and modified["57:3"].get("class_type") == "KSampler":
        # 使用随机种子增加多样性
        modified["57:3"]["inputs"]["seed"] = _random.randint(0, 2**64 - 1)
        changes.append("Seed: randomized")

    # 设置输出前缀 (SaveImage)
    if "9" in modified and modified["9"].get("class_type") == "SaveImage":
        modified["9"]["inputs"]["filename_prefix"] = output_prefix
        changes.append(f"SaveImage prefix: '{output_prefix}'")

    log_debug(f"Z-Image 工作流修改完成: {', '.join(changes)}")
    return modified


def generate_image_via_comfyui(
    prompt: str,
    aspect_ratio: str,
    output_dir: str,
    scene_id: str,
) -> str:
    """
    通过 ComfyUI Z-Image-Turbo 生成图片

    Args:
        prompt: 图片提示词
        aspect_ratio: 画幅比例 "16:9" 或 "9:16"
        output_dir: 输出目录
        scene_id: 分镜ID

    Returns:
        生成的图片文件路径
    """
    t0 = time.time()
    log_step("Z-Image 文生图", "开始", f"scene_id={scene_id} | aspect={aspect_ratio} | prompt_len={len(prompt)}")

    # 根据画幅比例计算尺寸
    if aspect_ratio == "9:16":
        width, height = 1080, 1920
    else:
        width, height = 1920, 1080

    # 加载并修改工作流
    workflow = load_workflow(IMAGE_Z_IMAGE_TURBO_WORKFLOW_PATH)
    output_prefix = f"solo_img_{scene_id}"
    modified_workflow = modify_z_image_workflow(workflow, prompt, width, height, output_prefix)

    # 提交任务
    prompt_id = queue_prompt(modified_workflow)
    log_info(f"Z-Image 工作流已提交, scene_id={scene_id}, prompt_id={prompt_id}")

    # 等待完成
    wait_for_completion(prompt_id)

    # 获取输出
    latest_img = get_latest_output([".png", ".jpg", ".jpeg", ".webp"])
    if latest_img:
        os.makedirs(output_dir, exist_ok=True)
        dest_path = os.path.join(output_dir, f"scene_{scene_id}.png")
        shutil.copy2(latest_img, dest_path)
        elapsed = time.time() - t0
        file_size = os.path.getsize(dest_path)
        log_step("Z-Image 文生图", "完成", f"scene_id={scene_id} | output={dest_path} | size={file_size}bytes | elapsed={elapsed:.1f}s")
        return dest_path

    log_error("ComfyUI", "未找到生成的图片文件")
    raise Exception("未找到生成的图片文件")