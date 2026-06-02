/**
 * Solo 视频生成工具 - 前端交互逻辑
 */

// ============ 工具函数 ============
const API_BASE = "";

function getAspectRatio() {
    const radio = document.querySelector('input[name="aspectRatio"]:checked');
    return radio ? radio.value : "16:9";
}

function showStatus(elementId, message, type = "loading") {
    const el = document.getElementById(elementId);
    el.textContent = message;
    el.className = `status-msg show ${type}`;
}

function hideStatus(elementId) {
    const el = document.getElementById(elementId);
    el.className = "status-msg";
}

// ============ Loading 遮罩 ============
let loadingCount = 0;

function showLoading() {
    loadingCount++;
    document.getElementById("loadingOverlay").classList.add("show");
}

function hideLoading() {
    loadingCount--;
    if (loadingCount <= 0) {
        loadingCount = 0;
        document.getElementById("loadingOverlay").classList.remove("show");
    }
}

async function apiFetch(url, options = {}) {
    showLoading();
    try {
        const response = await fetch(url, {
            headers: { "Content-Type": "application/json" },
            ...options,
        });
        return await response.json();
    } finally {
        hideLoading();
    }
}

// ============ 媒体路径转换 ============
const mediaUrlCache = {};

async function toWebUrl(localPath) {
    if (!localPath) return "";
    // 已经是 web URL 或相对路径
    if (localPath.startsWith("/") || localPath.startsWith("http")) return localPath;
    if (mediaUrlCache[localPath]) return mediaUrlCache[localPath];

    try {
        const result = await apiFetch(`/api/media-url?path=${encodeURIComponent(localPath)}`);
        mediaUrlCache[localPath] = result.url;
        return result.url;
    } catch (e) {
        console.warn("媒体路径转换失败:", localPath, e);
        return localPath;
    }
}

async function convertStoryboardMediaUrls(storyboard) {
    const fields = ["img_start", "img_end", "video"];
    for (const scene of storyboard) {
        for (const field of fields) {
            if (scene[field]) {
                scene[field] = await toWebUrl(scene[field]);
            }
        }
    }
    return storyboard;
}

async function convertCharacterMediaUrls(characters) {
    for (const char of characters) {
        if (char.img) {
            char.img = await toWebUrl(char.img);
        }
    }
    return characters;
}

// ============ Tab 切换 ============
let currentTab = "creative";

function switchTab(tabName) {
    document.querySelectorAll(".tab-btn").forEach((btn) => btn.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.remove("active"));

    const btn = document.querySelector(`[data-tab="${tabName}"]`);
    if (btn) btn.classList.add("active");

    const panel = document.getElementById(`panel-${tabName}`);
    if (panel) panel.classList.add("active");

    currentTab = tabName;
    loadTabData(tabName);

    // 切换到创意页时刷新项目列表
    if (tabName === "creative") {
        loadProjectList();
    }
}

document.getElementById("tabNav").addEventListener("click", (e) => {
    const btn = e.target.closest(".tab-btn");
    if (btn) {
        switchTab(btn.dataset.tab);
    }
});

// 画幅比例选择器交互
document.getElementById("aspectRatioGroup").addEventListener("click", (e) => {
    const item = e.target.closest(".aspect-ratio-item");
    if (item) {
        document.querySelectorAll(".aspect-ratio-item").forEach((el) => el.classList.remove("active"));
        item.classList.add("active");
        item.querySelector('input[type="radio"]').checked = true;
    }
});

// ============ 页面数据加载 ============
async function loadTabData(tabName) {
    switch (tabName) {
        case "creative":
            await loadCreativeData();
            break;
        case "script":
            await loadScriptData();
            break;
        case "storyboard":
            await loadStoryboardData();
            break;
        case "character":
            await loadCharacterData();
            break;
        case "image-gen":
            await loadImageGenData();
            break;
        case "video":
            await loadVideoData();
            break;
    }
}

// ============ 项目管理 ============
let currentProjectId = null;

async function loadProjectList() {
    try {
        const data = await apiFetch("/api/projects/list");
        currentProjectId = data.current_id;
        renderProjectList(data.projects, data.current_id);
        updateProjectInfo();
    } catch (e) {
        console.error("加载项目列表失败:", e);
    }
}

function renderProjectList(projects, currentId) {
    const container = document.getElementById("projectList");
    if (!projects || projects.length === 0) {
        container.innerHTML = '<p class="empty-hint">暂无历史项目</p>';
        return;
    }

    let html = "";
    projects.forEach((p) => {
        const isActive = p.id === currentId;
        const time = (p.updated_at || p.created_at || "").slice(5); // MM-DD HH:MM
        html += `
        <div class="project-item${isActive ? " active" : ""}" data-project-id="${p.id}">
            <span class="proj-id">${p.id}</span>
            <span class="proj-name">${p.creative_preview || p.name}</span>
            <span class="proj-time">${time}</span>
        </div>`;
    });
    container.innerHTML = html;
}

function updateProjectInfo() {
    const infoEl = document.getElementById("projectInfo");
    const idEl = document.getElementById("currentProjectId");
    if (currentProjectId) {
        infoEl.style.display = "";
        idEl.textContent = currentProjectId;
    } else {
        infoEl.style.display = "none";
    }
}

// 项目列表点击事件（事件委托）
document.getElementById("projectList").addEventListener("click", async (e) => {
    const item = e.target.closest(".project-item");
    if (!item) return;

    const pid = item.dataset.projectId;
    if (pid === currentProjectId) return; // 已经是当前项目

    const result = await apiFetch("/api/projects/load", {
        method: "POST",
        body: JSON.stringify({ id: pid }),
    });

    if (result.success) {
        currentProjectId = pid;
        updateProjectInfo();
        await loadProjectList(); // 刷新列表高亮
        // 重新加载当前页面数据
        await loadTabData(currentTab);
        showStatus("creativeStatus", `已切换到项目 ${pid}`, "success");
    } else {
        showStatus("creativeStatus", result.error || "切换项目失败", "error");
    }
});

// 新建项目按钮
document.getElementById("btnNewProject").addEventListener("click", () => {
    document.getElementById("creativeInput").value = "";
    const radios = document.querySelectorAll('input[name="scriptOption"]');
    if (radios.length > 0) radios[0].checked = true;
    // 重置画幅
    const arRadio = document.querySelector('input[name="aspectRatio"][value="16:9"]');
    if (arRadio) {
        arRadio.checked = true;
        document.querySelectorAll(".aspect-ratio-item").forEach((el) => el.classList.remove("active"));
        arRadio.closest(".aspect-ratio-item").classList.add("active");
    }
    currentProjectId = null;
    updateProjectInfo();
});

// 确保有当前项目的辅助函数
async function ensureProject() {
    if (currentProjectId) return true;

    const creative = document.getElementById("creativeInput").value.trim();
    if (!creative) return false;

    const optionId = document.querySelector('input[name="scriptOption"]:checked').value;
    const aspectRatio = getAspectRatio();

    const result = await apiFetch("/api/projects/create", {
        method: "POST",
        body: JSON.stringify({ creative, option_id: optionId, aspect_ratio: aspectRatio }),
    });

    if (result.success) {
        currentProjectId = result.project.id;
        updateProjectInfo();
        await loadProjectList();
        return true;
    }
    return false;
}

// ============ 创意页面 ============
async function loadCreativeData() {
    try {
        const data = await apiFetch("/api/creative/load");
        if (data.project_id) {
            currentProjectId = data.project_id;
            updateProjectInfo();
        }
        if (data.creative) {
            document.getElementById("creativeInput").value = data.creative;
        }
        if (data.option && data.option.option_id) {
            const radio = document.querySelector(`input[name="scriptOption"][value="${data.option.option_id}"]`);
            if (radio) radio.checked = true;
        }
        // 恢复画幅比例
        if (data.option && data.option.aspect_ratio) {
            const arRadio = document.querySelector(`input[name="aspectRatio"][value="${data.option.aspect_ratio}"]`);
            if (arRadio) {
                arRadio.checked = true;
                document.querySelectorAll(".aspect-ratio-item").forEach((el) => el.classList.remove("active"));
                arRadio.closest(".aspect-ratio-item").classList.add("active");
            }
        }
    } catch (e) {
        console.error("加载创意数据失败:", e);
    }
}

document.getElementById("btnSaveCreative").addEventListener("click", async () => {
    const creative = document.getElementById("creativeInput").value.trim();
    if (!creative) {
        showStatus("creativeStatus", "请输入创意内容", "error");
        return;
    }

    // 确保有项目
    if (!currentProjectId) {
        showStatus("creativeStatus", "正在创建项目...", "loading");
        if (!await ensureProject()) {
            showStatus("creativeStatus", "创建项目失败", "error");
            return;
        }
    }

    const optionId = document.querySelector('input[name="scriptOption"]:checked').value;
    const aspectRatio = getAspectRatio();

    showStatus("creativeStatus", "正在保存创意...", "loading");
    const result = await apiFetch("/api/creative/save", {
        method: "POST",
        body: JSON.stringify({ creative, option_id: optionId, aspect_ratio: aspectRatio }),
    });

    if (result.success) {
        showStatus("creativeStatus", "创意已保存", "success");
    } else {
        showStatus("creativeStatus", result.error || "保存失败", "error");
    }
});

document.getElementById("btnGenerateScript").addEventListener("click", async () => {
    const creative = document.getElementById("creativeInput").value.trim();
    if (!creative) {
        showStatus("creativeStatus", "请输入创意内容", "error");
        return;
    }

    // 确保有项目
    if (!currentProjectId) {
        showStatus("creativeStatus", "正在创建项目...", "loading");
        if (!await ensureProject()) {
            showStatus("creativeStatus", "创建项目失败", "error");
            return;
        }
    }

    const optionId = document.querySelector('input[name="scriptOption"]:checked').value;
    const aspectRatio = getAspectRatio();

    // 先保存创意
    showStatus("creativeStatus", "正在保存创意并生成剧本...", "loading");
    await apiFetch("/api/creative/save", {
        method: "POST",
        body: JSON.stringify({ creative, option_id: optionId, aspect_ratio: aspectRatio }),
    });

    // 生成剧本
    const result = await apiFetch("/api/script/generate", {
        method: "POST",
        body: JSON.stringify({ creative, option_id: optionId, aspect_ratio: aspectRatio }),
    });

    if (result.success) {
        showStatus("creativeStatus", "剧本生成成功！切换到剧本页面查看", "success");
        setTimeout(() => switchTab("script"), 1000);
    } else {
        showStatus("creativeStatus", result.error || "剧本生成失败", "error");
    }
});

// ============ 剧本页面 ============
async function loadScriptData() {
    try {
        const data = await apiFetch("/api/script/load");
        if (data.script) {
            document.getElementById("scriptEditor").value = data.script;
        }
    } catch (e) {
        console.error("加载剧本数据失败:", e);
    }

    // 加载画幅信息显示
    try {
        const creativeData = await apiFetch("/api/creative/load");
        if (creativeData.option && creativeData.option.aspect_ratio) {
            const badge = document.getElementById("scriptAspectBadge");
            badge.textContent = "画幅: " + creativeData.option.aspect_ratio;
            badge.style.display = "";
        }
    } catch (e) {}
}

document.getElementById("btnSaveScript").addEventListener("click", async () => {
    const script = document.getElementById("scriptEditor").value.trim();
    showStatus("scriptStatus", "正在保存剧本...", "loading");
    const result = await apiFetch("/api/script/save", {
        method: "POST",
        body: JSON.stringify({ script }),
    });
    if (result.success) {
        showStatus("scriptStatus", "剧本已保存", "success");
    } else {
        showStatus("scriptStatus", "保存失败", "error");
    }
});

document.getElementById("btnRegenerateScript").addEventListener("click", async () => {
    showStatus("scriptStatus", "正在重新生成剧本...", "loading");
    try {
        const creativeData = await apiFetch("/api/creative/load");
        if (!creativeData.creative) {
            showStatus("scriptStatus", "请先在创意页面输入创意", "error");
            return;
        }
        const aspectRatio = creativeData.option?.aspect_ratio || "16:9";
        const result = await apiFetch("/api/script/generate", {
            method: "POST",
            body: JSON.stringify({
                creative: creativeData.creative,
                option_id: creativeData.option?.option_id || "1",
                aspect_ratio: aspectRatio,
            }),
        });
        if (result.success) {
            document.getElementById("scriptEditor").value = result.script;
            showStatus("scriptStatus", "剧本已重新生成", "success");
        } else {
            showStatus("scriptStatus", result.error || "生成失败", "error");
        }
    } catch (e) {
        showStatus("scriptStatus", "请求失败: " + e.message, "error");
    }
});

document.getElementById("btnGenerateStoryboard").addEventListener("click", async () => {
    const script = document.getElementById("scriptEditor").value.trim();
    if (!script) {
        showStatus("scriptStatus", "请先生成或输入剧本", "error");
        return;
    }
    // 先保存
    await apiFetch("/api/script/save", {
        method: "POST",
        body: JSON.stringify({ script }),
    });

    showStatus("scriptStatus", "正在生成分镜脚本...", "loading");
    const result = await apiFetch("/api/storyboard/generate", { method: "POST" });

    if (result.success) {
        showStatus("scriptStatus", "分镜生成成功！切换到分镜页面查看", "success");
        setTimeout(() => switchTab("storyboard"), 1000);
    } else {
        showStatus("scriptStatus", result.error || "分镜生成失败", "error");
    }
});

// ============ 分镜页面（仅显示JSON字段 + 重新生成） ============
function renderFieldRow(label, value) {
    if (!value && value !== 0 && value !== false) return "";
    return `<div class="scene-field"><label>${label}</label><span class="field-value">${escapeHtml(String(value))}</span></div>`;
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function renderStoryboardList(storyboard) {
    const container = document.getElementById("storyboardList");
    if (!storyboard || storyboard.length === 0) {
        container.innerHTML = '<p class="empty-hint">暂无分镜数据，请先生成分镜</p>';
        return;
    }

    let html = "";
    storyboard.forEach((scene) => {
        html += `
        <div class="storyboard-scene">
            <div class="scene-header">
                <span class="scene-id">${scene.scene_id} - ${scene.group_id || ""}</span>
                <span class="scene-duration">${scene.duration || 0}秒</span>
            </div>
            ${renderFieldRow("描述", scene.desc)}
            ${renderFieldRow("视频提示词 (prompt_video)", scene.prompt_video)}
            ${renderFieldRow("首帧图提示词 (prompt_img_start)", scene.prompt_img_start)}
            ${renderFieldRow("尾帧图提示词 (prompt_img_end)", scene.prompt_img_end)}
            ${renderFieldRow("对话/旁白", scene.narration)}
            ${renderFieldRow("首帧图", scene.img_start)}
            ${renderFieldRow("尾帧图", scene.img_end)}
            ${renderFieldRow("视频", scene.video)}
            ${renderFieldRow("角色列表", (scene.name_en_list || []).join(", "))}
        </div>`;
    });
    container.innerHTML = html;
}

async function loadStoryboardData() {
    try {
        const data = await apiFetch("/api/storyboard/load");
        data.storyboard = await convertStoryboardMediaUrls(data.storyboard);
        renderStoryboardList(data.storyboard);
    } catch (e) {
        console.error("加载分镜数据失败:", e);
    }
}

document.getElementById("btnSaveStoryboard").addEventListener("click", async () => {
    showStatus("storyboardStatus", "分镜数据已自动保存", "success");
});

document.getElementById("btnRegenerateStoryboard").addEventListener("click", async () => {
    showStatus("storyboardStatus", "正在重新生成分镜...", "loading");
    const result = await apiFetch("/api/storyboard/generate", { method: "POST" });
    if (result.success) {
        result.storyboard = await convertStoryboardMediaUrls(result.storyboard);
        renderStoryboardList(result.storyboard);
        showStatus("storyboardStatus", "分镜已重新生成", "success");
    } else {
        showStatus("storyboardStatus", result.error || "生成失败", "error");
    }
});

// ============ 生图页面（首帧图提示词 + 首帧图 + 视频 + 预览 + 打开文件） ============
function openFileLocation(filePath) {
    if (!filePath) return;
    apiFetch("/api/open-file", {
        method: "POST",
        body: JSON.stringify({ path: filePath }),
    }).catch((e) => console.error("打开文件失败:", e));
}

function renderImageGenList(storyboard) {
    const container = document.getElementById("imageGenList");
    if (!storyboard || storyboard.length === 0) {
        container.innerHTML = '<p class="empty-hint">暂无分镜数据，请先生成分镜</p>';
        return;
    }

    let html = '<div class="storyboard-preview-row" id="imgPreviewRow"></div>';
    html += '<div class="storyboard-preview-row" id="videoPreviewRow"></div>';

    storyboard.forEach((scene) => {
        html += `
        <div class="storyboard-scene">
            <div class="scene-header">
                <span class="scene-id">${scene.scene_id} - ${scene.group_id || ""}</span>
                <span class="scene-duration">${scene.duration || 0}秒</span>
            </div>
            <div class="scene-desc">${scene.desc || ""}</div>
            ${scene.prompt_video ? `<div class="scene-field"><label>视频提示词 (prompt_video)</label><textarea readonly>${scene.prompt_video}</textarea></div>` : ""}
            ${scene.prompt_img_start ? `<div class="scene-field"><label>首帧图提示词</label><textarea readonly>${scene.prompt_img_start}</textarea></div>` : ""}
            ${scene.narration ? `<div class="scene-field"><label>对话/旁白</label><textarea readonly>${scene.narration}</textarea></div>` : ""}
            <div class="scene-field">
                <label>角色列表</label>
                <span style="font-size:0.85rem;color:var(--text-dim)">${(scene.name_en_list || []).join(", ") || "无"}</span>
            </div>
            <div class="scene-media">
                ${scene.img_start
                    ? `<div class="media-box">
                        <label>首帧图</label>
                        <img src="${scene.img_start}?t=${Date.now()}" alt="首帧图">
                        <button class="btn btn-small" onclick="openFileLocation('${scene.img_start.replace(/\\/g, "\\\\")}')">打开文件位置</button>
                    </div>`
                    : '<div class="media-placeholder">首帧图未生成</div>'}
                ${scene.video
                    ? `<div class="media-box">
                        <label>视频</label>
                        <video src="${scene.video}?t=${Date.now()}" controls></video>
                        <button class="btn btn-small" onclick="openFileLocation('${scene.video.replace(/\\/g, "\\\\")}')">打开文件位置</button>
                    </div>`
                    : '<div class="media-placeholder">视频未生成</div>'}
            </div>
        </div>`;
    });

    container.innerHTML = html;

    // 渲染横排预览
    renderPreviewRow("imgPreviewRow", storyboard, "img_start", "首帧图");
    renderPreviewRow("videoPreviewRow", storyboard, "video", "视频");
}

function renderPreviewRow(rowId, storyboard, field, label) {
    const row = document.getElementById(rowId);
    if (!row) return;

    const items = storyboard.filter((s) => s[field]);
    if (items.length === 0) {
        row.innerHTML = "";
        return;
    }

    let html = "";
    items.forEach((s) => {
        const src = `${s[field]}?t=${Date.now()}`;
        if (field === "video") {
            html += `<div class="preview-item"><video src="${src}" controls></video><div class="preview-label">${s.scene_id}</div><button class="btn btn-small" onclick="openFileLocation('${s[field].replace(/\\/g, "\\\\")}')">打开</button></div>`;
        } else {
            html += `<div class="preview-item"><img src="${src}" alt="${s.scene_id}"><div class="preview-label">${s.scene_id}</div><button class="btn btn-small" onclick="openFileLocation('${s[field].replace(/\\/g, "\\\\")}')">打开</button></div>`;
        }
    });
    row.innerHTML = html;
}

async function loadImageGenData() {
    try {
        const data = await apiFetch("/api/storyboard/load");
        data.storyboard = await convertStoryboardMediaUrls(data.storyboard);
        renderImageGenList(data.storyboard);
    } catch (e) {
        console.error("加载生图数据失败:", e);
    }
}

document.getElementById("btnGenerateImgPrompts").addEventListener("click", async () => {
    showStatus("imageGenStatus", "正在生成首帧图提示词...", "loading");
    const result = await apiFetch("/api/storyboard/generate-img-prompts", { method: "POST" });
    if (result.success) {
        result.storyboard = await convertStoryboardMediaUrls(result.storyboard);
        renderImageGenList(result.storyboard);
        showStatus("imageGenStatus", "首帧图提示词生成完成", "success");
    } else {
        showStatus("imageGenStatus", result.error || "生成失败", "error");
    }
});

document.getElementById("btnGenerateImgs").addEventListener("click", async () => {
    showStatus("imageGenStatus", "正在生成首帧图，请稍候...", "loading");
    const result = await apiFetch("/api/storyboard/generate-images", { method: "POST" });
    if (result.success) {
        result.storyboard = await convertStoryboardMediaUrls(result.storyboard);
        renderImageGenList(result.storyboard);
        showStatus("imageGenStatus", "首帧图生成完成", "success");
    } else {
        showStatus("imageGenStatus", result.error || "生成失败", "error");
    }
});

document.getElementById("btnGenerateVideos").addEventListener("click", async () => {
    showStatus("imageGenStatus", "正在生成视频，这可能需要较长时间...", "loading");
    const result = await apiFetch("/api/storyboard/generate-videos", { method: "POST" });
    if (result.success) {
        result.storyboard = await convertStoryboardMediaUrls(result.storyboard);
        renderImageGenList(result.storyboard);
        showStatus("imageGenStatus", "视频生成完成", "success");
    } else {
        showStatus("imageGenStatus", result.error || "生成失败", "error");
    }
});

// ============ 角色页面 ============
function renderCharacterList(characters) {
    const container = document.getElementById("characterList");
    if (!characters || characters.length === 0) {
        container.innerHTML = '<p class="empty-hint">暂无角色数据，请先提取角色</p>';
        return;
    }

    let html = "";
    characters.forEach((char) => {
        html += `
        <div class="character-card">
            <div class="char-header">
                <span class="char-name">${char.name_cn || ""}</span>
                <span class="char-name-en">${char.name_en || ""}</span>
            </div>
            <div class="char-prompt">${char.prompt || "无提示词"}</div>
            ${char.img
                ? `<img class="char-img" src="${char.img}?t=${Date.now()}" alt="${char.name_cn}">`
                : '<div class="char-img-placeholder">角色图未生成</div>'}
        </div>`;
    });
    container.innerHTML = html;
}

async function loadCharacterData() {
    try {
        const data = await apiFetch("/api/character/load");
        data.characters = await convertCharacterMediaUrls(data.characters);
        renderCharacterList(data.characters);
    } catch (e) {
        console.error("加载角色数据失败:", e);
    }
}

document.getElementById("btnExtractCharacters").addEventListener("click", async () => {
    showStatus("characterStatus", "正在提取角色...", "loading");
    const result = await apiFetch("/api/character/extract", { method: "POST" });
    if (result.success) {
        result.characters = await convertCharacterMediaUrls(result.characters);
        renderCharacterList(result.characters);
        showStatus("characterStatus", "角色提取完成", "success");
    } else {
        showStatus("characterStatus", result.error || "提取失败", "error");
    }
});

document.getElementById("btnGenerateCharImgs").addEventListener("click", async () => {
    showStatus("characterStatus", "正在生成角色图，请稍候...", "loading");
    const result = await apiFetch("/api/character/generate-images", { method: "POST" });
    if (result.success) {
        loadCharacterData();
        showStatus("characterStatus", "角色图生成完成", "success");
    } else {
        showStatus("characterStatus", result.error || "生成失败", "error");
    }
});

// ============ 视频页面 ============
function renderVideoList(videos) {
    const container = document.getElementById("videoList");
    if (!videos || videos.length === 0) {
        container.innerHTML = '<p class="empty-hint">暂无视频数据，请先生成视频</p>';
        return;
    }

    let html = "";
    videos.forEach((v) => {
        html += `
        <div class="video-card">
            <video src="${v.video}?t=${Date.now()}" controls></video>
            <div class="video-info">
                <div class="video-scene-id">${v.scene_id}</div>
                <div class="video-desc">${v.desc || ""}</div>
                <div class="video-duration">${v.duration || 0}秒</div>
            </div>
        </div>`;
    });
    container.innerHTML = html;
}

async function loadVideoData() {
    try {
        const data = await apiFetch("/api/video/list");
        data.videos = await convertStoryboardMediaUrls(data.videos);
        renderVideoList(data.videos);
    } catch (e) {
        console.error("加载视频数据失败:", e);
    }
}

document.getElementById("btnRefreshVideos").addEventListener("click", () => {
    loadVideoData();
    showStatus("videoStatus", "视频列表已刷新", "success");
});

// ============ 初始化 ============
document.addEventListener("DOMContentLoaded", () => {
    loadProjectList();
    loadTabData("creative");
});