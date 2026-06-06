# Plan: 新增独立角色库

## Summary

在现有项目角色（分镜提取）之外，新增一个跨项目共享的「角色库」功能。角色数据保存在独立目录 `character_library/` 中，支持手动添加/编辑/删除角色、生成角色图、将角色应用到当前分镜。

## Current State

- 角色数据保存在每个项目目录下（`projects/{PROJECT_ID}/角色.json`）
- 角色通过分镜脚本由 LLM 提取生成（`POST /api/character/extract`）
- 角色字段：`id`, `name_cn`, `name_en`, `prompt`, `img`
- 角色页面无手动编辑功能

## Proposed Changes

### 1. 数据目录结构

新增 `character_library/` 目录：
```
character_library/
  index.json     # 角色库索引（所有角色数据）
  images/        # 角色图片存储
```

### 2. 角色数据格式（index.json）

```json
[
  {
    "id": "001",
    "name_cn": "苏轼（中年）",
    "name_en": "Su_Shi",
    "prompt": "绘图提示词...",
    "img": "D:\\AAA\\video-tools\\ai-video-solo\\character_library\\images\\char_001.png",
    "description": "角色介绍：北宋著名文学家、书法家..."
  }
]
```

新增 `description` 字段（角色介绍），与现有 `id`/`name_cn`/`name_en`/`prompt`/`img` 共存。

### 3. 后端 API（app.py）

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/api/character-library/list` | 获取角色库列表 |
| POST | `/api/character-library/save` | 新增/编辑角色 |
| POST | `/api/character-library/delete` | 删除角色 |
| POST | `/api/character-library/generate-image` | 生成角色图 |
| POST | `/api/character-library/import-project` | 从当前项目导入角色到库 |

### 4. 前端 UI（index.html + app.js）

- **Tab 导航**：在「角色」和「生图」之间新增「角色库」tab
- **角色库页面**：类似现有角色页面的卡片布局，额外显示 `description` 字段
- **操作按钮**：
  - 新增角色（弹出表单：填入 name_cn, name_en, prompt, description）
  - 编辑角色（点击卡片弹出编辑表单）
  - 删除角色（确认后删除）
  - 生成角色图
  - 从项目导入角色

### 5. 文件修改清单

| 文件 | 改动 |
|------|------|
| `app.py` | 新增 `/api/character-library/*` 路由（约 80 行） |
| `index.html` | 新增 `panel-character-library`（角色库页面 HTML，约 60 行）+ Tab 按钮 |
| `app.js` | 新增 `loadCharacterLibraryData()`、`renderCharacterLibraryList()`、新增/编辑/删除函数（约 80 行） |
| `style.css` | 角色库卡片和表单样式（约 30 行） |

## Assumptions & Decisions

- 角色库独立于项目，不随项目切换而变化
- 角色库的角色可以手动编辑，不受分镜脚本限制
- 从项目导入角色时复制角色数据到角色库，不建立引用关系
- 角色库角色图生成与现有角色图生成逻辑一致

## Verification

1. 角色库 tab 能正常显示已保存的角色
2. 新增角色：填写表单后保存成功，列表刷新
3. 编辑角色：修改字段后保存成功
4. 删除角色：确认删除后列表中消失
5. 生成角色图：调用 Agnes API 生成并显示
6. 从项目导入：当前项目角色复制到角色库
7. Web 重启无报错
