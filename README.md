# Solo 视频生成工具

基于 AI 大模型的视频生成工具，输入创意即可自动生成微短剧视频。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
cd solo
python app.py
```

访问 http://127.0.0.1:5000

## 功能流程

```
输入创意 → 生成剧本 → 生成分镜 → 提取角色 → 生成角色图 → 生成首帧图 → 生成视频
```

共 6 个 Tab 页，13 个操作步骤，按编号顺序执行即可。

## 依赖服务

| 服务 | 用途 |
|------|------|
| DeepSeek API | 剧本生成、分镜脚本、角色提取、提示词生成 |
| 火山引擎 Ark API | 角色图、首帧图生成（Seedream 模型） |
| ComfyUI (本地) | 图生视频 |

## 项目结构

```
solo/
├── app.py                 # Flask 后端入口
├── config.py              # 配置文件
├── api_client.py          # DeepSeek API 客户端
├── image_generator.py     # 图片生成客户端
├── video_generator.py     # 视频生成客户端
├── logger.py              # 日志模块
├── index.html / style.css / app.js   # 前端页面
├── requirements.txt       # Python 依赖
├── projects.json          # 项目索引
├── projects/              # 项目数据（每个项目独立子目录）
│   └── P001/
│       ├── 创意.md / 剧本.md
│       ├── 分镜.json / 角色.json / 选项.json
│       ├── 分镜/ / 角色/ / 视频/
└── 需求及设计文档.md       # 详细设计文档
```

## 配置

编辑 `config.py` 填入 API 密钥和服务地址：

- `DEEPSEEK_API_KEY` — DeepSeek API 密钥
- `ARK_API_KEY` — 火山引擎 API 密钥
- `COMFYUI_HOST` — ComfyUI 服务地址
- `COMFYUI_OUTPUT_DIR` — ComfyUI 输出目录

## 项目管理

- 每个创意自动分配独立编号（P001, P002...）和子目录
- 创意页面底部显示历史项目列表，点击可切换项目
- 项目数据完全隔离，互不影响