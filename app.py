"""Flask 后端入口 - Solo 视频生成工具"""
import json
import os
import sys
import threading
import time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SOLO_DIR, PROJECTS_DIR, PROJECTS_INDEX, FLASK_HOST, FLASK_PORT, FLASK_DEBUG, IMAGE_ENGINE, VIDEO_ENGINE
from api_client import (
    generate_script,
    generate_storyboard,
    extract_characters,
    generate_img_prompt,
    parse_json_response,
    SCRIPT_OPTIONS,
)
from image_generator import generate_image_by_prompt
from video_generator import generate_video, generate_image_via_comfyui
from logger import (
    log_step, log_llm_call, log_api_call, log_error, log_warn, log_info, log_debug,
)
from jianying_export import create_jianying_draft
from video_queue import add_to_queue, get_queue, start_queue_worker


def generate_image_by_engine(prompt: str, aspect_ratio: str, output_dir: str, scene_id: str, reference_image_path: str = None, engine: str = None) -> str:
    """
    根据配置的 IMAGE_ENGINE 选择图片生成方式

    Args:
        prompt: 图片提示词
        aspect_ratio: 画幅比例 "16:9" 或 "9:16"
        output_dir: 输出目录
        scene_id: 场景/角色ID
        reference_image_path: 参考角色图路径（可选）
        engine: 指定使用的引擎，不传则使用 config.IMAGE_ENGINE

    Returns:
        生成的图片文件路径
    """
    output_path = os.path.join(output_dir, f"scene_{scene_id}.png")
    current_engine = engine or IMAGE_ENGINE

    if current_engine == "comfyui":
        log_debug(f"使用 ComfyUI 生成图片: scene_id={scene_id}")
        return generate_image_via_comfyui(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            output_dir=output_dir,
            scene_id=scene_id,
        )
    else:
        # 默认使用豆包 Seedream 或 Agnes
        log_debug(f"使用 {current_engine} 生成图片: scene_id={scene_id}")
        return generate_image_by_prompt(prompt=prompt, output_path=output_path, reference_image_path=reference_image_path, aspect_ratio=aspect_ratio, engine=current_engine)

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    log_error("全局异常", f"未处理的异常: {str(e)}\n{traceback.format_exc()}", "")
    return jsonify({"success": False, "error": str(e)}), 500

# ============ 项目路径管理 ============
current_project_id = None  # 当前活跃项目ID


def get_project_paths(project_id=None):
    """获取项目目录下各文件的完整路径，不传参则使用当前项目"""
    pid = project_id or current_project_id
    if not pid:
        return None
    base = os.path.join(PROJECTS_DIR, pid)
    return {
        "base": base,
        "creative": os.path.join(base, "创意.md"),
        "script": os.path.join(base, "剧本.md"),
        "storyboard": os.path.join(base, "分镜.json"),
        "character": os.path.join(base, "角色.json"),
        "option": os.path.join(base, "选项.json"),
        "storyboard_img": os.path.join(base, "分镜"),
        "character_img": os.path.join(base, "角色"),
        "video": os.path.join(base, "视频"),
    }


def load_projects_index():
    return read_json(PROJECTS_INDEX, [])


def save_projects_index(data):
    write_json(PROJECTS_INDEX, data)


def get_next_project_id():
    projects = load_projects_index()
    if not projects:
        return "P001"
    max_id = max(int(p["id"][1:]) for p in projects)
    return f"P{max_id + 1:03d}"


def create_project_dir(project_id):
    paths = get_project_paths(project_id)
    for d in [paths["base"], paths["storyboard_img"], paths["character_img"], paths["video"]]:
        os.makedirs(d, exist_ok=True)


# ============ 工具函数 ============
def read_file(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def read_json(path, default=None):
    if default is None:
        default = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    return default


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============ 请求日志中间件 ============
@app.before_request
def before_request():
    if request.path.startswith("/api/"):
        log_info(f"[HTTP] {request.method} {request.path}")


@app.after_request
def after_request(response):
    if request.path.startswith("/api/"):
        log_info(f"[HTTP] {request.method} {request.path} -> {response.status_code}")
    return response


# ============ 前端页面 ============
@app.route("/")
def index():
    return send_from_directory(SOLO_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(SOLO_DIR, filename)


# ============ 诗词库 API ============
@app.route("/api/poems/list", methods=["GET"])
def api_poems_list():
    """加载内置诗词库"""
    poems_path = os.path.join(SOLO_DIR, "poems.json")
    if not os.path.exists(poems_path):
        return jsonify({"poems": []})
    try:
        with open(poems_path, "r", encoding="utf-8") as f:
            poems = json.load(f)
        return jsonify({"poems": poems})
    except Exception as e:
        log_error("诗词库", str(e))
        return jsonify({"poems": []})


# ============ 项目管理 API ============
@app.route("/api/projects/list", methods=["GET"])
def api_projects_list():
    log_debug("获取项目列表")
    projects = load_projects_index()
    return jsonify({"projects": projects, "current_id": current_project_id})


@app.route("/api/projects/create", methods=["POST"])
def api_project_create():
    data = request.get_json()
    creative = data.get("creative", "")
    pid = get_next_project_id()
    name = creative[:20].replace("\n", " ").strip() or f"项目{pid}"
    create_project_dir(pid)

    # 保存创意
    paths = get_project_paths(pid)
    write_file(paths["creative"], creative)
    write_json(paths["option"], {
        "option_id": data.get("option_id", "1"),
        "option_name": SCRIPT_OPTIONS.get(data.get("option_id", "1"), {}).get("name", ""),
        "aspect_ratio": data.get("aspect_ratio", "16:9"),
    })

    # 更新索引
    projects = load_projects_index()
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    projects.append({"id": pid, "name": name, "creative_preview": creative[:20].replace("\n", " "), "created_at": now, "updated_at": now})
    save_projects_index(projects)

    # 切换为当前项目
    global current_project_id
    current_project_id = pid

    log_step("创建项目", "完成", f"id={pid} | name={name}")
    return jsonify({"success": True, "project": {"id": pid, "name": name}})


@app.route("/api/projects/load", methods=["POST"])
def api_project_load():
    data = request.get_json()
    pid = data.get("id", "")
    if not pid:
        return jsonify({"success": False, "error": "缺少项目ID"}), 400

    project_dir = os.path.join(PROJECTS_DIR, pid)
    if not os.path.isdir(project_dir):
        return jsonify({"success": False, "error": f"项目 {pid} 不存在"}), 404

    global current_project_id
    current_project_id = pid

    # 更新最近访问时间
    projects = load_projects_index()
    for p in projects:
        if p["id"] == pid:
            p["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            break
    save_projects_index(projects)

    log_step("加载项目", "完成", f"id={pid}")
    return jsonify({"success": True, "project_id": pid})


def _require_paths():
    """确保当前项目已设置，返回 paths 或 None"""
    paths = get_project_paths()
    if not paths:
        return None
    return paths


# ============ 创意页面 API ============
@app.route("/api/creative/save", methods=["POST"])
def save_creative():
    data = request.get_json()
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先创建或选择项目"}), 400

    creative = data.get("creative", "")
    option_id = data.get("option_id", "1")
    aspect_ratio = data.get("aspect_ratio", "16:9")
    art_style = data.get("art_style", "电影级超写实")

    log_step("保存创意", "执行", f"option={SCRIPT_OPTIONS.get(option_id, {}).get('name', '')} | 画幅={aspect_ratio} | 风格={art_style} | 创意长度={len(creative)}")
    write_file(paths["creative"], creative)
    write_json(paths["option"], {
        "option_id": option_id,
        "option_name": SCRIPT_OPTIONS.get(option_id, {}).get("name", ""),
        "aspect_ratio": aspect_ratio,
        "art_style": art_style,
    })
    log_info("创意已保存到 " + paths["creative"])

    return jsonify({"success": True, "message": "创意已保存"})


@app.route("/api/creative/load", methods=["GET"])
def load_creative():
    paths = _require_paths()
    if not paths:
        return jsonify({"creative": "", "option": {"option_id": "1", "option_name": "", "aspect_ratio": "16:9"}, "options": SCRIPT_OPTIONS})
    creative = read_file(paths["creative"])
    option = read_json(paths["option"], {"option_id": "1", "option_name": "", "aspect_ratio": "16:9"})
    return jsonify({"creative": creative, "option": option, "options": SCRIPT_OPTIONS, "project_id": current_project_id})


# ============ 剧本页面 API ============
@app.route("/api/script/generate", methods=["POST"])
def api_generate_script():
    t0 = time.time()
    data = request.get_json()
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先创建或选择项目"}), 400

    creative = data.get("creative", "")
    option_id = data.get("option_id", "1")
    aspect_ratio = data.get("aspect_ratio", "16:9")
    art_style = data.get("art_style", "电影级超写实")

    option_name = SCRIPT_OPTIONS.get(option_id, {}).get("name", option_id)
    log_step("生成剧本", "开始", f"option={option_name} | 画幅={aspect_ratio} | 风格={art_style} | 创意长度={len(creative)}")

    if not creative:
        log_warn("生成剧本", "创意为空")
        return jsonify({"success": False, "error": "请先输入创意"}), 400

    try:
        script = generate_script(creative, option_id, aspect_ratio)
        write_file(paths["script"], script)
        write_json(paths["option"], {
            "option_id": option_id,
            "option_name": SCRIPT_OPTIONS.get(option_id, {}).get("name", ""),
            "aspect_ratio": aspect_ratio,
            "art_style": art_style,
        })
        elapsed = time.time() - t0
        log_step("生成剧本", "完成", f"剧本长度={len(script)}chars | elapsed={elapsed:.1f}s")
        return jsonify({"success": True, "script": script})
    except Exception as e:
        log_error("生成剧本", str(e))
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/script/generate-stream", methods=["POST"])
def api_generate_script_stream():
    from flask import Response, stream_with_context
    import queue
    import time
    data = request.get_json()
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先创建或选择项目"}), 400

    creative = data.get("creative", "")
    option_id = data.get("option_id", "1")
    aspect_ratio = data.get("aspect_ratio", "16:9")
    art_style = data.get("art_style", "电影级超写实")

    option_name = SCRIPT_OPTIONS.get(option_id, {}).get("name", option_id)
    log_step("生成剧本(流式)", "开始", f"option={option_name} | 画幅={aspect_ratio} | 风格={art_style} | 创意长度={len(creative)}")

    if not creative:
        log_warn("生成剧本", "创意为空")
        return jsonify({"success": False, "error": "请先输入创意"}), 400

    option = SCRIPT_OPTIONS.get(option_id, SCRIPT_OPTIONS["1"])
    user_prompt = option["user_prompt_template"].replace("{aspect_ratio}", aspect_ratio).replace("{creative}", creative)

    result_queue = queue.Queue()

    def llm_thread():
        try:
            def stream_callback(chunk):
                result_queue.put(chunk)
            
            script = call_deepseek(option["system_prompt"], user_prompt, temperature=0.7, purpose="生成剧本", stream_callback=stream_callback)
            write_file(paths["script"], script)
            write_json(paths["option"], {
                "option_id": option_id,
                "option_name": SCRIPT_OPTIONS.get(option_id, {}).get("name", ""),
                "aspect_ratio": aspect_ratio,
                "art_style": art_style,
            })
            result_queue.put({"type": "done", "script": script})
        except Exception as e:
            log_error("生成剧本(流式)", str(e))
            result_queue.put({"type": "error", "error": str(e)})

    import threading
    thread = threading.Thread(target=llm_thread)
    thread.start()

    def generate():
        while True:
            try:
                chunk = result_queue.get(timeout=120)
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                time.sleep(0.01)
                if chunk["type"] == "done" or chunk["type"] == "error":
                    break
            except queue.Empty:
                break
    
    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )


@app.route("/api/script/load", methods=["GET"])
def load_script():
    paths = _require_paths()
    if not paths:
        return jsonify({"script": ""})
    script = read_file(paths["script"])
    log_debug(f"加载剧本: {len(script)} chars")
    return jsonify({"script": script})


@app.route("/api/script/save", methods=["POST"])
def save_script():
    data = request.get_json()
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先创建或选择项目"}), 400
    script = data.get("script", "")
    log_step("保存剧本", "执行", f"剧本长度={len(script)}")
    write_file(paths["script"], script)
    return jsonify({"success": True, "message": "剧本已保存"})


# ============ 分镜页面 API ============
@app.route("/api/storyboard/generate", methods=["POST"])
def api_generate_storyboard():
    t0 = time.time()
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先创建或选择项目"}), 400

    script = read_file(paths["script"])
    option = read_json(paths["option"], {"option_id": "1", "option_name": "", "aspect_ratio": "16:9"})
    aspect_ratio = option.get("aspect_ratio", "16:9")
    art_style = option.get("art_style", "电影级超写实")

    log_step("生成分镜", "开始", f"剧本长度={len(script)}chars | 画幅={aspect_ratio} | 风格={art_style}")

    if not script:
        log_warn("生成分镜", "剧本为空")
        return jsonify({"success": False, "error": "请先生成剧本"}), 400

    try:
        response = generate_storyboard(script, aspect_ratio, art_style)
        storyboard = parse_json_response(response)
        write_json(paths["storyboard"], storyboard)
        elapsed = time.time() - t0
        log_step("生成分镜", "完成", f"分镜数={len(storyboard)} | elapsed={elapsed:.1f}s")
        return jsonify({"success": True, "storyboard": storyboard})
    except Exception as e:
        log_error("生成分镜", str(e), f"原始响应前200字符: {(response if 'response' in dir() else 'N/A')}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/storyboard/load", methods=["GET"])
def load_storyboard():
    paths = _require_paths()
    if not paths:
        return jsonify({"storyboard": []})
    storyboard = read_json(paths["storyboard"])
    log_debug(f"加载分镜: {len(storyboard)} 条")
    return jsonify({"storyboard": storyboard})


@app.route("/api/storyboard/save", methods=["POST"])
def save_storyboard():
    data = request.get_json()
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先创建或选择项目"}), 400
    storyboard = data.get("storyboard", [])
    log_step("保存分镜", "执行", f"分镜数={len(storyboard)}")
    write_json(paths["storyboard"], storyboard)
    return jsonify({"success": True, "message": "分镜已保存"})


# ============ 角色页面 API ============
@app.route("/api/character/extract", methods=["POST"])
def api_extract_characters():
    t0 = time.time()
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先创建或选择项目"}), 400

    storyboard = read_json(paths["storyboard"])
    option = read_json(paths["option"], {"aspect_ratio": "16:9", "art_style": "电影级超写实"})
    aspect_ratio = option.get("aspect_ratio", "16:9")
    art_style = option.get("art_style", "电影级超写实")

    log_step("提取角色", "开始", f"分镜数={len(storyboard)} | 画幅={aspect_ratio} | 风格={art_style}")

    if not storyboard:
        log_warn("提取角色", "分镜为空")
        return jsonify({"success": False, "error": "请先生成分镜脚本"}), 400

    try:
        response = extract_characters(json.dumps(storyboard, ensure_ascii=False), aspect_ratio, art_style)
        characters = parse_json_response(response)
        write_json(paths["character"], characters)
        elapsed = time.time() - t0
        log_step("提取角色", "完成", f"角色数={len(characters)} | elapsed={elapsed:.1f}s")
        return jsonify({"success": True, "characters": characters})
    except Exception as e:
        log_error("提取角色", str(e))
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/character/load", methods=["GET"])
def load_characters():
    paths = _require_paths()
    if not paths:
        return jsonify({"characters": []})
    characters = read_json(paths["character"])
    log_debug(f"加载角色: {len(characters)} 个")
    return jsonify({"characters": characters})


@app.route("/api/character/save", methods=["POST"])
def api_save_characters():
    """保存角色数据"""
    data = request.get_json()
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先创建或选择项目"}), 400
    characters = data.get("characters", [])
    log_step("保存角色", "执行", f"角色数={len(characters)}")
    write_json(paths["character"], characters)
    return jsonify({"success": True, "message": "角色已保存"})


@app.route("/api/character/generate-images", methods=["POST"])
def api_generate_character_images():
    t0 = time.time()
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先创建或选择项目"}), 400

    characters = read_json(paths["character"])
    option = read_json(paths["option"], {"aspect_ratio": "16:9"})
    aspect_ratio = option.get("aspect_ratio", "16:9")

    log_step("生成角色图", "开始", f"角色数={len(characters)} | 画幅={aspect_ratio}")

    if not characters:
        log_warn("生成角色图", "角色列表为空")
        return jsonify({"success": False, "error": "请先提取角色"}), 400

    os.makedirs(paths["character_img"], exist_ok=True)

    results = []
    for char in characters:
        char_id = char.get("id", "?")
        if not char.get("prompt"):
            log_warn("生成角色图", f"角色 {char_id} 无提示词，跳过")
            results.append({"id": char_id, "status": "skip", "reason": "无提示词"})
            continue

        log_step("生成角色图", "执行", f"角色id={char_id} | name={char.get('name_cn', '?')}")
        try:
            img_path = generate_image_by_engine(
                prompt=char["prompt"],
                aspect_ratio=aspect_ratio,
                output_dir=paths["character_img"],
                scene_id=f"char_{char_id}",
            )
            char["img"] = img_path
            results.append({"id": char_id, "status": "success", "img": img_path})
        except Exception as e:
            log_error("生成角色图", str(e), f"角色id={char_id}")
            results.append({"id": char_id, "status": "error", "error": str(e)})

    write_json(paths["character"], characters)
    success_count = sum(1 for r in results if r["status"] == "success")
    elapsed = time.time() - t0
    log_step("生成角色图", "完成", f"成功={success_count}/{len(characters)} | elapsed={elapsed:.1f}s")
    return jsonify({"success": True, "results": results})


@app.route("/api/character/generate-image/<char_id>", methods=["POST"])
def api_generate_single_character_image(char_id):
    """重新生成单个角色图"""
    t0 = time.time()
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先创建或选择项目"}), 400

    characters = read_json(paths["character"])
    option = read_json(paths["option"], {"aspect_ratio": "16:9"})
    aspect_ratio = option.get("aspect_ratio", "16:9")

    char = None
    for c in characters:
        if c.get("id") == char_id:
            char = c
            break

    if not char:
        return jsonify({"success": False, "error": f"角色 {char_id} 不存在"}), 404
    if not char.get("prompt"):
        return jsonify({"success": False, "error": "角色无提示词"}), 400

    os.makedirs(paths["character_img"], exist_ok=True)

    log_step("重新生成角色图", "执行", f"角色id={char_id} | name={char.get('name_cn', '?')}")
    try:
        img_path = generate_image_by_engine(
            prompt=char["prompt"],
            aspect_ratio=aspect_ratio,
            output_dir=paths["character_img"],
            scene_id=f"char_{char_id}",
        )
        char["img"] = img_path
        write_json(paths["character"], characters)
        elapsed = time.time() - t0
        log_step("重新生成角色图", "完成", f"角色id={char_id} | elapsed={elapsed:.1f}s")
        return jsonify({"success": True, "img": img_path, "character": char})
    except Exception as e:
        log_error("重新生成角色图", str(e), f"角色id={char_id}")
        return jsonify({"success": False, "error": str(e)}), 500


# ============ 分镜首帧图提示词 API ============
@app.route("/api/storyboard/generate-img-prompts", methods=["POST"])
def api_generate_img_prompts():
    t0 = time.time()
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先创建或选择项目"}), 400

    storyboard = read_json(paths["storyboard"])
    option = read_json(paths["option"], {"aspect_ratio": "16:9", "art_style": "电影级超写实"})
    aspect_ratio = option.get("aspect_ratio", "16:9")
    art_style = option.get("art_style", "电影级超写实")

    log_step("生成首帧图提示词", "开始", f"分镜数={len(storyboard)} | 画幅={aspect_ratio} | 风格={art_style}")

    if not storyboard:
        log_warn("生成首帧图提示词", "分镜为空")
        return jsonify({"success": False, "error": "请先生成分镜脚本"}), 400

    results = []
    for scene in storyboard:
        scene_id = scene.get("scene_id", "?")
        prompt_video = scene.get("prompt_video", "")
        if not prompt_video:
            log_warn("生成首帧图提示词", f"分镜 {scene_id} 无视频提示词，跳过")
            results.append({"scene_id": scene_id, "status": "skip", "reason": "无视频提示词"})
            continue

        log_step("生成首帧图提示词", "执行", f"scene_id={scene_id}")
        try:
            img_prompt = generate_img_prompt(prompt_video, aspect_ratio, art_style)
            scene["prompt_img_start"] = img_prompt
            results.append({"scene_id": scene_id, "status": "success"})
        except Exception as e:
            log_error("生成首帧图提示词", str(e), f"scene_id={scene_id}")
            results.append({"scene_id": scene_id, "status": "error", "error": str(e)})

    write_json(paths["storyboard"], storyboard)
    success_count = sum(1 for r in results if r["status"] == "success")
    elapsed = time.time() - t0
    log_step("生成首帧图提示词", "完成", f"成功={success_count}/{len(storyboard)} | elapsed={elapsed:.1f}s")
    return jsonify({"success": True, "results": results, "storyboard": storyboard})


# ============ 分镜首帧图生成 API ============
@app.route("/api/storyboard/generate-images", methods=["POST"])
def api_generate_storyboard_images():
    t0 = time.time()
    try:
        paths = _require_paths()
        if not paths:
            return jsonify({"success": False, "error": "请先创建或选择项目"}), 400

        storyboard = read_json(paths["storyboard"])
        characters = read_json(paths["character"])
        option = read_json(paths["option"], {"aspect_ratio": "16:9", "art_style": "电影级超写实"})

        log_step("生成分镜首帧图", "开始", f"分镜数={len(storyboard)} | 角色数={len(characters)} | 风格={option.get('art_style', '电影级超写实')}")

        if not storyboard:
            log_warn("生成分镜首帧图", "分镜为空")
            return jsonify({"success": False, "error": "请先生成分镜脚本"}), 400

        os.makedirs(paths["storyboard_img"], exist_ok=True)

        char_img_map = {}
        for char in characters:
            if char.get("name_en") and char.get("img"):
                char_img_map[char["name_en"]] = char["img"]

        results = []
        for scene in storyboard:
            scene_id = scene.get("scene_id", "?")
            prompt_img = scene.get("prompt_img_start", "")

            if not prompt_img:
                results.append({"scene_id": scene_id, "status": "skip", "reason": "无首帧图提示词"})
                continue

            existing_img = scene.get("img_start", "")
            if existing_img and os.path.exists(existing_img):
                results.append({"scene_id": scene_id, "status": "skip", "reason": "首帧图已生成"})
                continue

            reference_img = None
            name_list = scene.get("name_en_list", [])
            for name_en in name_list:
                if name_en in char_img_map:
                    reference_img = char_img_map[name_en]
                    break

            log_step("生成分镜首帧图", "执行", f"scene_id={scene_id} | 关联角色={name_list} | 参考图={reference_img or '无'}")

            try:
                img_path = generate_image_by_engine(
                    prompt=prompt_img,
                    aspect_ratio=option.get("aspect_ratio", "16:9"),
                    output_dir=paths["storyboard_img"],
                    scene_id=scene_id,
                    reference_image_path=reference_img,
                )
                scene["img_start"] = img_path
                results.append({"scene_id": scene_id, "status": "success", "img": img_path})
            except Exception as e:
                log_error("生成分镜首帧图", str(e), f"scene_id={scene_id}")
                results.append({"scene_id": scene_id, "status": "error", "error": str(e)})

        write_json(paths["storyboard"], storyboard)
        success_count = sum(1 for r in results if r["status"] == "success")
        elapsed = time.time() - t0
        log_step("生成分镜首帧图", "完成", f"成功={success_count}/{len(storyboard)} | elapsed={elapsed:.1f}s")
        return jsonify({"success": True, "results": results, "storyboard": storyboard})
    
    except Exception as e:
        import traceback
        log_error("生成分镜首帧图", f"全局异常: {str(e)}\n{traceback.format_exc()}", "")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/storyboard/generate-image/<scene_id>", methods=["POST"])
def api_generate_single_storyboard_image(scene_id):
    """重新生成单个分镜的首帧图"""
    t0 = time.time()
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先创建或选择项目"}), 400

    storyboard = read_json(paths["storyboard"])
    characters = read_json(paths["character"])
    option = read_json(paths["option"], {"aspect_ratio": "16:9", "art_style": "电影级超写实"})

    scene = None
    for s in storyboard:
        if s.get("scene_id") == scene_id:
            scene = s
            break

    if not scene:
        return jsonify({"success": False, "error": f"分镜 {scene_id} 不存在"}), 404

    prompt_img = scene.get("prompt_img_start", "")
    if not prompt_img:
        return jsonify({"success": False, "error": "该分镜无首帧图提示词"}), 400

    # 查找关联角色图
    char_img_map = {}
    for char in characters:
        if char.get("name_en") and char.get("img"):
            char_img_map[char["name_en"]] = char["img"]

    reference_img = None
    name_list = scene.get("name_en_list", [])
    for name_en in name_list:
        if name_en in char_img_map:
            reference_img = char_img_map[name_en]
            break

    os.makedirs(paths["storyboard_img"], exist_ok=True)

    log_step("重新生成分镜首帧图", "执行", f"scene_id={scene_id} | 参考图={reference_img or '无'}")
    try:
        img_path = generate_image_by_engine(
            prompt=prompt_img,
            aspect_ratio=option.get("aspect_ratio", "16:9"),
            output_dir=paths["storyboard_img"],
            scene_id=scene_id,
            reference_image_path=reference_img,
        )
        scene["img_start"] = img_path
        write_json(paths["storyboard"], storyboard)
        elapsed = time.time() - t0
        log_step("重新生成分镜首帧图", "完成", f"scene_id={scene_id} | elapsed={elapsed:.1f}s")
        return jsonify({"success": True, "img": img_path, "scene": scene})
    except Exception as e:
        log_error("重新生成分镜首帧图", str(e), f"scene_id={scene_id}")
        return jsonify({"success": False, "error": str(e)}), 500


# ============ 分镜视频生成 API ============
@app.route("/api/storyboard/generate-videos", methods=["POST"])
def api_generate_storyboard_videos():
    """根据 VIDEO_ENGINE 生成视频：comfyui/doubao 同步处理，agnes 异步队列"""
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先创建或选择项目"}), 400

    storyboard = read_json(paths["storyboard"])

    log_step("生成分镜视频", "开始", f"分镜数={len(storyboard)}, engine={VIDEO_ENGINE}")

    if not storyboard:
        log_warn("生成分镜视频", "分镜为空")
        return jsonify({"success": False, "error": "请先生成分镜脚本"}), 400

    os.makedirs(paths["video"], exist_ok=True)

    # ========== Agnes 模式：异步队列 ==========
    if VIDEO_ENGINE == "agnes":
        results = []
        for scene in storyboard:
            scene_id = scene.get("scene_id", "?")
            img_start = scene.get("img_start", "")
            prompt_video = scene.get("prompt_video", "")
            duration = scene.get("duration", 10)

            if not img_start or not os.path.exists(img_start):
                log_warn("生成分镜视频", f"分镜 {scene_id} 无首帧图或文件不存在: {img_start}")
                results.append({"scene_id": scene_id, "status": "skip", "reason": "无首帧图"})
                continue

            if not prompt_video:
                log_warn("生成分镜视频", f"分镜 {scene_id} 无视频提示词")
                results.append({"scene_id": scene_id, "status": "skip", "reason": "无视频提示词"})
                continue

            # 检查是否已有 video_id 在队列中
            existing_video_id = scene.get("video_id", "")
            if existing_video_id:
                from video_queue import get_task
                existing_task = get_task(existing_video_id)
                if existing_task and existing_task.get("status") not in ("completed", "failed"):
                    results.append({"scene_id": scene_id, "status": "skip", "reason": "已在队列中", "video_id": existing_video_id})
                    continue
                else:
                    log_debug(f"分镜 {scene_id} 旧 video_id={existing_video_id} 不在活跃队列中，允许重新入队")
                    scene["video_id"] = ""

            log_step("生成分镜视频", "入队", f"scene_id={scene_id} | duration={duration}s (Agnes 异步)")
            try:
                fps = 24
                num_frames = int(duration * fps)
                remainder = (num_frames - 1) % 8
                if remainder != 0:
                    num_frames = num_frames + (8 - remainder)
                if num_frames > 441:
                    num_frames = 441
                if num_frames < 9:
                    num_frames = 9

                task = add_to_queue(
                    project_id=current_project_id,
                    scene_id=scene_id,
                    prompt=prompt_video,
                    image_path=img_start,
                    duration=duration,
                    output_dir=paths["video"],
                    num_frames=num_frames,
                    fps=fps,
                )
                scene["video_id"] = task["task_id"]
                results.append({"scene_id": scene_id, "status": "queued", "task_id": task["task_id"]})
            except Exception as e:
                log_error("生成分镜视频", str(e), f"scene_id={scene_id}")
                results.append({"scene_id": scene_id, "status": "error", "error": str(e)})

        write_json(paths["storyboard"], storyboard)
        queued_count = sum(1 for r in results if r["status"] == "queued")
        log_step("生成分镜视频", "入队完成", f"queued={queued_count}/{len(storyboard)}")
        return jsonify({"success": True, "results": results, "storyboard": storyboard})

    # ========== ComfyUI / 豆包 Seedance 模式：同步处理 ==========
    results = []
    for scene in storyboard:
        scene_id = scene.get("scene_id", "?")
        img_start = scene.get("img_start", "")
        prompt_video = scene.get("prompt_video", "")
        duration = scene.get("duration", 10)

        if not img_start or not os.path.exists(img_start):
            log_warn("生成分镜视频", f"分镜 {scene_id} 无首帧图或文件不存在: {img_start}")
            results.append({"scene_id": scene_id, "status": "skip", "reason": "无首帧图"})
            continue

        if not prompt_video:
            log_warn("生成分镜视频", f"分镜 {scene_id} 无视频提示词")
            results.append({"scene_id": scene_id, "status": "skip", "reason": "无视频提示词"})
            continue

        # 检查是否已有生成的视频
        existing_video = scene.get("video", "")
        if existing_video and os.path.exists(existing_video):
            log_debug(f"分镜 {scene_id} 已有视频，跳过: {existing_video}")
            results.append({"scene_id": scene_id, "status": "skipped", "reason": "已有视频"})
            continue

        log_step("生成分镜视频", "处理中", f"scene_id={scene_id} | duration={duration}s | engine={VIDEO_ENGINE}")
        try:
            from video_generator import generate_video
            video_path = generate_video(
                image_path=img_start,
                prompt=prompt_video,
                duration=duration,
                output_dir=paths["video"],
                scene_id=scene_id,
            )
            scene["video"] = video_path
            results.append({"scene_id": scene_id, "status": "completed", "path": video_path})
            log_step("生成分镜视频", "完成", f"scene_id={scene_id} | path={video_path}")
        except Exception as e:
            log_error("生成分镜视频", str(e), f"scene_id={scene_id}")
            results.append({"scene_id": scene_id, "status": "error", "error": str(e)})

    write_json(paths["storyboard"], storyboard)
    success_count = sum(1 for r in results if r["status"] == "completed")
    log_step("生成分镜视频", "全部完成", f"success={success_count}/{len(storyboard)}")
    return jsonify({"success": True, "results": results, "storyboard": storyboard})


@app.route("/api/video/queue", methods=["GET"])
def api_video_queue():
    """获取当前项目的视频生成队列状态"""
    queue = get_queue(project_id=current_project_id)
    log_debug(f"获取视频队列: {len(queue)} 个任务")
    return jsonify({"success": True, "queue": queue})


@app.route("/api/video/queue/<task_id>", methods=["DELETE"])
def api_remove_video_task(task_id):
    """从队列中移除任务"""
    log_step("移除视频任务", "执行", f"task_id={task_id}")
    from video_queue import remove_from_queue
    remove_from_queue(task_id)
    return jsonify({"success": True, "message": "任务已移除"})


@app.route("/api/video/check/<task_id>", methods=["GET"])
def api_check_video_task(task_id):
    """手动检查单个视频任务状态（查询 Agnes API）"""
    log_step("检查视频任务", "执行", f"task_id={task_id}")
    from video_queue import get_task, _query_agnes_video_task, update_task, _update_storyboard_video

    task = get_task(task_id)
    if not task:
        log_warn("检查视频任务", f"任务 {task_id} 不存在")
        return jsonify({"success": False, "error": "任务不存在"}), 404

    video_id = task.get("video_id", "")
    if not video_id:
        log_warn("检查视频任务", f"任务 {task_id} 尚未提交到 Agnes")
        return jsonify({"success": False, "error": "任务尚未提交到 Agnes"}), 400

    try:
        result = _query_agnes_video_task(video_id)
        api_status = result.get("status", "")
        log_debug(f"检查视频任务: task_id={task_id} | Agnes status={api_status}")

        if api_status == "completed":
            video_url = result.get("remixed_from_video_id") or result.get("video_url", "")
            if video_url:
                from video_queue import _download_video
                dest_path = os.path.join(task["output_dir"], f"scene_{task['scene_id']}.mp4")
                local_path = _download_video(video_url, dest_path)
                update_task(task_id, status="completed", video_url=video_url, local_path=local_path, completed_at=int(time.time()))
                _update_storyboard_video(task["project_id"], task["scene_id"], local_path, video_id)
                log_step("检查视频任务", "完成", f"task_id={task_id} | path={local_path}")
                return jsonify({"success": True, "status": "completed", "local_path": local_path})
            else:
                log_warn("检查视频任务", f"任务 {task_id} 完成但未获取到视频 URL")
                return jsonify({"success": True, "status": "completed", "warning": "未获取到视频 URL"})
        elif api_status == "failed":
            error_obj = result.get("error") or {}
            error_msg = error_obj.get("message", "") if isinstance(error_obj, dict) else str(error_obj)
            update_task(task_id, status="failed", error=error_msg)
            log_error("检查视频任务", f"任务 {task_id} 失败", error_msg)
            return jsonify({"success": True, "status": "failed", "error": error_msg})
        elif api_status == "in_progress":
            progress = result.get("progress", 0)
            update_task(task_id, status="generating")
            log_debug(f"视频生成中: task_id={task_id}, progress={progress}%")
            return jsonify({"success": True, "status": "in_progress", "progress": progress})
        elif api_status == "queued":
            log_debug(f"视频排队中: task_id={task_id}")
            return jsonify({"success": True, "status": "queued"})
        else:
            log_warn("检查视频任务", f"未知状态: task_id={task_id}, status={api_status}")
            return jsonify({"success": True, "status": api_status or "unknown"})
    except Exception as e:
        log_error("检查视频任务", str(e), f"task_id={task_id}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/video/regenerate/<scene_id>", methods=["POST"])
def api_regenerate_video(scene_id):
    """重新生成单个分镜视频：清除旧任务和video_id，重新入队"""
    log_step("视频重生成", "开始", f"scene_id={scene_id}")
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先创建或选择项目"}), 400

    storyboard = read_json(paths["storyboard"])
    scene = None
    scene_idx = -1
    for idx, s in enumerate(storyboard):
        if s.get("scene_id") == scene_id:
            scene = s
            scene_idx = idx
            break

    if not scene:
        log_warn("视频重生成", f"分镜 {scene_id} 不存在")
        return jsonify({"success": False, "error": f"分镜 {scene_id} 不存在"}), 404

    img_start = scene.get("img_start", "")
    prompt_video = scene.get("prompt_video", "")
    duration = scene.get("duration", 10)

    if not img_start or not os.path.exists(img_start):
        log_warn("视频重生成", f"分镜 {scene_id} 无首帧图或文件不存在")
        return jsonify({"success": False, "error": "该分镜无首帧图或文件不存在"}), 400
    if not prompt_video:
        log_warn("视频重生成", f"分镜 {scene_id} 无视频提示词")
        return jsonify({"success": False, "error": "该分镜无视频提示词"}), 400

    # 清除旧 video_id 和视频路径
    old_video_id = scene.get("video_id", "")
    if old_video_id:
        from video_queue import remove_from_queue
        remove_from_queue(old_video_id)
        log_debug(f"移除旧视频任务: {old_video_id}")

    scene["video_id"] = ""
    scene["video"] = ""
    write_json(paths["storyboard"], storyboard)

    # 重新入队
    try:
        fps = 24
        num_frames = int(duration * fps)
        remainder = (num_frames - 1) % 8
        if remainder != 0:
            num_frames = num_frames + (8 - remainder)
        if num_frames > 441:
            num_frames = 441
        if num_frames < 9:
            num_frames = 9

        task = add_to_queue(
            project_id=current_project_id,
            scene_id=scene_id,
            prompt=prompt_video,
            image_path=img_start,
            duration=duration,
            output_dir=paths["video"],
            num_frames=num_frames,
            fps=fps,
        )
        scene["video_id"] = task["task_id"]
        write_json(paths["storyboard"], storyboard)
        log_step("视频重生成", "入队", f"scene_id={scene_id} | task_id={task['task_id']}")
        return jsonify({"success": True, "task_id": task["task_id"], "scene_id": scene_id})
    except Exception as e:
        log_error("视频重生成", str(e), f"scene_id={scene_id}")
        return jsonify({"success": False, "error": str(e)}), 500


# ============ 视频页面 API ============
@app.route("/api/video/list", methods=["GET"])
def api_video_list():
    paths = _require_paths()
    if not paths:
        return jsonify({"videos": [], "total": 0})
    storyboard = read_json(paths["storyboard"])
    videos = []
    for scene in storyboard:
        if scene.get("video"):
            videos.append({
                "scene_id": scene["scene_id"],
                "desc": scene.get("desc", ""),
                "duration": scene.get("duration", 0),
                "video": scene["video"],
                "img_start": scene.get("img_start", ""),
            })
    log_debug(f"视频列表: {len(videos)} 个视频")
    return jsonify({"videos": videos, "total": len(videos)})


@app.route("/api/video/export-jianying", methods=["POST"])
def api_export_jianying():
    """导出剪映草稿"""
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先创建或选择项目"}), 400

    storyboard = read_json(paths["storyboard"])
    if not storyboard:
        return jsonify({"success": False, "error": "暂无分镜数据，无法导出"}), 400

    option = read_json(paths["option"], {"aspect_ratio": "16:9"})
    aspect_ratio = option.get("aspect_ratio", "16:9")

    # 获取项目名称
    projects = load_projects_index()
    project_name = current_project_id or "SOLO项目"
    for p in projects:
        if p["id"] == current_project_id:
            project_name = p.get("name", current_project_id)
            break

    # 输出到项目目录下的 jianying_draft 文件夹
    output_dir = os.path.join(paths["base"], "jianying_draft")
    os.makedirs(output_dir, exist_ok=True)

    log_step("导出剪映草稿", "开始", f"项目={project_name} | 分镜数={len(storyboard)}")
    try:
        draft_folder = create_jianying_draft(
            project_name=project_name,
            storyboard=storyboard,
            output_dir=output_dir,
            aspect_ratio=aspect_ratio
        )
        log_step("导出剪映草稿", "完成", f"路径={draft_folder}")
        return jsonify({
            "success": True,
            "message": "剪映草稿导出成功",
            "draft_folder": draft_folder,
            "draft_name": project_name
        })
    except Exception as e:
        log_error("导出剪映草稿", str(e))
        return jsonify({"success": False, "error": str(e)}), 500


# ============ 工具 API ============
@app.route("/api/media-url")
def api_media_url():
    """将本地绝对路径转为 web 可访问的相对 URL"""
    file_path = request.args.get("path", "")
    if not file_path:
        return jsonify({"success": False, "error": "缺少 path 参数"}), 400

    norm_abs = os.path.normpath(file_path)
    norm_base = os.path.normpath(SOLO_DIR)

    if os.path.commonpath([norm_abs, norm_base]) == norm_base:
        rel = os.path.relpath(norm_abs, norm_base).replace("\\", "/")
        log_debug(f"media-url: {file_path} -> /{rel}")
        return jsonify({"success": True, "url": "/" + rel})
    else:
        # 路径不在项目目录内，尝试通过 file:// 协议
        url_path = file_path.replace("\\", "/")
        log_debug(f"media-url: {file_path} -> file:///{url_path}")
        return jsonify({"success": True, "url": "file:///" + url_path})


@app.route("/api/open-file", methods=["POST"])
def api_open_file():
    """在文件资源管理器中打开文件所在目录并选中文件"""
    import subprocess
    data = request.get_json()
    file_path = data.get("path", "")
    if not file_path:
        return jsonify({"success": False, "error": "缺少 path 参数"}), 400

    # 如果传的是 web URL（以 / 开头），转为本地路径
    if file_path.startswith("/"):
        file_path = os.path.normpath(os.path.join(SOLO_DIR, file_path.lstrip("/")))

    if not os.path.exists(file_path):
        return jsonify({"success": False, "error": "文件不存在"}), 404

    log_step("打开文件", "执行", f"path={file_path}")
    try:
        subprocess.Popen(["explorer", "/select,", os.path.abspath(file_path)])
        return jsonify({"success": True})
    except Exception as e:
        log_error("打开文件", str(e))
        return jsonify({"success": False, "error": str(e)}), 500


# ============ 启动 ============

# ============ 设置 API ============
import config as app_config


def _get_config_values():
    """读取当前 config.py 中的配置值"""
    return {
        # 文本处理
        "text_engine": getattr(app_config, "TEXT_ENGINE", "agnes"),
        "deepseek_api_key": getattr(app_config, "DEEPSEEK_API_KEY", ""),
        "deepseek_api_base": getattr(app_config, "DEEPSEEK_API_BASE", ""),
        "deepseek_model": getattr(app_config, "DEEPSEEK_MODEL", ""),
        "ark_text_model": getattr(app_config, "ARK_TEXT_MODEL", ""),
        "ark_text_endpoint": getattr(app_config, "ARK_TEXT_ENDPOINT", ""),
        "agnes_api_key": getattr(app_config, "AGNES_API_KEY", ""),
        "agnes_api_base": getattr(app_config, "AGNES_API_BASE", ""),
        "agnes_text_model": getattr(app_config, "AGNES_TEXT_MODEL", ""),
        # 图片处理
        "image_engine": getattr(app_config, "IMAGE_ENGINE", "agnes"),
        "ark_api_key": getattr(app_config, "ARK_API_KEY", ""),
        "ark_image_model": getattr(app_config, "ARK_IMAGE_MODEL", "doubao-seedream-4-5-251128"),
        "ark_image_endpoint": getattr(app_config, "ARK_IMAGE_ENDPOINT", ""),
        "comfyui_host": getattr(app_config, "COMFYUI_HOST", ""),
        "comfyui_output_dir": getattr(app_config, "COMFYUI_OUTPUT_DIR", ""),
        "comfyui_image_workflow": getattr(app_config, "COMFYUI_IMAGE_WORKFLOW", ""),
        "agnes_image_model": getattr(app_config, "AGNES_IMAGE_MODEL", ""),
        "agnes_image_endpoint": getattr(app_config, "AGNES_IMAGE_ENDPOINT", ""),
        # 视频处理
        "video_engine": getattr(app_config, "VIDEO_ENGINE", "agnes"),
        "comfyui_video_workflow": getattr(app_config, "COMFYUI_VIDEO_WORKFLOW", ""),
        "ark_video_model": getattr(app_config, "ARK_VIDEO_MODEL", ""),
        "ark_video_endpoint": getattr(app_config, "ARK_VIDEO_ENDPOINT", ""),
        "agnes_video_model": getattr(app_config, "AGNES_VIDEO_MODEL", ""),
        "agnes_video_endpoint": getattr(app_config, "AGNES_VIDEO_ENDPOINT", ""),
    }


def _save_config_to_file(settings):
    """将设置写回 config.py 文件"""
    config_path = os.path.join(SOLO_DIR, "config.py")
    if not os.path.exists(config_path):
        return False, "config.py 文件不存在"

    content = read_file(config_path)
    if not content:
        return False, "无法读取 config.py"

    # 替换配置项
    replacements = {
        # 文本处理
        "TEXT_ENGINE": settings.get("text_engine", "agnes"),
        "DEEPSEEK_API_KEY": settings.get("deepseek_api_key", ""),
        "DEEPSEEK_API_BASE": settings.get("deepseek_api_base", ""),
        "DEEPSEEK_MODEL": settings.get("deepseek_model", ""),
        "ARK_TEXT_MODEL": settings.get("ark_text_model", ""),
        "ARK_TEXT_ENDPOINT": settings.get("ark_text_endpoint", ""),
        "AGNES_API_KEY": settings.get("agnes_api_key", ""),
        "AGNES_API_BASE": settings.get("agnes_api_base", ""),
        "AGNES_TEXT_MODEL": settings.get("agnes_text_model", ""),
        # 图片处理
        "IMAGE_ENGINE": settings.get("image_engine", "agnes"),
        "ARK_API_KEY": settings.get("ark_api_key", ""),
        "ARK_IMAGE_MODEL": settings.get("ark_image_model", "doubao-seedream-4-5-251128"),
        "ARK_IMAGE_ENDPOINT": settings.get("ark_image_endpoint", ""),
        "COMFYUI_HOST": settings.get("comfyui_host", ""),
        "COMFYUI_OUTPUT_DIR": settings.get("comfyui_output_dir", ""),
        "COMFYUI_IMAGE_WORKFLOW": settings.get("comfyui_image_workflow", ""),
        "AGNES_IMAGE_MODEL": settings.get("agnes_image_model", ""),
        "AGNES_IMAGE_ENDPOINT": settings.get("agnes_image_endpoint", ""),
        # 视频处理
        "VIDEO_ENGINE": settings.get("video_engine", "agnes"),
        "COMFYUI_VIDEO_WORKFLOW": settings.get("comfyui_video_workflow", ""),
        "ARK_VIDEO_MODEL": settings.get("ark_video_model", ""),
        "ARK_VIDEO_ENDPOINT": settings.get("ark_video_endpoint", ""),
        "AGNES_VIDEO_MODEL": settings.get("agnes_video_model", ""),
        "AGNES_VIDEO_ENDPOINT": settings.get("agnes_video_endpoint", ""),
    }

    import re
    updated_keys = []
    for key, value in replacements.items():
        if not value:  # 跳过空值
            continue
            
        # 转义 Windows 路径反斜杠
        escaped_value = value.replace("\\", "\\\\")
        
        # 尝试替换已存在的变量赋值（支持双引号、单引号或无引号）
        # 模式1: KEY = "value" 或 KEY = 'value'
        pattern1 = rf'^{key}\s*=\s*["\'].*["\']'
        # 模式2: KEY = value (无引号)
        pattern2 = rf'^{key}\s*=\s*[^"\']+'
        
        new_line = f'{key} = "{escaped_value}"'
        
        if re.search(pattern1, content, flags=re.MULTILINE):
            content = re.sub(pattern1, new_line, content, flags=re.MULTILINE)
            updated_keys.append(key)
        elif re.search(pattern2, content, flags=re.MULTILINE):
            content = re.sub(pattern2, new_line, content, flags=re.MULTILINE)
            updated_keys.append(key)
        else:
            # 配置项不存在，在文件末尾添加
            content = content.rstrip() + f'\n{new_line}'
            updated_keys.append(key)
            log_debug(f"添加新配置项: {key}")

    write_file(config_path, content)

    # 热更新模块属性
    for key in updated_keys:
        value = replacements[key]
        setattr(app_config, key, value)
    
    log_info(f"设置已保存: {len(updated_keys)} 个配置项")
    return True, f"已保存 {len(updated_keys)} 个配置项"


@app.route("/api/settings/load", methods=["GET"])
def api_settings_load():
    """获取当前设置"""
    log_debug("加载设置")
    settings = _get_config_values()
    return jsonify({"success": True, "settings": settings})


@app.route("/api/settings/save", methods=["POST"])
def api_settings_save():
    """保存设置"""
    data = request.get_json()
    log_step("保存设置", "执行")

    success, message = _save_config_to_file(data)
    if success:
        log_info("设置已保存并更新")
        return jsonify({"success": True, "message": message})
    else:
        log_error("保存设置", message)
        return jsonify({"success": False, "error": message}), 500


@app.route("/api/settings/test", methods=["POST"])
def api_settings_test():
    """测试各服务连接"""
    import requests as req

    settings = _get_config_values()
    results = []

    # 测试 DeepSeek API
    try:
        deepseek_url = f"{settings['deepseek_api_base']}/models"
        resp = req.get(
            deepseek_url,
            headers={"Authorization": f"Bearer {settings['deepseek_api_key']}"},
            timeout=10,
        )
        if resp.status_code == 200:
            results.append({"service": "DeepSeek API", "status": "ok", "message": "连接正常"})
        else:
            results.append({"service": "DeepSeek API", "status": "error", "message": f"HTTP {resp.status_code}"})
    except Exception as e:
        results.append({"service": "DeepSeek API", "status": "error", "message": str(e)})

    # 测试 Ark API
    try:
        resp = req.post(
            settings["ark_image_endpoint"],
            headers={"Authorization": f"Bearer {settings['ark_api_key']}"},
            json={"model": settings["ark_image_model"], "prompt": "test"},
            timeout=10,
        )
        # 即使返回错误也说明可以连通
        if resp.status_code < 500:
            results.append({"service": "Ark API", "status": "ok", "message": "连接正常"})
        else:
            results.append({"service": "Ark API", "status": "error", "message": f"HTTP {resp.status_code}"})
    except Exception as e:
        results.append({"service": "Ark API", "status": "error", "message": str(e)})

    # 测试 ComfyUI
    try:
        resp = req.get(f"{settings['comfyui_host']}/prompt", timeout=5)
        results.append({"service": "ComfyUI", "status": "ok", "message": "连接正常"})
    except Exception as e:
        results.append({"service": "ComfyUI", "status": "error", "message": str(e)})

    all_ok = all(r["status"] == "ok" for r in results)
    msg_lines = [f"{r['service']}: {'✓' if r['status'] == 'ok' else '✗'} {r['message']}" for r in results]

    return jsonify({
        "success": True,
        "results": results,
        "message": "\n".join(msg_lines),
        "all_ok": all_ok,
    })


# ============ 角色库 API ============

CHARACTER_LIBRARY_DIR = os.path.join(SOLO_DIR, "character_library")
CHARACTER_LIBRARY_INDEX = os.path.join(CHARACTER_LIBRARY_DIR, "index.json")
CHARACTER_LIBRARY_IMAGES = os.path.join(CHARACTER_LIBRARY_DIR, "images")


def _load_character_library():
    """加载角色库数据"""
    if not os.path.exists(CHARACTER_LIBRARY_INDEX):
        return []
    return read_json(CHARACTER_LIBRARY_INDEX, [])


def _save_character_library(characters):
    """保存角色库数据"""
    os.makedirs(CHARACTER_LIBRARY_DIR, exist_ok=True)
    write_json(CHARACTER_LIBRARY_INDEX, characters)


def _next_character_id(characters):
    """生成下一个角色 ID"""
    max_id = 0
    for c in characters:
        try:
            cid = int(c.get("id", 0))
            if cid > max_id:
                max_id = cid
        except (ValueError, TypeError):
            pass
    return f"{max_id + 1:03d}"


@app.route("/api/character-library/list", methods=["GET"])
def api_character_library_list():
    """获取角色库列表"""
    characters = _load_character_library()
    log_debug(f"获取角色库: {len(characters)} 个角色")
    return jsonify({"success": True, "characters": characters})


@app.route("/api/character-library/save", methods=["POST"])
def api_character_library_save():
    """新增/编辑角色"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "参数为空"}), 400

    name_cn = data.get("name_cn", "").strip()
    if not name_cn:
        return jsonify({"success": False, "error": "角色名称不能为空"}), 400

    characters = _load_character_library()
    char_id = data.get("id", "").strip()

    if char_id:
        # 编辑已有角色
        for c in characters:
            if c.get("id") == char_id:
                c["name_cn"] = name_cn
                c["name_en"] = data.get("name_en", "").strip()
                c["prompt"] = data.get("prompt", "").strip()
                c["description"] = data.get("description", "").strip()
                _save_character_library(characters)
                return jsonify({"success": True, "character": c})
        return jsonify({"success": False, "error": f"角色 {char_id} 不存在"}), 404
    else:
        # 新增角色
        char = {
            "id": _next_character_id(characters),
            "name_cn": name_cn,
            "name_en": data.get("name_en", "").strip(),
            "prompt": data.get("prompt", "").strip(),
            "img": "",
            "description": data.get("description", "").strip(),
        }
        characters.append(char)
        _save_character_library(characters)
        return jsonify({"success": True, "character": char})


@app.route("/api/character-library/delete", methods=["POST"])
def api_character_library_delete():
    """删除角色"""
    data = request.get_json()
    char_id = data.get("id", "")
    if not char_id:
        return jsonify({"success": False, "error": "缺少角色 ID"}), 400

    characters = _load_character_library()
    new_characters = [c for c in characters if c.get("id") != char_id]

    if len(new_characters) == len(characters):
        return jsonify({"success": False, "error": f"角色 {char_id} 不存在"}), 404

    log_step("删除角色库角色", "执行", f"char_id={char_id}")
    _save_character_library(new_characters)

    # 清理对应图片
    img_path = os.path.join(CHARACTER_LIBRARY_IMAGES, f"char_{char_id}.png")
    if os.path.exists(img_path):
        os.remove(img_path)

    return jsonify({"success": True})


@app.route("/api/character-library/generate-image", methods=["POST"])
def api_character_library_generate_image():
    """生成角色图"""
    data = request.get_json()
    char_id = data.get("id", "")
    if not char_id:
        return jsonify({"success": False, "error": "缺少角色 ID"}), 400

    characters = _load_character_library()
    char = None
    for c in characters:
        if c.get("id") == char_id:
            char = c
            break

    if not char:
        return jsonify({"success": False, "error": f"角色 {char_id} 不存在"}), 404
    if not char.get("prompt"):
        return jsonify({"success": False, "error": "角色无提示词"}), 400

    os.makedirs(CHARACTER_LIBRARY_IMAGES, exist_ok=True)

    try:
        img_path = generate_image_by_engine(
            prompt=char["prompt"],
            aspect_ratio="16:9",
            output_dir=CHARACTER_LIBRARY_IMAGES,
            scene_id=f"char_{char_id}",
        )
        char["img"] = img_path
        _save_character_library(characters)

        return jsonify({"success": True, "img": img_path})
    except Exception as e:
        log_error("角色库生成图片", str(e))
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/character-library/import-project", methods=["POST"])
def api_character_library_import_project():
    """从当前项目导入角色到库"""
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先选择项目"}), 400

    project_chars = read_json(paths["character"])
    if not project_chars:
        return jsonify({"success": False, "error": "当前项目无角色"}), 400

    library = _load_character_library()
    imported = []
    for pc in project_chars:
        # 检查是否已存在（按 name_en 去重）
        exists = any(lc.get("name_en") == pc.get("name_en") for lc in library)
        if not exists:
            char = {
                "id": _next_character_id(library),
                "name_cn": pc.get("name_cn", ""),
                "name_en": pc.get("name_en", ""),
                "prompt": pc.get("prompt", ""),
                "img": "",
                "description": "",
            }
            library.append(char)
            imported.append(char)

    log_step("导入角色到库", "完成", f"导入={len(imported)} 个 | 总数={len(library)} 个")
    _save_character_library(library)
    return jsonify({"success": True, "imported": len(imported), "characters": library})


# ============ 绘图风格示例图生成 API ============

STYLE_SAMPLES_DIR = os.path.join(CHARACTER_LIBRARY_DIR, "style_samples")

DRAWING_PROMPT_TEMPLATE = "{style_name}，8K 超高清，极致细节，完整构图，画面中心站立温柔长发年轻东方女性，飘逸长卷发，自然神态；女子脚边卧一只田园橘猫、一只小型金毛幼犬，猫狗互动亲昵；背景一栋独栋田园小木屋，木屋门前花草藤蔓环绕，远处平缓草地山林，画面上方天空悬挂暖调太阳，柔和天光，自然环境光影，完整包含人物、猫、狗、房屋、太阳五大核心元素，构图均衡，主体不裁切，元素齐全无缺失，细腻材质纹理，自然景深。图片左上角写文字：{style_name}"

DEFAULT_DRAWING_STYLES = [
    {"en": "Photorealistic", "name": "写实摄影", "desc": "超写实照片级画质，真实光影与质感", "img": ""},
    {"en": "Anime", "name": "二次元动漫", "desc": "日式动画风格，线条简洁，色彩明快", "img": ""},
    {"en": "Ink_Wash", "name": "水墨国风", "desc": "中国传统水墨画，墨色浓淡，意境悠远", "img": ""},
    {"en": "Oil_Painting", "name": "油画", "desc": "油画布纹理，厚重笔触，浓郁色彩", "img": ""},
    {"en": "Watercolor", "name": "水彩", "desc": "水彩晕染效果，柔和通透，边缘自然", "img": ""},
    {"en": "Cyberpunk", "name": "赛博朋克", "desc": "霓虹灯光，高对比，未来都市感", "img": ""},
    {"en": "Pixel_Art", "name": "像素艺术", "desc": "像素风格，复古游戏画面质感", "img": ""},
    {"en": "3D_Render", "name": "3D 渲染", "desc": "三维渲染风格，立体感强，材质精细", "img": ""},
    {"en": "Ukiyoe", "name": "浮世绘", "desc": "日本浮世绘风格，平面装饰感，线条勾勒", "img": ""},
    {"en": "Pop_Art", "name": "波普艺术", "desc": "鲜艳色块，网点效果，漫画风", "img": ""},
    {"en": "Sketch", "name": "素描速写", "desc": "铅笔素描质感，黑白灰层次", "img": ""},
    {"en": "Thick_Paint", "name": "厚涂插画", "desc": "厚涂技法，立体感强，笔触明显", "img": ""},
    {"en": "Low_Poly", "name": "Low Poly", "desc": "低多边形风格，几何面构成", "img": ""},
    {"en": "Vaporwave", "name": "蒸汽波", "desc": "怀旧霓虹，故障艺术，复古科技感", "img": ""},
    {"en": "Gongbi", "name": "重彩工笔画", "desc": "中国传统工笔重彩，线条精细，色彩浓郁厚重", "img": ""},
    {"en": "Q_Version_Cartoon", "name": "Q 版卡通", "desc": "Q 版可爱风格，大头小身，造型夸张萌趣", "img": ""},
    {"en": "Claymation", "name": "粘土黏土风", "desc": "黏土定格动画质感，手工感纹理，温暖质朴", "img": ""},
    {"en": "3D_Cartoon_OC", "name": "3D 卡通 OC 渲染风", "desc": "三维卡通角色渲染，皮克斯风格，光影圆润", "img": ""},
    {"en": "Chinese_Trend_Illustration", "name": "国潮插画", "desc": "国潮风格插画，传统元素与现代设计融合", "img": ""},
    {"en": "American_Cartoon", "name": "美式卡通", "desc": "美式卡通风格，线条粗犷，色彩饱和鲜明", "img": ""},
    {"en": "Retro_American", "name": "复古美式复古", "desc": "美式复古风格，怀旧色调，年代感纹理", "img": ""},
    {"en": "Dark_Gothic", "name": "暗黑哥特风", "desc": "暗黑哥特风格，阴暗色调，神秘华丽装饰", "img": ""},
    {"en": "Paper_Carving", "name": "立体纸雕风格", "desc": "立体纸雕艺术，多层纸张叠加，光影层次分明", "img": ""},
    {"en": "Minimalist_Line_Flat", "name": "极简线条平涂风", "desc": "极简线条勾勒，平涂色彩，简约现代感", "img": ""},
    {"en": "Korean_Soft_Comic", "name": "韩系温柔漫画风", "desc": "韩系漫画风格，柔和色调，温柔细腻画风", "img": ""},
    {"en": "Chinese_Elegant_HandDrawn", "name": "国风唯美手绘风", "desc": "国风唯美手绘，工笔线条，淡雅水墨着色", "img": ""},
    {"en": "Japanese_Anime_Cel", "name": "日系二次元赛璐璐风", "desc": "日式赛璐璐动画风，平涂上色，高饱和色块", "img": ""},
    {"en": "Disney_Animation", "name": "迪斯尼动漫风格", "desc": "迪士尼动画风格，圆润造型，夸张表情，歌舞感", "img": ""},
    {"en": "Pixar_Animation", "name": "皮克斯动漫风格", "desc": "皮克斯3D动画风格，质感细腻，光影丰富", "img": ""},
    {"en": "DreamWorks_Animation", "name": "梦工厂动漫风格", "desc": "梦工厂动画风格，角色个性鲜明，动态感强", "img": ""},
    {"en": "DC_Comics", "name": "DC动漫风格", "desc": "DC漫画风格，美式硬朗线条，暗色调超级英雄", "img": ""},
    {"en": "Mecha_Anime", "name": "机甲动漫风格", "desc": "日系机甲动漫风格，机械结构精密，战斗场景宏大", "img": ""},
    {"en": "Minimalist_Black_White_Stick_Figure", "name": "极简黑白手绘火柴人插画", "desc": "极简黑白手绘风格，线条勾勒火柴人形象，幽默夸张动作，留白意境，手绘草图质感", "img": ""},
]


def _scan_engine_images(engine: str, styles: list) -> list:
    """扫描引擎子目录中的图片，更新 styles 的 img 字段（相对路径）"""
    engine_dir = os.path.join(STYLE_SAMPLES_DIR, engine)
    if not os.path.exists(engine_dir):
        return styles
    for s in styles:
        style_dir = os.path.join(engine_dir, s.get("en", ""))
        candidate = os.path.join(style_dir, "scene_sample.png")
        if os.path.exists(candidate):
            # 计算相对于 SOLO_DIR 的路径
            rel = os.path.relpath(candidate, SOLO_DIR)
            s["img"] = rel
    return styles


def _get_engine_styles(engine: str) -> list:
    """获取某个引擎的风格列表，文件不存在则初始化"""
    styles_path = os.path.join(STYLE_SAMPLES_DIR, engine, "styles.json")
    if os.path.exists(styles_path):
        styles = read_json(styles_path, DEFAULT_DRAWING_STYLES)
        # 合并缺失的默认风格
        existing_ens = {s["en"] for s in styles if "en" in s}
        for ds in DEFAULT_DRAWING_STYLES:
            if ds["en"] not in existing_ens:
                styles.append(dict(ds))
        if len(styles) != len(existing_ens):
            _save_engine_styles(engine, styles)
        return _scan_engine_images(engine, styles)
    # 初始化
    os.makedirs(os.path.dirname(styles_path), exist_ok=True)
    write_json(styles_path, DEFAULT_DRAWING_STYLES)
    return list(DEFAULT_DRAWING_STYLES)


def _save_engine_styles(engine: str, styles: list):
    """保存某个引擎的风格列表"""
    styles_path = os.path.join(STYLE_SAMPLES_DIR, engine, "styles.json")
    os.makedirs(os.path.dirname(styles_path), exist_ok=True)
    write_json(styles_path, styles)


@app.route("/api/drawing-style/list", methods=["GET"])
def api_drawing_style_list():
    """获取绘图风格列表"""
    engine = request.args.get("engine", "agnes")
    if engine not in ("agnes", "doubao", "comfyui"):
        log_warn("获取绘图风格", f"不支持的引擎: {engine}")
        return jsonify({"success": False, "error": f"不支持的引擎: {engine}"}), 400
    styles = _get_engine_styles(engine)
    log_debug(f"获取绘图风格: engine={engine} | 数量={len(styles)}")
    return jsonify({"success": True, "styles": styles})


@app.route("/api/drawing-style/sync", methods=["POST"])
def api_drawing_style_sync():
    """扫描所有引擎的子目录，将已有图片路径写入 styles.json"""
    engines = ["agnes", "doubao", "comfyui"]
    results = {}
    for engine in engines:
        styles = _get_engine_styles(engine)
        updated = _scan_engine_images(engine, styles)
        _save_engine_styles(engine, updated)
        img_count = sum(1 for s in updated if s.get("img"))
        results[engine] = {"total": len(updated), "with_img": img_count}
    log_step("同步绘图风格", "完成", str(results))
    return jsonify({"success": True, "results": results})


@app.route("/api/drawing-style/generate", methods=["POST"])
def api_drawing_style_generate():
    """生成绘图风格示例图"""
    data = request.get_json()
    style_en = (data.get("style_en", "") or "").strip()
    style_name = (data.get("style_name", "") or "").strip()
    engine = (data.get("engine", "") or "").strip()

    if not style_en or not style_name:
        log_warn("生成绘图风格", "参数不完整")
        return jsonify({"success": False, "error": "参数不完整"}), 400
    if engine not in ("doubao", "comfyui", "agnes", ""):
        log_warn("生成绘图风格", f"不支持的引擎: {engine}")
        return jsonify({"success": False, "error": f"不支持的引擎: {engine}"}), 400

    log_step("生成绘图风格", "开始", f"style={style_name} | engine={engine}")

    # 构造提示词
    prompt = DRAWING_PROMPT_TEMPLATE.replace("{style_name}", style_name)

    # 引擎子目录
    engine_key = engine or "default"
    style_dir = os.path.join(STYLE_SAMPLES_DIR, engine_key, style_en)
    os.makedirs(style_dir, exist_ok=True)

    try:
        img_path = generate_image_by_engine(
            prompt=prompt,
            aspect_ratio="16:9",
            output_dir=style_dir,
            scene_id="sample",
            engine=engine or None,
        )
        # 更新 styles.json 中的 img 字段（相对路径）
        styles = _get_engine_styles(engine_key)
        for s in styles:
            if s.get("en") == style_en:
                s["img"] = os.path.relpath(img_path, SOLO_DIR)
                break
        _save_engine_styles(engine_key, styles)
        log_step("生成绘图风格", "完成", f"style={style_name} | path={img_path}")
        return jsonify({"success": True, "img_path": img_path})
    except Exception as e:
        log_error("绘图风格生成", str(e))
        return jsonify({"success": False, "error": str(e)}), 500


# ============ 启动 ============
if __name__ == "__main__":
    log_step("启动服务", "开始")
    log_info(f"访问地址: http://{FLASK_HOST}:{FLASK_PORT}")
    # 启动视频生成队列工作线程
    start_queue_worker()
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)