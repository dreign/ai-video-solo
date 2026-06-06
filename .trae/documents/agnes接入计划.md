# Agnes AI Provider 接入计划

## 概述
为项目新增 Agnes 大模型的文本、图像、视频 API 支持。

## 当前状态分析
- 文本处理：`TEXT_ENGINE` 支持 `"deepseek"` 和 `"ark"` 两种引擎
- 图像处理：`IMAGE_ENGINE` 支持 `"doubao"` 和 `"comfyui"` 两种引擎
- 视频处理：`VIDEO_ENGINE` 支持 `"comfyui"` 和 `"doubao"` 两种引擎
- 所有配置集中在 `config.example.py` 文件中

## 接入信息
- **官网**: https://agnes-ai.com/
- **BASE URL**: `https://apihub.agnes-ai.com/v1`
- **API Key**: `sk-sC9PAfKo5dfdv7gV5gDGzQHKT9k4IxQNFNMbOQDCMN6l35Ap`
- **文本模型**: `agnes-2.0-flash`
- **图像模型**: `agnes-image-2.1-flash`
- **视频模型**: `agnes-video-v2.0`

## 修改计划

### 1. 配置文件 `config.example.py`
新增 Agnes 相关配置项：

```python
# Agnes API
AGNES_API_KEY = "sk-sC9PAfKo5dfdv7gV5gDGzQHKT9k4IxQNFNMbOQDCMN6l35Ap"
AGNES_API_BASE = "https://apihub.agnes-ai.com/v1"
AGNES_TEXT_MODEL = "agnes-2.0-flash"
AGNES_IMAGE_MODEL = "agnes-image-2.1-flash"
AGNES_VIDEO_MODEL = "agnes-video-v2.0"
```

### 2. 文本处理 `api_client.py`
新增 `_call_agnes` 函数处理 Agnes 文本 API：
- 使用 OpenAI 兼容格式调用 Agnes API
- 复用现有的 `client` 初始化模式
- 在 `call_deepseek()` 中添加 `TEXT_ENGINE == "agnes"` 分支

### 3. 图像处理 `image_generator.py`
新增 `generate_image_agnes()` 函数：
- 调用 Agnes 图像 API
- 返回图片 URL 或下载到本地
- 参考现有的 `generate_image()` 模式

### 4. 视频处理 `video_generator.py`
新增 `generate_video_agnes()` 函数：
- 调用 Agnes 视频 API
- 支持图片生成视频（I2V）
- 参考现有的 `generate_video_seedance()` 模式

## 实施步骤

1. **修改 `config.example.py`**
   - 添加 AGNES_API_KEY, AGNES_API_BASE
   - 添加 AGNES_TEXT_MODEL, AGNES_IMAGE_MODEL, AGNES_VIDEO_MODEL

2. **修改 `api_client.py`**
   - 导入 AGNES 相关配置
   - 添加 `_call_agnes()` 函数
   - 修改 `call_deepseek()` 支持 TEXT_ENGINE="agnes"

3. **修改 `image_generator.py`**
   - 导入 AGNES 相关配置
   - 添加 `generate_image_agnes()` 函数
   - 修改 `generate_image()` 支持 IMAGE_ENGINE="agnes"

4. **修改 `video_generator.py`**
   - 导入 AGNES 相关配置
   - 添加 `generate_video_agnes()` 函数
   - 修改 `generate_video()` 支持 VIDEO_ENGINE="agnes"

## 验证步骤
1. 确认配置正确添加
2. 检查代码导入无误
3. 确认 API 调用逻辑正确

## 假设
- Agnes 文本 API 兼容 OpenAI ChatCompletion 格式
- Agnes 图像 API 返回格式与现有 Ark API 类似
- Agnes 视频 API 返回格式与现有 Seedance API 类似
