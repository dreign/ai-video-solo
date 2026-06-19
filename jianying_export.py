"""
剪映草稿导出模块
根据项目的分镜数据生成剪映可导入的草稿文件

剪映草稿结构（PC版 5.x/6.x 兼容）：
- draft_content.json: 核心内容（轨道、素材、时间轴）
- draft_meta_info.json: 元数据（草稿名称、素材路径等）
"""
import json
import os
import uuid
import shutil
from datetime import datetime


def _new_id():
    """生成剪映格式的 UUID"""
    return str(uuid.uuid4()).upper()


def _us(ms):
    """毫秒转微秒"""
    return int(ms * 1000)


def create_jianying_draft(project_name, storyboard, output_dir, aspect_ratio="16:9"):
    """
    创建剪映草稿文件夹

    Args:
        project_name: 草稿名称
        storyboard: 分镜数据列表
        output_dir: 输出目录（剪映草稿目录）
        aspect_ratio: 画幅比例 "16:9" 或 "9:16"

    Returns:
        draft_folder_path: 草稿文件夹路径
    """
    draft_id = _new_id()
    draft_name = project_name or "SOLO导出草稿"
    draft_folder = os.path.join(output_dir, draft_name)
    os.makedirs(draft_folder, exist_ok=True)

    # 画布尺寸
    if aspect_ratio == "9:16":
        width, height = 1080, 1920
    else:
        width, height = 1920, 1080

    # 收集素材
    materials_videos = []
    materials_speeds = []
    materials_canvases = []
    materials_sound_channel_mappings = []
    materials_vocal_separations = []
    materials_texts = []

    # 轨道
    video_segments = []
    text_segments = []

    current_time_us = 0  # 当前时间轴位置（微秒）

    for scene in storyboard:
        scene_id = scene.get("scene_id", "")
        duration_sec = scene.get("duration", 5)
        duration_us = _us(duration_sec * 1000)  # 秒 -> 毫秒 -> 微秒
        video_path = scene.get("video", "")
        narration = scene.get("narration", "")
        desc = scene.get("desc", "")

        # 如果有视频文件
        if video_path and os.path.exists(video_path):
            # 素材 UUID
            video_material_id = _new_id()
            speed_id = _new_id()
            canvas_id = _new_id()
            sound_channel_id = _new_id()
            vocal_sep_id = _new_id()
            segment_id = _new_id()

            # 获取视频/图片实际尺寸（简单处理，默认用画布尺寸）
            material_width, material_height = width, height

            # 判断类型
            ext = os.path.splitext(video_path)[1].lower()
            if ext in (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif"):
                media_type = "photo"
                # 图片默认持续5秒，如果duration有值则用duration
                duration_us = _us(duration_sec * 1000)
            else:
                media_type = "video"
                # 视频尝试获取实际时长，失败则用分镜duration
                duration_us = _us(duration_sec * 1000)

            # materials.videos
            materials_videos.append({
                "aigc_type": "none",
                "audio_fade": None,
                "cartoon_path": "",
                "category_id": "",
                "category_name": "local",
                "check_flag": 63487,
                "crop": {
                    "lower_left_x": 0.0,
                    "lower_left_y": 1.0,
                    "lower_right_x": 1.0,
                    "lower_right_y": 1.0,
                    "upper_left_x": 0.0,
                    "upper_left_y": 0.0,
                    "upper_right_x": 1.0,
                    "upper_right_y": 0.0
                },
                "crop_ratio": "free",
                "crop_scale": 1.0,
                "duration": duration_us,
                "extra_type_option": 0,
                "formula_id": "",
                "freeze": None,
                "gameplay": None,
                "has_audio": False,
                "height": material_height,
                "id": video_material_id,
                "intensifies_audio_path": "",
                "intensifies_path": "",
                "is_ai_generate_content": False,
                "is_unified_beauty_mode": False,
                "local_id": "",
                "local_material_id": "",
                "material_id": "",
                "material_name": os.path.basename(video_path),
                "material_url": "",
                "matting": {
                    "flag": 0,
                    "has_use_quick_brush": False,
                    "has_use_quick_eraser": False,
                    "interactiveTime": [],
                    "path": "",
                    "strokes": []
                },
                "media_path": "",
                "object_locked": None,
                "origin_material_id": "",
                "path": video_path,
                "picture_from": "none",
                "picture_set_category_id": "",
                "picture_set_category_name": "",
                "request_id": "",
                "reverse_intensifies_path": "",
                "reverse_path": "",
                "smart_motion": None,
                "source": 0,
                "source_platform": 0,
                "stable": {
                    "matrix_path": "",
                    "stable_level": 0,
                    "time_range": {"duration": 0, "start": 0}
                },
                "team_id": "",
                "type": media_type,
                "video_algorithm": {
                    "algorithms": [],
                    "deflicker": None,
                    "motion_blur_config": None,
                    "noise_reduction": None,
                    "path": "",
                    "quality_enhance": None,
                    "time_range": None
                },
                "width": material_width
            })

            # materials.speeds
            materials_speeds.append({
                "curve_speed": None,
                "id": speed_id,
                "mode": 0,
                "speed": 1.0,
                "type": "speed"
            })

            # materials.canvases
            materials_canvases.append({
                "album_image": "",
                "blur": 0,
                "color": "",
                "id": canvas_id,
                "image": "",
                "image_id": "",
                "image_name": "",
                "source_platform": 0,
                "team_id": "",
                "type": "canvas_color"
            })

            # materials.sound_channel_mappings
            materials_sound_channel_mappings.append({
                "audio_channel_mapping": 0,
                "id": sound_channel_id,
                "is_config_open": False,
                "type": "none"
            })

            # materials.vocal_separations
            materials_vocal_separations.append({
                "choice": 0,
                "id": vocal_sep_id,
                "production_path": "",
                "time_range": None,
                "type": "vocal_separation"
            })

            # 视频轨道 segment
            video_segments.append({
                "cartoon": False,
                "clip": {
                    "alpha": 1.0,
                    "flip": {"horizontal": False, "vertical": False},
                    "rotation": 0.0,
                    "scale": {"x": 1.0, "y": 1.0},
                    "transform": {"x": 0.0, "y": 0.0}
                },
                "common_keyframes": [],
                "enable_adjust": True,
                "enable_color_curves": True,
                "enable_color_match_adjust": False,
                "enable_color_wheels": True,
                "enable_lut": True,
                "enable_smart_color_adjust": False,
                "extra_material_refs": [
                    speed_id,
                    canvas_id,
                    sound_channel_id,
                    vocal_sep_id
                ],
                "group_id": "",
                "hdr_settings": {"intensity": 1.0, "mode": 1, "nits": 1000},
                "id": segment_id,
                "intensifies_audio": False,
                "is_placeholder": False,
                "is_tone_modify": False,
                "keyframe_refs": [],
                "last_nonzero_volume": 1.0,
                "material_id": video_material_id,
                "render_index": 0,
                "responsive_layout": {
                    "enable": False,
                    "horizontal_pos_layout": 0,
                    "size_layout": 0,
                    "target_follow": "",
                    "vertical_pos_layout": 0
                },
                "reverse": False,
                "source_timerange": {"duration": duration_us, "start": 0},
                "speed": 1.0,
                "target_timerange": {"duration": duration_us, "start": current_time_us},
                "template_id": "",
                "template_scene": "default",
                "track_attribute": 0,
                "track_render_index": 0,
                "uniform_scale": {"on": True, "value": 1.0},
                "visible": True,
                "volume": 1.0
            })

        # 字幕/旁白（如果有文字）
        text_content = narration or desc
        if text_content:
            text_material_id = _new_id()
            text_segment_id = _new_id()

            # materials.texts
            materials_texts.append({
                "id": text_material_id,
                "content": f"<font id=\"\" size=\"9.0\"><color_val>{text_content}</color_val></font>",
                "type": "subtitle"
            })

            # 文字轨道 segment
            text_segments.append({
                "id": text_segment_id,
                "material_id": text_material_id,
                "target_timerange": {
                    "start": current_time_us,
                    "duration": duration_us
                }
            })

        # 时间轴前进
        current_time_us += duration_us

    # 构建 tracks
    tracks = []
    if video_segments:
        tracks.append({
            "attribute": 0,
            "flag": 0,
            "id": _new_id(),
            "is_default_name": True,
            "name": "",
            "segments": video_segments,
            "type": "video"
        })
    if text_segments:
        tracks.append({
            "attribute": 0,
            "flag": 0,
            "id": _new_id(),
            "is_default_name": True,
            "name": "",
            "segments": text_segments,
            "type": "text"
        })

    # 构建 draft_content.json
    now_ts = int(datetime.now().timestamp())
    draft_content = {
        "canvas_config": {
            "height": height,
            "ratio": "original",
            "width": width
        },
        "color_space": 0,
        "config": {
            "adjust_max_index": 1,
            "attachment_info": [],
            "combination_max_index": 1,
            "export_range": None,
            "extract_audio_last_index": 1,
            "lyrics_recognition_id": "",
            "lyrics_sync": True,
            "lyrics_taskinfo": [],
            "maintrack_adsorb": True,
            "material_save_mode": 0,
            "original_sound_last_index": 1,
            "record_audio_last_index": 1,
            "sticker_max_index": 1,
            "subtitle_recognition_id": "",
            "subtitle_sync": True,
            "subtitle_taskinfo": [],
            "system_font_list": [],
            "video_mute": False,
            "zoom_info_params": None
        },
        "cover": None,
        "create_time": now_ts,
        "duration": current_time_us,
        "extra_info": None,
        "fps": 30.0,
        "free_render_index_mode_on": False,
        "group_container": None,
        "id": draft_id,
        "keyframe_graph_list": [],
        "keyframes": {
            "adjusts": [],
            "audios": [],
            "effects": [],
            "filters": [],
            "handwrites": [],
            "stickers": [],
            "texts": [],
            "videos": []
        },
        "last_modified_platform": {
            "app_id": 3704,
            "app_source": "lv",
            "app_version": "5.9.0",
            "device_id": "",
            "hard_disk_id": "",
            "mac_address": "",
            "os": "windows",
            "os_version": "10.0.19044"
        },
        "materials": {
            "audio_balances": [],
            "audio_effects": [],
            "audio_fades": [],
            "audios": [],
            "beats": [],
            "canvases": materials_canvases,
            "chromas": [],
            "color_curves": [],
            "digital_humans": [],
            "drafts": [],
            "effects": [],
            "flowers": [],
            "green_screens": [],
            "handwrites": [],
            "hsl": [],
            "images": [],
            "log_color_wheels": [],
            "loudnesses": [],
            "manual_deformations": [],
            "masks": [],
            "material_animations": [],
            "material_colors": [],
            "placeholders": [],
            "plugin_effects": [],
            "primary_color_wheels": [],
            "realtime_denoises": [],
            "shapes": [],
            "smart_crops": [],
            "sound_channel_mappings": materials_sound_channel_mappings,
            "speeds": materials_speeds,
            "stickers": [],
            "tail_leaders": [],
            "text_templates": [],
            "texts": materials_texts,
            "transitions": [],
            "video_effects": [],
            "video_trackings": [],
            "videos": materials_videos,
            "vocal_beautifys": [],
            "vocal_separations": materials_vocal_separations
        },
        "mutable_config": None,
        "name": draft_name,
        "new_version": "87.0.0",
        "platform": {
            "app_id": 3704,
            "app_source": "lv",
            "app_version": "5.9.0",
            "device_id": "",
            "hard_disk_id": "",
            "mac_address": "",
            "os": "windows",
            "os_version": "10.0.19044"
        },
        "relationships": [],
        "render_index_track_mode_on": False,
        "retouch_cover": None,
        "source": "default",
        "static_cover_image_path": "",
        "tracks": tracks,
        "update_time": now_ts,
        "version": 360000
    }

    # 构建 draft_meta_info.json
    draft_materials = []
    for mv in materials_videos:
        draft_materials.append({
            "create_time": now_ts,
            "duration": mv["duration"],
            "extra_info": mv["material_name"],
            "file_Path": mv["path"],
            "height": mv.get("height", height),
            "id": _new_id().lower(),
            "import_time": now_ts,
            "import_time_ms": now_ts * 1000,
            "item_source": 1,
            "md5": "",
            "metetype": mv["type"],
            "roughcut_time_range": {"duration": -1, "start": -1},
            "sub_time_range": {"duration": -1, "start": -1},
            "type": 0,
            "width": mv.get("width", width)
        })

    draft_meta_info = {
        "cloud_package_completed_time": "",
        "draft_cloud_capcut_purchase_info": "",
        "draft_cloud_last_action_download": False,
        "draft_cloud_materials": [],
        "draft_cloud_purchase_info": "",
        "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "",
        "draft_cloud_videocut_purchase_info": "",
        "draft_cover": "draft_cover.jpg",
        "draft_deeplink_url": "",
        "draft_enterprise_info": {
            "draft_enterprise_extra": "",
            "draft_enterprise_id": "",
            "draft_enterprise_name": "",
            "enterprise_material": []
        },
        "draft_fold_path": draft_folder,
        "draft_id": draft_id.lower(),
        "draft_is_article_video_draft": False,
        "draft_is_from_deeplink": "false",
        "draft_materials": [
            {"type": 0, "value": draft_materials},
            {"type": 1, "value": []},
            {"type": 2, "value": []},
            {"type": 3, "value": []},
            {"type": 6, "value": []},
            {"type": 7, "value": []},
            {"type": 8, "value": []}
        ],
        "draft_materials_copied_info": [],
        "draft_name": draft_name,
        "draft_new_version": "",
        "draft_removable_storage_device": "",
        "draft_root_path": os.path.dirname(draft_folder),
        "draft_segment_extra_info": [],
        "draft_timeline_materials_size_": 0,
        "tm_draft_cloud_completed": "",
        "tm_draft_cloud_modified": 0,
        "tm_draft_create": now_ts * 1000,
        "tm_draft_modified": now_ts * 1000,
        "tm_draft_removed": 0,
        "tm_duration": current_time_us
    }

    # 写入文件
    draft_content_path = os.path.join(draft_folder, "draft_content.json")
    draft_meta_path = os.path.join(draft_folder, "draft_meta_info.json")

    with open(draft_content_path, "w", encoding="utf-8") as f:
        json.dump(draft_content, f, ensure_ascii=False, indent=2)

    with open(draft_meta_path, "w", encoding="utf-8") as f:
        json.dump(draft_meta_info, f, ensure_ascii=False, indent=2)

    return draft_folder
