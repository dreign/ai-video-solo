#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 读取文件
with open("d:/AAA/video-tools/ai-video-solo/projects/P012/分镜.json", "r", encoding="utf-8") as f:
    content = f.read()

# 替换对话内容中的英文双引号为中文全角双引号
# 匹配模式：中文说："内容"；画面
import re

# 使用正则表达式替换
content = re.sub(r'(中文说：)"([^"]+)"(；画面)', r'\1"\2"\3', content)

# 写回文件
with open("d:/AAA/video-tools/ai-video-solo/projects/P012/分镜.json", "w", encoding="utf-8") as f:
    f.write(content)

print("替换完成")
