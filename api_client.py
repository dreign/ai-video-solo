"""DeepSeek / Ark LLM API 客户端封装"""
import json
import os
import time
import requests as req
from openai import OpenAI
from config import TEXT_ENGINE, DEEPSEEK_API_KEY, DEEPSEEK_API_BASE, DEEPSEEK_MODEL, ARK_API_KEY, ARK_TEXT_MODEL, ARK_TEXT_ENDPOINT
from logger import log_llm_call, log_llm_response, log_llm_full_io, log_error, log_debug
from prompt import (
    SCRIPT_SYSTEM_PROMPT_STORY,
    SCRIPT_SYSTEM_PROMPT_QUAD,
    SCRIPT_SYSTEM_PROMPT_FPV,
    STORYBOARD_SYSTEM_PROMPT,
    CHARACTER_EXTRACT_SYSTEM_PROMPT,
    IMG_PROMPT_SYSTEM,
)

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_API_BASE,
)


def _get_current_model() -> str:
    """获取当前使用的模型名"""
    if TEXT_ENGINE == "ark":
        return ARK_TEXT_MODEL
    return DEEPSEEK_MODEL


def call_deepseek(system_prompt: str, user_prompt: str, temperature: float = 0.7, purpose: str = "chat") -> str:
    """调用 LLM API（根据 TEXT_ENGINE 自动选择引擎）"""
    if TEXT_ENGINE == "ark":
        return _call_ark_deepseek(system_prompt, user_prompt, temperature, purpose)
    return _call_deepseek_direct(system_prompt, user_prompt, temperature, purpose)


def _call_deepseek_direct(system_prompt: str, user_prompt: str, temperature: float = 0.7, purpose: str = "chat") -> str:
    """调用 DeepSeek 官方 API（OpenAI 兼容格式）"""
    t0 = time.time()

    try:
        response = client.chat.completions.create(
            model=_get_current_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=8192,
        )
    except Exception as e:
        log_error("DeepSeek", str(e))
        raise

    elapsed = time.time() - t0
    content = response.choices[0].message.content
    usage = response.usage
    log_llm_call(
        model=_get_current_model(),
        purpose=purpose,
        prompt_len=usage.prompt_tokens if usage else 0,
        response_len=usage.completion_tokens if usage else len(content),
        duration=elapsed,
    )
    log_llm_response(purpose, content)
    log_llm_full_io(
        purpose=purpose,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response=content,
        model=_get_current_model(),
    )
    return content


def _call_ark_deepseek(system_prompt: str, user_prompt: str, temperature: float = 0.7, purpose: str = "chat") -> str:
    """调用豆包 Ark DeepSeek API（Responses API 格式）"""
    t0 = time.time()

    url = ARK_TEXT_ENDPOINT
    headers = {
        "Authorization": f"Bearer {ARK_API_KEY}",
        "Content-Type": "application/json",
    }

    body = {
        "model": ARK_TEXT_MODEL,
        "stream": False,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
        ],
    }

    try:
        resp = req.post(url, headers=headers, json=body, timeout=120)
    except Exception as e:
        log_error("Ark DeepSeek", str(e))
        raise

    if resp.status_code != 200:
        log_error("Ark DeepSeek", f"HTTP {resp.status_code}", resp.text[:1000])
        raise Exception(f"Ark DeepSeek API 调用失败: {resp.status_code} - {resp.text}")

    result = resp.json()
    elapsed = time.time() - t0
    log_llm_full_io(
        purpose=purpose,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response=json.dumps(result, ensure_ascii=False),
        model=ARK_TEXT_MODEL,
    )

    # 解析 Ark Responses API 格式
    content = ""
    output = result.get("output", [])
    for item in output:
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    content += c.get("text", "")

    if not content:
        log_error("Ark DeepSeek", "响应中未找到输出文本", str(result)[:500])
        raise Exception(f"Ark DeepSeek 响应格式异常: {result}")

    log_llm_call(
        model=ARK_TEXT_MODEL,
        purpose=purpose,
        prompt_len=len(system_prompt) + len(user_prompt),
        response_len=len(content),
        duration=elapsed,
    )
    log_llm_response(purpose, content)
    return content


# ============ 剧本生成相关 ============

SCRIPT_OPTIONS = {
    "1": {
        "name": "小故事（情感类）",
        "system_prompt": SCRIPT_SYSTEM_PROMPT_STORY,
        "user_prompt_template": "创意内容：{creative}",
    },
    "2": {
        "name": "四联故事（情感类）",
        "system_prompt": SCRIPT_SYSTEM_PROMPT_QUAD,
        "user_prompt_template": "参考创意：{creative}",
    },
    "3": {
        "name": "穿梭机（风景类）",
        "system_prompt": SCRIPT_SYSTEM_PROMPT_FPV,
        "user_prompt_template": "创意内容：{creative}",
    },
}


def generate_script(creative: str, option_id: str, aspect_ratio: str = "16:9") -> str:
    """根据创意、选项和画幅比例生成剧本"""
    option = SCRIPT_OPTIONS.get(option_id, SCRIPT_OPTIONS["1"])
    user_prompt = option["user_prompt_template"]
    user_prompt = user_prompt.replace("{aspect_ratio}", aspect_ratio)
    user_prompt = user_prompt.replace("{creative}", creative)
    purpose = f"生成剧本 [{option['name']}]"
    log_llm_call(model=_get_current_model(), purpose=purpose, prompt_len=len(user_prompt), response_len=0)
    return call_deepseek(option["system_prompt"], user_prompt, purpose=purpose)


# ============ 分镜生成相关 ============

STORYBOARD_USER_PROMPT = """请根据以下剧本生成分镜脚本，以JSON数组格式返回。

【画幅比例】{aspect_ratio}

【输出格式】
严格JSON数组，每个元素含：
- group_id: 场景编号，如"001"
- scene_id: 分镜编号，如"001"
- desc: 分镜标题
- duration: 整数秒数
- prompt_img_start: 首帧图提示词（生成时留空）
- prompt_img_end: 尾帧图提示词（生成时留空）
- prompt_video: 视频提示词
- narration: 对白/旁白（中文原文）
- img_start: 首帧图路径（生成时留空）
- img_end: 尾帧图路径（生成时留空）
- video: 视频路径（生成时留空）
- name_en_list: 角色英文名数组，同一角色多年龄段用_young/_old后缀区分，无原生英文名用拼音+下划线命名。

【注意事项】
- group_id/scene_id 用3位数字，如"001"
- duration 为整数
- 直接返回JSON数组，不要markdown代码块标记

【剧本内容】
{script}"""


def generate_storyboard(script: str, aspect_ratio: str = "16:9") -> str:
    """根据剧本和画幅比例生成分镜脚本"""
    system_prompt = STORYBOARD_SYSTEM_PROMPT.replace("{aspect_ratio}", aspect_ratio)
    user_prompt = STORYBOARD_USER_PROMPT.replace("{aspect_ratio}", aspect_ratio)
    user_prompt = user_prompt.replace("{script}", script)
    purpose = "生成分镜脚本"
    log_llm_call(model=_get_current_model(), purpose=purpose, prompt_len=len(user_prompt), response_len=0)
    return call_deepseek(system_prompt, user_prompt, temperature=0.5, purpose=purpose)


# ============ 角色提取相关 ============

CHARACTER_EXTRACT_PROMPT = """【画幅比例】{aspect_ratio}

【分镜脚本】
{storyboard}

请从以上分镜脚本中提取角色，按System Prompt指定的格式返回JSON数组。"""


def extract_characters(storyboard_json: str, aspect_ratio: str = "16:9") -> str:
    """从分镜脚本中提取角色"""
    user_prompt = CHARACTER_EXTRACT_PROMPT.replace("{aspect_ratio}", aspect_ratio)
    user_prompt = user_prompt.replace("{storyboard}", storyboard_json)
    purpose = "提取角色"
    log_llm_call(model=_get_current_model(), purpose=purpose, prompt_len=len(user_prompt), response_len=0)
    return call_deepseek(
        CHARACTER_EXTRACT_SYSTEM_PROMPT,
        user_prompt,
        temperature=0.5,
        purpose=purpose,
    )


# ============ 分镜首帧图提示词生成 ============

IMG_PROMPT_USER = """【画幅比例】{aspect_ratio}

【视频提示词】
{prompt_video}

请提取首帧静态视觉要素，生成同风格同画幅的绘图提示词。"""


def generate_img_prompt(prompt_video: str, aspect_ratio: str = "16:9") -> str:
    """根据视频提示词和画幅比例生成首帧图提示词"""
    user_prompt = IMG_PROMPT_USER.replace("{aspect_ratio}", aspect_ratio)
    user_prompt = user_prompt.replace("{prompt_video}", prompt_video)
    purpose = "生成首帧图提示词"
    log_llm_call(model=_get_current_model(), purpose=purpose, prompt_len=len(user_prompt), response_len=0)
    return call_deepseek(IMG_PROMPT_SYSTEM, user_prompt, temperature=0.5, purpose=purpose)


def parse_json_response(response: str) -> list:
    """解析 DeepSeek 返回的 JSON 响应"""
    import re
    from logger import log_debug, log_warn

    text = response.strip()
    log_debug(f"解析 JSON 响应，原始长度: {len(text)} chars")

    # 尝试提取 markdown 代码块中的 JSON
    code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if code_block:
        text = code_block.group(1).strip()
        log_debug("检测到 markdown 代码块，已提取 JSON 内容")

    # 尝试找到 JSON 数组的起始位置
    bracket_start = text.find("[")
    bracket_end = text.rfind("]")
    if bracket_start >= 0 and bracket_end > bracket_start:
        text = text[bracket_start:bracket_end + 1]
        log_debug(f"截取 JSON 数组: [{bracket_start}:{bracket_end + 1}]")
    else:
        log_warn("parse_json", "未找到 JSON 数组标记 [ ]")

    result = json.loads(text)
    log_debug(f"JSON 解析成功，共 {len(result)} 条记录")
    return result