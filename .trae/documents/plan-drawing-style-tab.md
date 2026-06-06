# Plan: 新增「绘图风格」Tab

## Summary

在导航栏左侧（角色库和设置之前）新增一个「绘图风格」Tab。该页面为纯静态展示页，无需后端 API，包含：
1. **绘图提示词模版区**：按模型 API 名称分类（doubao-seedream、agnes-image、comfyui），展示可复制的标准提示词模版
2. **常见绘图风格列表**：列出常见绘图风格名称及对应的图片示例

## Current State

- 导航栏 Tab：创意、剧本、分镜、角色、生图、视频、角色库、设置
- 所有 Tab 都关联后端 API 数据加载
- 页面样式基于 `.tab-panel` + `.panel-content`

## Proposed Changes

### 1. Tab 按钮（index.html）

在 `character-library` 和 `settings` 按钮之间插入新的 tab 按钮（带 `tab-btn-settings` 类，置于右侧分组）：

```html
<button class="tab-btn tab-btn-settings" data-tab="drawing-style">绘图风格</button>
<button class="tab-btn tab-btn-settings" data-tab="settings">设置</button>
```

### 2. Tab 页面 HTML（index.html）

在 `panel-settings` 之前插入新的 panel：

**模版区（上方）**：按 API 分类展示提示词模版
- 使用 `settings-section` 样式，每个模型分类一个 section
- 提示词模版内容使用 `<textarea readonly>` 展示，支持一键复制
- 模版占位符 `{绘图风格}` 用可编辑的 `<input>` 或直接嵌入文本

**风格列表区（下方）**：卡片网格布局
- 每张卡片包含：风格名称 + 示例图片占位
- 示例图片用占位图或 CSS 渐变背景

### 3. Tab 加载逻辑（app.js）

在 `loadTabData` 中新增 `case "drawing-style"`，渲染静态内容（无需 API 调用）。

### 4. CSS 样式（style.css）

- 风格卡片网格布局（参考 `.character-library-list`）
- 提示词模版的样式（参考 `.settings-section`）
- 复制按钮交互

### 5. 提示词模版内容

按模型分类：
- **Agnes Image (agnes-image-2.1-flash)**：`{绘图风格}，8K 超高清...`
- **豆包 Seedream (doubao-seedream-5-0-260128)**：同上格式
- **ComfyUI Z-Image-Turbo**：同上格式

### 6. 常见绘图风格列表

约 12-16 种常见风格，例如：
- 写实摄影、二次元动漫、水墨国风、油画、水彩、赛博朋克、像素艺术、3D 渲染、浮世绘、波普艺术、素描速写、厚涂插画、low poly、蒸汽波

## Files Changed

| File | Changes |
|------|---------|
| `index.html` | 新增 Tab 按钮 + panel HTML（约 50 行） |
| `app.js` | 新增 `loadTabData` case（2 行） |
| `style.css` | 新增风格卡片、模版展示样式（约 60 行） |

## Assumptions

- 页面纯静态，无后端 API
- 提示词模版富文本可编辑/选择
- 图片示例用 CSS 占位展示（真实图片由用户自行生成后存放）

## Verification

1. 切换到绘图风格 Tab 能正确显示
2. 提示词模版区块按模型分类展示
3. 风格列表卡片正常显示
4. Web 启动无报错
