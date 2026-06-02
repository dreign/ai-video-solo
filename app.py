"""Flask 后端入口 - Solo 视频生成工具"""
import json
import os
import sys
import threading
import time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SOLO_DIR, PROJECTS_DIR, PROJECTS_INDEX, FLASK_HOST, FLASK_PORT, FLASK_DEBUG
from api_client import (
    generate_script,
    generate_storyboard,
    extract_characters,
    generate_img_prompt,
    parse_json_response,
    SCRIPT_OPTIONS,
)
from image_generator import generate_image_by_prompt
from video_generator import generate_video
from logger import (
    log_step, log_llm_call, log_api_call, log_error, log_warn, log_info, log_debug,
)

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

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
        with open(path, "r", encoding="utf-8") as f:
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


# ============ 项目管理 API ============
@app.route("/api/projects/list", methods=["GET"])
def api_projects_list():
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

    log_step("保存创意", "执行", f"option={SCRIPT_OPTIONS.get(option_id, {}).get('name', '')} | 画幅={aspect_ratio} | 创意长度={len(creative)}")
    write_file(paths["creative"], creative)
    write_json(paths["option"], {
        "option_id": option_id,
        "option_name": SCRIPT_OPTIONS.get(option_id, {}).get("name", ""),
        "aspect_ratio": aspect_ratio,
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

    option_name = SCRIPT_OPTIONS.get(option_id, {}).get("name", option_id)
    log_step("生成剧本", "开始", f"option={option_name} | 画幅={aspect_ratio} | 创意长度={len(creative)}")

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
        })
        elapsed = time.time() - t0
        log_step("生成剧本", "完成", f"剧本长度={len(script)}chars | elapsed={elapsed:.1f}s")
        return jsonify({"success": True, "script": script})
    except Exception as e:
        log_error("生成剧本", str(e))
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/script/load", methods=["GET"])
def load_script():
    paths = _require_paths()
    if not paths:
        return jsonify({"script": ""})
    script = read_file(paths["script"])
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

    log_step("生成分镜", "开始", f"剧本长度={len(script)}chars | 画幅={aspect_ratio}")

    if not script:
        log_warn("生成分镜", "剧本为空")
        return jsonify({"success": False, "error": "请先生成剧本"}), 400

    try:
        response = generate_storyboard(script, aspect_ratio)
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
    option = read_json(paths["option"], {"aspect_ratio": "16:9"})
    aspect_ratio = option.get("aspect_ratio", "16:9")

    log_step("提取角色", "开始", f"分镜数={len(storyboard)} | 画幅={aspect_ratio}")

    if not storyboard:
        log_warn("提取角色", "分镜为空")
        return jsonify({"success": False, "error": "请先生成分镜脚本"}), 400

    try:
        response = extract_characters(json.dumps(storyboard, ensure_ascii=False), aspect_ratio)
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
    return jsonify({"characters": characters})


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
        output_path = os.path.join(paths["character_img"], f"char_{char_id}.png")
        # 将画幅比例信息追加到角色prompt
        char_prompt = f"aspect ratio {aspect_ratio}, {char['prompt']}"
        try:
            img_path = generate_image_by_prompt(char_prompt, output_path)
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


# ============ 分镜首帧图提示词 API ============
@app.route("/api/storyboard/generate-img-prompts", methods=["POST"])
def api_generate_img_prompts():
    t0 = time.time()
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先创建或选择项目"}), 400

    storyboard = read_json(paths["storyboard"])
    option = read_json(paths["option"], {"aspect_ratio": "16:9"})
    aspect_ratio = option.get("aspect_ratio", "16:9")

    log_step("生成首帧图提示词", "开始", f"分镜数={len(storyboard)} | 画幅={aspect_ratio}")

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
            img_prompt = generate_img_prompt(prompt_video, aspect_ratio)
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
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先创建或选择项目"}), 400

    storyboard = read_json(paths["storyboard"])
    characters = read_json(paths["character"])

    log_step("生成分镜首帧图", "开始", f"分镜数={len(storyboard)} | 角色数={len(characters)}")

    if not storyboard:
        log_warn("生成分镜首帧图", "分镜为空")
        return jsonify({"success": False, "error": "请先生成分镜脚本"}), 400

    os.makedirs(paths["storyboard_img"], exist_ok=True)

    # 构建角色名称到图片路径的映射
    char_img_map = {}
    for char in characters:
        if char.get("name_en") and char.get("img"):
            char_img_map[char["name_en"]] = char["img"]
    log_debug(f"角色图片映射: {list(char_img_map.keys())}")

    results = []
    for scene in storyboard:
        scene_id = scene.get("scene_id", "?")
        prompt_img = scene.get("prompt_img_start", "")

        if not prompt_img:
            log_warn("生成分镜首帧图", f"分镜 {scene_id} 无首帧图提示词，跳过")
            results.append({"scene_id": scene_id, "status": "skip", "reason": "无首帧图提示词"})
            continue

        # 查找关联角色图
        reference_img = None
        name_list = scene.get("name_en_list", [])
        for name_en in name_list:
            if name_en in char_img_map:
                reference_img = char_img_map[name_en]
                break
        log_step("生成分镜首帧图", "执行", f"scene_id={scene_id} | 关联角色={name_list} | 参考图={reference_img or '无'}")

        output_path = os.path.join(paths["storyboard_img"], f"scene_{scene_id}.png")
        try:
            img_path = generate_image_by_prompt(prompt_img, output_path)
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


# ============ 分镜视频生成 API ============
@app.route("/api/storyboard/generate-videos", methods=["POST"])
def api_generate_storyboard_videos():
    t0 = time.time()
    paths = _require_paths()
    if not paths:
        return jsonify({"success": False, "error": "请先创建或选择项目"}), 400

    storyboard = read_json(paths["storyboard"])

    log_step("生成分镜视频", "开始", f"分镜数={len(storyboard)}")

    if not storyboard:
        log_warn("生成分镜视频", "分镜为空")
        return jsonify({"success": False, "error": "请先生成分镜脚本"}), 400

    os.makedirs(paths["video"], exist_ok=True)

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

        log_step("生成分镜视频", "执行", f"scene_id={scene_id} | duration={duration}s | img={img_start}")
        try:
            video_path = generate_video(img_start, prompt_video, duration, paths["video"], scene_id)
            scene["video"] = video_path
            results.append({"scene_id": scene_id, "status": "success", "video": video_path})
        except Exception as e:
            log_error("生成分镜视频", str(e), f"scene_id={scene_id}")
            results.append({"scene_id": scene_id, "status": "error", "error": str(e)})

    write_json(paths["storyboard"], storyboard)
    success_count = sum(1 for r in results if r["status"] == "success")
    elapsed = time.time() - t0
    log_step("生成分镜视频", "完成", f"成功={success_count}/{len(storyboard)} | elapsed={elapsed:.1f}s")
    return jsonify({"success": True, "results": results, "storyboard": storyboard})


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
        return jsonify({"success": True, "url": "/" + rel})
    else:
        # 路径不在项目目录内，尝试通过 file:// 协议
        return jsonify({"success": True, "url": "file:///" + file_path.replace("\\", "/")})


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
if __name__ == "__main__":
    log_step("启动服务", "开始")
    log_info(f"访问地址: http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)