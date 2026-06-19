# Plan: Agnes 图片/视频模式自动检测

## Summary

移除设置页面中 Agnes 图片和视频的「生成模式」手动切换选项，改为根据调用上下文自动选择模式：

* **图片**：有参考角色图时用图生图（image2image），无参考角色图时用文生图（text2image）

* **视频**：默认使用分镜首帧图做图生视频（image2video）

## Current State

1. `config.py` 中有 `AGNES_IMAGE_MODE` 和 `AGNES_VIDEO_MODE` 配置项
2. 设置页面（index.html）有 Agnes 图片和视频的「生成模式」toggle 切换 UI
3. `app.js` 有加载/保存 `agnes_image_mode` 和 `agnes_video_mode` 的逻辑
4. `app.py` 的 `_get_config_values` 和 `_save_config_to_file` 中保存/读取这两个字段
5. `image_generator.py` 的 `generate_image_agnes` 使用 `AGNES_IMAGE_MODE` 决定模式
6. `video_generator.py` 的 `generate_video_agnes` 使用 `AGNES_VIDEO_MODE` 决定模式
7. `app.py` 的 `generate_image_by_engine` 缺少 `reference_image_path` 参数
8. `app.py` 的 `api_generate_storyboard_images` 找到 `reference_img` 但未传入 `generate_image_by_engine`

## Proposed Changes

### 1. config.py — 移除模式配置项

* 删除 `AGNES_IMAGE_MODE = "text2image"` 行

* 删除 `AGNES_VIDEO_MODE = "image2video"` 行和注释

### 2. index.html — 替换模式切换 UI 为文本说明

* **图片处理 - Agnes 配置区**: 移除 `agnesImageModeToggle` 的 radio 切换，替换为一行说明文字，如 `<p class="settings-hint">支持模式：文生图、图生图（有角色参考图时自动切换）</p>`

* **视频处理 - Agnes 配置区**: 移除 `agnesVideoModeToggle` 的 radio 切换，替换为一行说明文字，如 `<p class="settings-hint">支持模式：文生视频、图生视频、多图视频、首尾帧（默认使用首帧图做图生视频）</p>`

### 3. image\_generator.py — 自动检测模式

* 从 `from config import ...` 中移除 `AGNES_IMAGE_MODE`

* `generate_image_agnes` 函数：移除 `mode = AGNES_IMAGE_MODE`，改为根据 `reference_image_path` 自动判断：

  * 如果 `reference_image_path` 存在且文件可读 → image2image 模式（使用 agnes-image-2.0-flash + extra\_body）

  * 否则 → text2image 模式（使用 agnes-image-2.1-flash）

* 更新 log 输出，记录实际使用的模式

### 4. video\_generator.py — 固定默认模式

* 从 `from config import ...` 中移除 `AGNES_VIDEO_MODE`

* `generate_video_agnes` 函数：移除 `mode = AGNES_VIDEO_MODE`，移除 switch-case 逻辑

* 简化函数：当 `image_path` 提供时，默认走图生视频（image2video），保留参数但只使用 image\_path

* 保留 `end_image_path` 和 `extra_images` 参数（将来可扩展，当前默认不使用）

### 5. app.py — 传递参考图参数

* `generate_image_by_engine` 函数：

  * 新增 `reference_image_path: str = None` 参数

  * 当引擎为 agnes 时，将 `reference_image_path` 传入 `generate_image_agnes`

* `api_generate_storyboard_images`：

  * 将找到的 `reference_img` 传入 `generate_image_by_engine`（作为 `reference_image_path`）

* `_get_config_values`：移除 `agnes_image_mode` 和 `agnes_video_mode` 字段

* `_save_config_to_file`：移除 `AGNES_IMAGE_MODE` 和 `AGNES_VIDEO_MODE` 替换项

### 6. app.js — 移除模式加载/保存

* `loadSettingsData`：移除加载 `agnes_image_mode` 和 `agnes_video_mode` 的相关代码

* 保存设置逻辑：移除 `agnes_image_mode` 和 `agnes_video_mode` 字段

## Assumptions & Decisions

* 角色图生成时不会传 `reference_image_path`，因此始终走文生图 — **正确**

* 分镜首帧图生成时能找到角色参考图则传 reference，否则不传 — **已实现逻辑**

* 视频始终使用分镜首帧图做图生视频 — **当前使用模式**

* 移除 config 中的模式配置不影响现有项目数据

## Verification

1. 启动 web 服务后，打开设置页面检查 Agnes 图片和视频配置区没有模式切换 UI
2. 角色图生成时应走文生图（日志中应显示 text2image）
3. 分镜首帧图生成时，有角色参考图时应走图生图（日志中应显示 image2image）
4. 分镜首帧图生成时，无角色参考图时应走文生图（日志中应显示 text2image）
5. 视频生成时应使用首帧图做图生视频（日志中应显示 image2video）

