"""豆包 Seedream 图片生成客户端（Ark API）"""
import os
import time
import base64
import requests
from config import (
    ARK_API_KEY, ARK_IMAGE_MODEL, ARK_IMAGE_ENDPOINT,
    AGNES_API_KEY, AGNES_IMAGE_MODEL, AGNES_IMAGE_ENDPOINT,
    IMAGE_ENGINE
)
from logger import log_step, log_image_gen, log_api_call, log_api_full_io, log_error, log_debug


def generate_image(prompt: str, reference_image_path: str = None, output_path: str = None, aspect_ratio: str = "16:9", engine: str = None) -> str:
    """
    调用图片生成模型生成图片

    Args:
        prompt: 图片提示词
        reference_image_path: 参考角色图路径（可选）
        output_path: 输出图片保存路径
        aspect_ratio: 画幅比例 "16:9" 或 "9:16"
        engine: 指定引擎（"agnes"/"doubao"），不传则使用 IMAGE_ENGINE 配置

    Returns:
        生成的图片路径
    """
    current = (engine or IMAGE_ENGINE) if engine or IMAGE_ENGINE else "doubao"
    if current == "agnes":
        return generate_image_agnes(prompt=prompt, reference_image_path=reference_image_path, output_path=output_path, aspect_ratio=aspect_ratio)
    else:
        # 默认使用豆包 Seedream
        return generate_image_seedream(prompt=prompt, reference_image_path=reference_image_path, output_path=output_path, aspect_ratio=aspect_ratio)


def generate_image_seedream(prompt: str, reference_image_path: str = None, output_path: str = None, aspect_ratio: str = "16:9") -> str:
    """
    调用豆包 Seedream 模型生成图片

    Args:
        prompt: 图片提示词
        reference_image_path: 参考角色图路径（可选）
        output_path: 输出图片保存路径
        aspect_ratio: 画幅比例 "16:9" 或 "9:16"

    Returns:
        生成的图片路径
    """
    t0 = time.time()

    # 根据画幅设置尺寸（方式 2：宽高像素）
    if aspect_ratio == "9:16":
        width, height = 2160, 3840
    else:
        width, height = 3840, 2160

    log_step("图片生成", "开始", f"model={ARK_IMAGE_MODEL} | size={width}x{height} | output={output_path} | prompt_len={len(prompt)}")
    log_debug(f"图片提示词: {prompt[:500]}...")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ARK_API_KEY}",
    }

    body = {
        "model": ARK_IMAGE_MODEL,
        "prompt": prompt,
        "sequential_image_generation": "disabled",
        "response_format": "url",
        "size": f"{width}x{height}",
        "stream": False,
        "watermark": False,
    }

    try:
        response = requests.post(
            ARK_IMAGE_ENDPOINT,
            headers=headers,
            json=body,
            timeout=3600,
        )
    except Exception as e:
        log_error("Seedream", f"API 请求失败: {str(e)}")
        raise

    elapsed_api = time.time() - t0
    log_api_call(
        api_name="Seedream",
        method="POST",
        url=ARK_IMAGE_ENDPOINT,
        status_code=response.status_code,
        duration=elapsed_api,
    )

    if response.status_code != 200:
        log_api_full_io(
            api_name="Seedream",
            method="POST",
            url=ARK_IMAGE_ENDPOINT,
            request_body=body,
            response_body=response.text,
            status_code=response.status_code,
        )
        log_error("Seedream", f"status={response.status_code}", response.text[:500])
        raise Exception(f"图片生成 API 调用失败: {response.status_code} - {response.text}")

    result = response.json()
    log_api_full_io(
        api_name="Seedream",
        method="POST",
        url=ARK_IMAGE_ENDPOINT,
        request_body=body,
        response_body=response.text,
        status_code=response.status_code,
    )
    data_list = result.get("data", [])
    if not data_list:
        log_error("Seedream", "返回 data 为空", str(result))
        raise Exception(f"API 返回数据异常: {result}")

    image_url = data_list[0].get("url", "")
    if not image_url:
        log_error("Seedream", "未获取到图片 URL", str(result))
        raise Exception(f"未获取到图片 URL: {result}")

    log_debug(f"获取到图片 URL: {image_url[:100]}...")

    # 下载图片
    try:
        img_response = requests.get(image_url, timeout=3600)
    except Exception as e:
        log_error("Seedream", f"图片下载失败: {str(e)}")
        raise

    if output_path and img_response.status_code == 200:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(img_response.content)
        elapsed_total = time.time() - t0
        file_size = os.path.getsize(output_path)
        log_image_gen(
            purpose="生成图片",
            model=ARK_IMAGE_MODEL,
            prompt_len=len(prompt),
            output_path=output_path,
            duration=elapsed_total,
        )
        log_step("图片生成", "完成", f"output={output_path} | size={file_size}bytes | elapsed={elapsed_total:.1f}s")
        return output_path

    raise Exception(f"图片下载失败: {img_response.status_code}")


def generate_image_agnes(prompt: str, reference_image_path: str = None, output_path: str = None, aspect_ratio: str = "16:9") -> str:
    """
    调用 Agnes AI 模型生成图片（支持文生图和图生图）

    Args:
        prompt: 图片提示词
        reference_image_path: 参考角色图路径（图生图模式时使用）
        output_path: 输出图片保存路径
        aspect_ratio: 画幅比例 "16:9" 或 "9:16"

    Returns:
        生成的图片路径
    """
    t0 = time.time()

    # 自动检测模式: 有参考图则用图生图，否则文生图
    use_img2img = reference_image_path and os.path.exists(reference_image_path)
    mode = "image2image" if use_img2img else "text2image"

    # 根据画幅比例设置尺寸
    if aspect_ratio == "9:16":
        width, height = 1080, 1920
    else:
        width, height = 1920, 1280

    log_step("Agnes 图片生成", "开始", f"model={AGNES_IMAGE_MODEL} | mode={mode} | size={width}x{height} | output={output_path} | prompt_len={len(prompt)}")
    log_debug(f"图片提示词: {prompt[:500]}...")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AGNES_API_KEY}",
    }

    # 文生图模式（agnes-image-2.1-flash）— 不支持 response_format
    if mode == "text2image":
        body = {
            "model": AGNES_IMAGE_MODEL,
            "prompt": prompt,
            "size": f"{width}x{height}",
        }
    else:
        # 图生图模式（agnes-image-2.0-flash）
        image_url = None
        if reference_image_path and os.path.exists(reference_image_path):
            # 上传本地图片获取 URL（使用 data URI）
            try:
                with open(reference_image_path, "rb") as f:
                    image_data = f.read()
                ext = os.path.splitext(reference_image_path)[1].lower()
                mime = "image/png" if ext == ".png" else "image/jpeg"
                image_b64 = base64.b64encode(image_data).decode("utf-8")
                image_url = f"data:{mime};base64,{image_b64}"
            except Exception as e:
                log_error("Agnes", f"读取参考图片失败: {str(e)}")
                raise
        elif reference_image_path:
            # 如果已经是 URL
            image_url = reference_image_path

        if not image_url:
            raise Exception("图生图模式需要提供 reference_image_path")

        body = {
            "model": "agnes-image-2.0-flash",
            "prompt": prompt,
            "size": f"{width}x{height}",
            "extra_body": {
                "tags": ["img2img"],
                "image": [image_url],
                "response_format": "url",
            },
        }

    try:
        response = requests.post(
            AGNES_IMAGE_ENDPOINT,
            headers=headers,
            json=body,
            timeout=3600,
        )
    except Exception as e:
        log_error("Agnes", f"API 请求失败: {str(e)}")
        raise

    elapsed_api = time.time() - t0
    log_api_call(
        api_name="Agnes",
        method="POST",
        url=AGNES_IMAGE_ENDPOINT,
        status_code=response.status_code,
        duration=elapsed_api,
    )

    if response.status_code != 200:
        log_api_full_io(
            api_name="Agnes",
            method="POST",
            url=AGNES_IMAGE_ENDPOINT,
            request_body=body,
            response_body=response.text,
            status_code=response.status_code,
        )
        log_error("Agnes", f"status={response.status_code}", response.text[:500])
        raise Exception(f"Agnes 图片生成 API 调用失败: {response.status_code} - {response.text}")

    result = response.json()
    log_api_full_io(
        api_name="Agnes",
        method="POST",
        url=AGNES_IMAGE_ENDPOINT,
        request_body=body,
        response_body=response.text,
        status_code=response.status_code,
    )

    # 解析 OpenAI 兼容格式响应: data 是列表
    data_list = result.get("data", [])
    image_url = data_list[0].get("url", "") if data_list else (result.get("url") or "")
    if not image_url:
        log_error("Agnes", "未获取到图片 URL", str(result))
        raise Exception(f"未获取到图片 URL: {result}")

    # 修复 URL：某些情况下返回的 URL 缺少 scheme
    if image_url and not image_url.startswith("http://") and not image_url.startswith("https://"):
        image_url = "https://" + image_url

    log_debug(f"获取到图片 URL: {image_url[:100]}...")

    # 下载图片
    try:
        img_response = requests.get(image_url, timeout=3600)
    except Exception as e:
        log_error("Agnes", f"图片下载失败: {str(e)}")
        raise

    if output_path and img_response.status_code == 200:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(img_response.content)
        elapsed_total = time.time() - t0
        file_size = os.path.getsize(output_path)
        log_image_gen(
            purpose="生成图片",
            model=AGNES_IMAGE_MODEL,
            prompt_len=len(prompt),
            output_path=output_path,
            duration=elapsed_total,
        )
        log_step("Agnes 图片生成", "完成", f"output={output_path} | size={file_size}bytes | elapsed={elapsed_total:.1f}s")
        return output_path

    raise Exception(f"图片下载失败: {img_response.status_code}")


def generate_image_by_prompt(prompt: str, output_path: str, reference_image_path: str = None, aspect_ratio: str = "16:9", engine: str = None) -> str:
    """便捷方法：根据提示词生成图片并保存到指定路径"""
    return generate_image(prompt=prompt, reference_image_path=reference_image_path, output_path=output_path, aspect_ratio=aspect_ratio, engine=engine)
