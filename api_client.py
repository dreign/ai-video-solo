"""DeepSeek API 客户端封装"""
import json
import os
import time
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_BASE, DEEPSEEK_MODEL
from logger import log_llm_call, log_llm_response, log_llm_full_io, log_error

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_API_BASE,
)


def call_deepseek(system_prompt: str, user_prompt: str, temperature: float = 0.7, purpose: str = "chat") -> str:
    """调用 DeepSeek API 聊天补全"""
    t0 = time.time()

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
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
        model=DEEPSEEK_MODEL,
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
        model=DEEPSEEK_MODEL,
    )
    return content


# ============ 剧本生成相关 ============

SCRIPT_OPTIONS = {
    "1": {
        "name": "小故事（情感类）",
        "system_prompt": "你是一个专业的微短剧编剧，擅长将诗词改编为触达人心的微剧故事。",
        "user_prompt_template": "画幅比例为{aspect_ratio}，以人性为底层内核，以情绪表达为叙事骨架，把以下内容改编成一个触达人心的微剧小故事，使用抖音黄金3秒法则锁停留：\n\n{creative}",
    },
    "2": {
        "name": "四联故事（情感类）",
        "system_prompt": "你是一个专业的微短剧编剧，擅长将多首诗词融合改编为触达人心的微剧故事。",
        "user_prompt_template": "画幅比例为{aspect_ratio}，以人性为底层内核，以情绪表达为叙事骨架，选同一意境或感受或思想内核的四首著名诗词，改编成一个触达人心的微剧小故事，故事融入时代背景（可以用旁白），结合作者的亲身经历，并读出诗词最有代表性的名句。最后在情绪共振中收尾。使用抖音黄金3秒法则锁停留。\n\n参考创意：{creative}",
    },
    "3": {
        "name": "穿梭机（风景类）",
        "system_prompt": "你是一个专业的视频脚本编剧，擅长用无人机穿梭机POV视角描述宏大自然场景。",
        "user_prompt_template": "画幅比例为{aspect_ratio}，用无人机穿梭机的POV第一视角来详细构建出以下内容表达美景的详细描述，提取主角人物，能表现出主角在宏大的场景中的行动轨迹和情感变化。\n\n创意内容：{creative}",
    },
}


def generate_script(creative: str, option_id: str, aspect_ratio: str = "16:9") -> str:
    """根据创意、选项和画幅比例生成剧本"""
    option = SCRIPT_OPTIONS.get(option_id, SCRIPT_OPTIONS["1"])
    user_prompt = option["user_prompt_template"]
    user_prompt = user_prompt.replace("{aspect_ratio}", aspect_ratio)
    user_prompt = user_prompt.replace("{creative}", creative)
    purpose = f"生成剧本 [{option['name']}]"
    log_llm_call(model=DEEPSEEK_MODEL, purpose=purpose, prompt_len=len(user_prompt), response_len=0)
    return call_deepseek(option["system_prompt"], user_prompt, purpose=purpose)


# ============ 分镜生成相关 ============

STORYBOARD_SYSTEM_PROMPT = """你是一个专业的分镜师，严格按照规则将剧本转换为分镜脚本。

一、通用结构（必按顺序写，算法识别度最高）
画幅比例 + 整体风格 + 镜头机位 + 运镜方式 + 场景环境 + 完整人物外貌+服饰+神态 + 肢体动作+表情细节 + 光影色调 + 画质细节 + 约束限定。
1. 100%尊重原文：所有对话、剧情、人设、场景均来自原文，不新增、不删减、不魔改、不原创解读。
2. 分镜按空间，动作，情绪，结果来描述，长描述分层，避免冗长堆砌
3. 人物样貌、发型、衣着、神态每镜完整写入，杜绝形象跑偏，人物形象要适配时代背景
4. 动作写细微具象动态，不写抽象情绪词
5. 负面约束后置：人物面部不变形、肢体无扭曲、动作顺滑、无闪烁崩坏、画面稳定
6. 禁止出现代词他/她或参考某一分镜的描述
7. 列出场景，分镜编号，标题，时长

二、分段时序提示词规范写法（必须严格遵守）:
语言规范：除了"时间标记（如 0-3秒）"和"人物说话内容（如 女子中文说：你好）"使用中文外，其余所有视觉描述、技术参数、运镜及环境描述必须全部使用英文提示词。
分秒控制：分镜内必须使用 0-3秒，[英文内容] 的格式来划分镜头切换和动作流。
对话逻辑：必须按照时间顺序描述对话，格式为：某某人物说：[内容]。
时序对齐：确保动作、运镜、对话的时间轴（0-X秒）在逻辑上完全匹配。
场景拆分：同一场景的分镜合理分配，最长约15秒的分镜提示词中，时间区间的秒数是按剧本内容动态调整规划的，不是固定值，总时长略超或略短都是允许的。

基础分段书写规则：
1. 前缀统一固定：{aspect_ratio}，电影级超写实，8K超清
2. 先写明机位、时空、整体场景、人物固定样貌服饰（整镜不变形象只写一次）
3. 按时间节点拆分动作、神态、运镜变化
4. 保留画幅、风格、镜头、运镜、人物、场景、动作、光影、防崩坏约束，同画面内按时段拆分动态变化，保证人物形象全程统一；
5. 末尾统一加画质约束：面部稳定无变形，动作流畅，画面无闪烁崩坏，有音效，无配乐，无字幕

三、避坑优化技巧（提升出片成功率）
1. 人物优先原则：人脸、服饰放在场景动作前写，AI优先锁定人物形象，减少换脸、穿搭错乱
2. 动作描写要"轻"：古风历史镜头少写大幅度蹦跳奔跑，多用：缓步、伫立、俯身、抬手、凝望、轻声吟诵，适配模型动作逻辑
3. 时长对应运镜：短镜头用固定定镜、慢推；长镜头用平移、环绕、拉远
"""

STORYBOARD_USER_PROMPT = """请根据以下剧本生成分镜脚本，以JSON数组格式输出。每个分镜必须包含以下字段：

返回格式（严格JSON数组）：
[
  {
    "group_id": "001",
    "scene_id": "001",
    "desc": "分镜描述",
    "duration": 10,
    "prompt_img_start": "",
    "prompt_img_end": "",
    "prompt_video": "分镜视频提示词（英文为主，时间标记用中文）",
    "narration": "分镜对话/旁白",
    "img_start": "",
    "img_end": "",
    "video": "",
    "name_en_list": ["角色英文名列表"]
  }
]

注意：
- group_id 和 scene_id 使用3位数字如 "001", "002"
- duration 为整数秒数
- prompt_video 必须严格按照分镜规则编写
- name_en_list 是英文角色名列表，同一角色按年龄段分别命名，使用后缀区分：年轻时加 _young，老年时加 _old，中年成年不加后缀。例如：Li_Bai_young, Li_Bai_old, Li_Bai（中年/成年）。不区分年龄段的角色直接用原名，不加后缀。
- 直接返回JSON数组，不要包含markdown代码块标记

剧本如下：
{script}"""


def generate_storyboard(script: str, aspect_ratio: str = "16:9") -> str:
    """根据剧本和画幅比例生成分镜脚本"""
    system_prompt = STORYBOARD_SYSTEM_PROMPT.replace("{aspect_ratio}", aspect_ratio)
    user_prompt = STORYBOARD_USER_PROMPT.replace("{script}", script)
    purpose = "生成分镜脚本"
    log_llm_call(model=DEEPSEEK_MODEL, purpose=purpose, prompt_len=len(user_prompt), response_len=0)
    return call_deepseek(system_prompt, user_prompt, temperature=0.5, purpose=purpose)


# ============ 角色提取相关 ============

CHARACTER_EXTRACT_PROMPT = """从以下分镜脚本中提取角色形象的提示词，画幅比例为{aspect_ratio}，分别为每个人物面部特写搭配全身三视图组合画面，严格按照画面左侧放置超大尺寸人物面部特写，右侧依次排布正面全身照、侧面全身照、背面全身照，所有内容整合在同一画幅内。
严格复刻人物五官样貌、脸型轮廓、发型发色、身形比例、身高体态；完整还原全套服饰版型、色彩纹样、配饰穿戴、衣料褶皱细节；统一人物肤色、神态气质、画风光影。
画面平铺排版，采用纯白色背景，严格对齐人物人体比例，杜绝透视畸变问题，各视图之间间距均匀规整，细节高度一致，用作角色定型参考图。

请以JSON数组格式返回，每个角色包含：
[
  {
    "id": "001",
    "name_cn": "角色中文名",
    "name_en": "角色英文名",
    "prompt": "角色形象提示词（英文）",
    "img": ""
  }
]

注意：直接返回JSON数组，不要包含markdown代码块标记。
- 同一角色如有不同年龄段出现，必须分别提取，每个年龄段一条独立记录。
  例如：李白年轻时 name_en=Li_Bai_young，李白老年时 name_en=Li_Bai_old，李白中年/成年 name_en=Li_Bai。
  name_cn 也需体现年龄段，如 李白（青年）、李白（老年）。
  不同年龄段的 prompt 要分别描述该年龄段的五官、身形、服饰、神态特征。

分镜脚本如下：
{storyboard}"""


def extract_characters(storyboard_json: str, aspect_ratio: str = "16:9") -> str:
    """从分镜脚本中提取角色"""
    user_prompt = CHARACTER_EXTRACT_PROMPT.replace("{aspect_ratio}", aspect_ratio)
    user_prompt = user_prompt.replace("{storyboard}", storyboard_json)
    purpose = "提取角色"
    log_llm_call(model=DEEPSEEK_MODEL, purpose=purpose, prompt_len=len(user_prompt), response_len=0)
    return call_deepseek(
        "你是一个专业的角色设计专家，擅长从剧本中提取角色形象并生成角色定型提示词。",
        user_prompt,
        temperature=0.5,
        purpose=purpose,
    )


# ============ 分镜首帧图提示词生成 ============

IMG_PROMPT_SYSTEM = "你是一个专业的AI图片提示词专家，擅长从视频提示词中提取关键视觉信息，生成同风格同比例的首帧图片提示词。"

IMG_PROMPT_USER = """请根据以下分镜视频提示词，生成同风格同比例的分镜首帧图片的提示词。

要求：
1. 保留画幅比例（{aspect_ratio}）
2. 保留整体风格、光影色调
3. 提取初始场景和人物初始状态
4. 使用英文提示词
5. 直接返回提示词内容，不要带任何额外说明

视频提示词：
{prompt_video}"""


def generate_img_prompt(prompt_video: str, aspect_ratio: str = "16:9") -> str:
    """根据视频提示词和画幅比例生成首帧图提示词"""
    user_prompt = IMG_PROMPT_USER.replace("{aspect_ratio}", aspect_ratio)
    user_prompt = user_prompt.replace("{prompt_video}", prompt_video)
    purpose = "生成首帧图提示词"
    log_llm_call(model=DEEPSEEK_MODEL, purpose=purpose, prompt_len=len(user_prompt), response_len=0)
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