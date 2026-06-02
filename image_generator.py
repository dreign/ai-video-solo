"""豆包 Seedream 图片生成客户端（Ark API）"""
import os
import time
import requests
from config import ARK_API_KEY, ARK_IMAGE_MODEL, ARK_IMAGE_ENDPOINT
from logger import log_step, log_image_gen, log_api_call, log_api_full_io, log_error, log_debug


def generate_image(prompt: str, reference_image_path: str = None, output_path: str = None) -> str:
    """
    调用豆包 Seedream 模型生成图片

    Args:
        prompt: 图片提示词
        reference_image_path: 参考角色图路径（可选）
        output_path: 输出图片保存路径

    Returns:
        生成的图片路径
    """
    t0 = time.time()

    log_step("图片生成", "开始", f"model={ARK_IMAGE_MODEL} | output={output_path} | prompt_len={len(prompt)}")
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
        "size": "2K",
        "stream": False,
        "watermark": False,
    }

    try:
        response = requests.post(
            ARK_IMAGE_ENDPOINT,
            headers=headers,
            json=body,
            timeout=120,
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
        img_response = requests.get(image_url, timeout=60)
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


def generate_image_by_prompt(prompt: str, output_path: str) -> str:
    """便捷方法：根据提示词生成图片并保存到指定路径"""
    return generate_image(prompt=prompt, output_path=output_path)