"""
视频生成队列模块 - 异步任务管理
支持 Agnes AI 异步视频生成任务的持久化队列

队列状态:
- pending: 等待提交
- submitted: 已提交，等待生成
- generating: 生成中
- completed: 已完成
- failed: 失败
"""
import json
import os
import time
import threading
import requests
from datetime import datetime
from pathlib import Path

from config import AGNES_API_KEY, AGNES_VIDEO_ENDPOINT, AGNES_VIDEO_MODEL, PROJECTS_DIR
from logger import log_step, log_error, log_info, log_warn, log_debug

QUEUE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "video_queue.json")
QUEUE_LOCK = threading.Lock()
POLL_INTERVAL = 10  # 秒


def _load_queue() -> list:
    """加载队列数据"""
    if not os.path.exists(QUEUE_FILE):
        return []
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log_error("视频队列", f"加载队列失败: {e}")
        return []


def _save_queue(queue: list):
    """保存队列数据"""
    try:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_error("视频队列", f"保存队列失败: {e}")


def add_to_queue(project_id: str, scene_id: str, prompt: str, image_path: str,
                 duration: int, output_dir: str, num_frames: int = 121, fps: int = 24) -> dict:
    """
    添加视频生成任务到队列

    Returns:
        任务信息 dict
    """
    task = {
        "task_id": f"{project_id}_{scene_id}_{int(time.time() * 1000)}",
        "project_id": project_id,
        "scene_id": scene_id,
        "prompt": prompt,
        "image_path": image_path,
        "duration": duration,
        "output_dir": output_dir,
        "num_frames": num_frames,
        "fps": fps,
        "status": "pending",
        "video_id": "",           # Agnes API 返回的任务 ID
        "video_url": "",          # 生成完成后的视频 URL
        "local_path": "",         # 本地保存路径
        "error": "",
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
        "submitted_at": 0,
        "completed_at": 0,
    }

    with QUEUE_LOCK:
        queue = _load_queue()
        queue.append(task)
        _save_queue(queue)

    log_step("视频队列", "添加任务", f"task_id={task['task_id']} | scene_id={scene_id}")
    return task


def remove_from_queue(task_id: str):
    """从队列中移除任务"""
    with QUEUE_LOCK:
        queue = _load_queue()
        queue = [t for t in queue if t["task_id"] != task_id]
        _save_queue(queue)
    log_debug(f"视频队列: 移除任务 {task_id}")


def update_task(task_id: str, **kwargs):
    """更新任务字段"""
    with QUEUE_LOCK:
        queue = _load_queue()
        for task in queue:
            if task["task_id"] == task_id:
                for k, v in kwargs.items():
                    task[k] = v
                task["updated_at"] = int(time.time())
                break
        _save_queue(queue)


def get_queue(project_id: str = None) -> list:
    """获取队列，可选按项目过滤"""
    queue = _load_queue()
    if project_id:
        queue = [t for t in queue if t["project_id"] == project_id]
    return queue


def get_task(task_id: str) -> dict:
    """获取单个任务"""
    queue = _load_queue()
    for task in queue:
        if task["task_id"] == task_id:
            return task
    return None


def _create_agnes_video_task_async(prompt: str, image_path: str, num_frames: int, fps: int) -> dict:
    """创建 Agnes 视频生成任务，返回 API 响应

    约束:
    - num_frames 必须 <= 441
    - num_frames 必须满足 8n + 1，例如 81、121、161、241、441
    """
    import base64

    # 确保 num_frames 满足约束
    if num_frames > 441:
        num_frames = 441
    if num_frames < 9:
        num_frames = 9
    remainder = (num_frames - 1) % 8
    if remainder != 0:
        num_frames = num_frames + (8 - remainder)
        if num_frames > 441:
            num_frames = 441

    body = {
        "model": AGNES_VIDEO_MODEL,
        "prompt": prompt,
        "width": 1152,
        "height": 768,
        "num_frames": num_frames,
        "frame_rate": fps,
    }

    if image_path and os.path.exists(image_path):
        ext = os.path.splitext(image_path)[1].lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"
        with open(image_path, "rb") as f:
            data = f.read()
        # 使用标准 base64 编码，确保无换行符
        b64_data = base64.b64encode(data).decode("utf-8")
        body["image"] = f"data:{mime};base64,{b64_data}"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AGNES_API_KEY}",
    }

    log_debug(f"Agnes 视频请求: num_frames={num_frames}, fps={fps}, image_size={len(body.get('image', ''))} chars")

    response = requests.post(
        AGNES_VIDEO_ENDPOINT,
        headers=headers,
        json=body,
        timeout=3600,
    )

    if response.status_code != 200:
        raise Exception(f"创建任务失败: {response.status_code} - {response.text}")

    return response.json()


def _query_agnes_video_task(video_id: str) -> dict:
    """查询 Agnes 视频任务状态"""
    url = f"{AGNES_VIDEO_ENDPOINT}/{video_id}"
    headers = {"Authorization": f"Bearer {AGNES_API_KEY}"}
    response = requests.get(url, headers=headers, timeout=120)
    if response.status_code != 200:
        raise Exception(f"查询任务失败: {response.status_code}")
    return response.json()


def _download_video(video_url: str, dest_path: str) -> str:
    """下载视频到本地"""
    response = requests.get(video_url, timeout=3600)
    if response.status_code != 200:
        raise Exception(f"下载视频失败: {response.status_code}")
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(response.content)
    return dest_path


def _update_storyboard_video(project_id: str, scene_id: str, video_path: str, video_id: str = ""):
    """更新分镜 JSON 中的 video 和 video_id 字段"""
    storyboard_path = os.path.join(PROJECTS_DIR, project_id, "分镜.json")
    if not os.path.exists(storyboard_path):
        log_warn("视频队列", f"分镜文件不存在: {storyboard_path}")
        return

    try:
        with open(storyboard_path, "r", encoding="utf-8") as f:
            storyboard = json.load(f)

        updated = False
        for scene in storyboard:
            if scene.get("scene_id") == scene_id:
                scene["video"] = video_path
                if video_id:
                    scene["video_id"] = video_id
                updated = True
                break

        if updated:
            with open(storyboard_path, "w", encoding="utf-8") as f:
                json.dump(storyboard, f, ensure_ascii=False, indent=2)
            log_debug(f"更新分镜视频路径: {scene_id} -> {video_path}")
    except Exception as e:
        log_error("视频队列", f"更新分镜失败: {e}")


def process_queue():
    """
    处理队列中的任务
    - pending 任务: 提交到 Agnes API
    - submitted/generating 任务: 轮询状态
    """
    queue = _load_queue()
    if not queue:
        return

    for task in queue:
        task_id = task["task_id"]
        status = task["status"]

        try:
            if status == "pending":
                # 提交任务到 Agnes API
                log_step("视频队列", "提交任务", f"task_id={task_id} | scene_id={task['scene_id']}")
                result = _create_agnes_video_task_async(
                    prompt=task["prompt"],
                    image_path=task["image_path"],
                    num_frames=task.get("num_frames", 121),
                    fps=task.get("fps", 24),
                )
                video_id = result.get("task_id") or result.get("id", "")
                if not video_id:
                    raise Exception(f"未获取到 video_id: {result}")

                update_task(task_id,
                            status="submitted",
                            video_id=video_id,
                            submitted_at=int(time.time()))
                log_info(f"视频任务已提交 Agnes, video_id={video_id}")

                # 同时更新分镜中的 video_id
                _update_storyboard_video(task["project_id"], task["scene_id"], "", video_id)

            elif status in ("submitted", "generating"):
                video_id = task.get("video_id", "")
                if not video_id:
                    log_warn("视频队列", f"任务无 video_id, task_id={task_id}")
                    continue

                try:
                    result = _query_agnes_video_task(video_id)
                except Exception as e:
                    log_warn("视频队列", f"查询任务状态超时/失败: {task_id}, 将在下次轮询重试")
                    continue
                api_status = result.get("status", "")

                if api_status == "completed":
                    # remixed_from_video_id 为最终生成的视频 URL，仅在 status 为 completed 时可用
                    video_url = result.get("remixed_from_video_id") or result.get("video_url", "")
                    if not video_url:
                        raise Exception("任务完成但未获取到视频 URL")

                    # 下载视频
                    dest_path = os.path.join(task["output_dir"], f"scene_{task['scene_id']}.mp4")
                    local_path = _download_video(video_url, dest_path)

                    update_task(task_id,
                                status="completed",
                                video_url=video_url,
                                local_path=local_path,
                                completed_at=int(time.time()))
                    log_step("视频队列", "任务完成", f"task_id={task_id} | path={local_path}")

                    # 更新分镜 JSON
                    _update_storyboard_video(task["project_id"], task["scene_id"], local_path, video_id)

                elif api_status == "failed":
                    error_obj = result.get("error") or {}
                    error_msg = error_obj.get("message", "") if isinstance(error_obj, dict) else str(error_obj)
                    update_task(task_id, status="failed", error=error_msg)
                    log_error("视频队列", f"任务失败: {task_id}", error_msg)

                elif api_status == "in_progress":
                    # 视频正在生成中
                    progress = result.get("progress", 0)
                    if status != "generating":
                        update_task(task_id, status="generating")
                    log_debug(f"视频生成中... task_id={task_id}, status={api_status}, progress={progress}%")

                elif api_status == "queued":
                    # 任务正在队列中等待
                    log_debug(f"视频排队中... task_id={task_id}, status={api_status}")

                else:
                    # 其他未知状态
                    log_warn("视频队列", f"未知状态: task_id={task_id}, status={api_status}")

        except Exception as e:
            log_error("视频队列", f"处理任务异常: {task_id}", str(e))
            update_task(task_id, status="failed", error=str(e))


def start_queue_worker():
    """启动队列工作线程"""
    def worker():
        log_info("视频队列工作线程已启动")
        while True:
            try:
                process_queue()
            except Exception as e:
                log_error("视频队列", f"工作线程异常: {e}")
            time.sleep(POLL_INTERVAL)

    thread = threading.Thread(target=worker, daemon=True, name="VideoQueueWorker")
    thread.start()
    return thread
