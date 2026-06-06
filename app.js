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

// ============ 角色库 ============

function renderCharacterLibraryList(characters) {
    const container = document.getElementById("characterLibraryList");
    if (!characters || characters.length === 0) {
        container.innerHTML = '<p class="empty-hint">暂无角色库数据，请新增或从项目导入</p>';
        return;
    }

    let html = "";
    characters.forEach((char) => {
        const imgSrc = char.img ? `${char.img}?t=${Date.now()}` : "";
        html += `
        <div class="char-lib-card" data-id="${char.id}">
            <div class="char-lib-header">
                <span class="char-lib-name">${char.name_cn || ""}</span>
                <span class="char-lib-name-en">${char.name_en || ""}</span>
            </div>
            ${char.description ? `<div class="char-lib-desc">${escapeHtml(char.description)}</div>` : ""}
            <div class="char-lib-prompt">${char.prompt ? escapeHtml(char.prompt).slice(0, 200) + (char.prompt.length > 200 ? "..." : "") : "无提示词"}</div>
            ${imgSrc
                ? `<img class="char-lib-img" src="${imgSrc}" alt="${char.name_cn}" onmouseenter="showImagePreview(this.src)" onmouseleave="hideImagePreview()">`
                : '<div class="char-lib-img-placeholder">角色图未生成</div>'}
            <div class="char-lib-actions">
                <button class="btn btn-small btn-accent" onclick="charLibGenerateImage('${char.id}')">生成图</button>
                <button class="btn btn-small btn-primary" onclick="charLibEdit('${char.id}')">编辑</button>
                <button class="btn btn-small btn-danger" onclick="charLibDelete('${char.id}')">删除</button>
            </div>
        </div>`;
    });
    container.innerHTML = html;
}

async function loadCharacterLibraryData() {
    try {
        const data = await apiFetch("/api/character-library/list");
        const chars = data.characters || [];
        await convertCharacterMediaUrls(chars);
        renderCharacterLibraryList(chars);
    } catch (e) {
        console.error("加载角色库失败:", e);
        showStatus("characterLibraryStatus", "加载角色库失败", "error");
    }
}

function openCharLibDialog(char) {
    document.getElementById("charLibEditId").value = char ? char.id : "";
    document.getElementById("charLibNameCn").value = char ? (char.name_cn || "") : "";
    document.getElementById("charLibNameEn").value = char ? (char.name_en || "") : "";
    document.getElementById("charLibDescription").value = char ? (char.description || "") : "";
    document.getElementById("charLibPrompt").value = char ? (char.prompt || "") : "";
    document.getElementById("charLibDialogTitle").textContent = char ? "编辑角色" : "新增角色";
    document.getElementById("charLibDialogOverlay").style.display = "flex";
}

function closeCharLibDialog() {
    document.getElementById("charLibDialogOverlay").style.display = "none";
}

async function charLibSave() {
    const id = document.getElementById("charLibEditId").value;
    const nameCn = document.getElementById("charLibNameCn").value.trim();
    if (!nameCn) {
        showStatus("characterLibraryStatus", "角色名称不能为空", "error");
        return;
    }

    const result = await apiFetch("/api/character-library/save", {
        method: "POST",
        body: JSON.stringify({
            id: id,
            name_cn: nameCn,
            name_en: document.getElementById("charLibNameEn").value.trim(),
            description: document.getElementById("charLibDescription").value.trim(),
            prompt: document.getElementById("charLibPrompt").value.trim(),
        }),
    });

    if (result.success) {
        closeCharLibDialog();
        await loadCharacterLibraryData();
        showStatus("characterLibraryStatus", "角色已保存", "success");
    } else {
        showStatus("characterLibraryStatus", result.error || "保存失败", "error");
    }
}

function charLibEdit(charId) {
    // 从当前列表中找到角色数据
    const cards = document.querySelectorAll(".char-lib-card");
    for (const card of cards) {
        if (card.dataset.id === charId) {
            const nameEl = card.querySelector(".char-lib-name");
            const nameEnEl = card.querySelector(".char-lib-name-en");
            const descEl = card.querySelector(".char-lib-desc");
            const promptEl = card.querySelector(".char-lib-prompt");
            openCharLibDialog({
                id: charId,
                name_cn: nameEl ? nameEl.textContent : "",
                name_en: nameEnEl ? nameEnEl.textContent : "",
                description: descEl ? descEl.textContent : "",
                prompt: promptEl ? promptEl.textContent.replace(/\.\.\.$/, "") : "",
            });
            return;
        }
    }
    // 回退：从 API 加载
    apiFetch("/api/character-library/list").then(data => {
        const chars = data.characters || [];
        const char = chars.find(c => c.id === charId);
        if (char) openCharLibDialog(char);
        else showStatus("characterLibraryStatus", "角色不存在", "error");
    });
}

async function charLibDelete(charId) {
    if (!confirm("确定要删除该角色吗？")) return;
    const result = await apiFetch("/api/character-library/delete", {
        method: "POST",
        body: JSON.stringify({ id: charId }),
    });
    if (result.success) {
        await loadCharacterLibraryData();
        showStatus("characterLibraryStatus", "角色已删除", "success");
    } else {
        showStatus("characterLibraryStatus", result.error || "删除失败", "error");
    }
}

async function charLibGenerateImage(charId) {
    showStatus("characterLibraryStatus", "正在生成角色图...", "loading");
    const result = await apiFetch("/api/character-library/generate-image", {
        method: "POST",
        body: JSON.stringify({ id: charId }),
    });
    if (result.success) {
        await loadCharacterLibraryData();
        showStatus("characterLibraryStatus", "角色图生成完成", "success");
    } else {
        showStatus("characterLibraryStatus", result.error || "生成失败", "error");
    }
}

// 角色库事件绑定
document.getElementById("btnCharLibAdd").addEventListener("click", () => openCharLibDialog(null));
document.getElementById("btnCharLibDialogClose").addEventListener("click", closeCharLibDialog);
document.getElementById("btnCharLibDialogCancel").addEventListener("click", closeCharLibDialog);
document.getElementById("charLibDialogOverlay").addEventListener("click", (e) => {
    if (e.target.id === "charLibDialogOverlay") closeCharLibDialog();
});
document.getElementById("btnCharLibDialogSave").addEventListener("click", charLibSave);

document.getElementById("btnCharLibImport").addEventListener("click", async () => {
    showStatus("characterLibraryStatus", "正在导入角色...", "loading");
    const result = await apiFetch("/api/character-library/import-project", { method: "POST" });
    if (result.success) {
        await loadCharacterLibraryData();
        showStatus("characterLibraryStatus", `成功导入 ${result.imported} 个角色`, "success");
    } else {
        showStatus("characterLibraryStatus", result.error || "导入失败", "error");
    }
});

// ============ 绘图风格 ============



let currentStyleEngine = "agnes";
let currentStyles = [];

function switchStyleEngine(engine) {
    currentStyleEngine = engine;
    document.querySelectorAll("#styleEngineTabs .sub-tab").forEach(tab => {
        tab.classList.toggle("active", tab.dataset.engine === engine);
    });
    loadDrawingStyleData();
}

function loadDrawingStyleData() {
    apiFetch(`/api/drawing-style/list?engine=${currentStyleEngine}`).then(data => {
        currentStyles = data.styles || [];
        renderStyleGallery(currentStyles);
    }).catch(e => {
        console.error("加载绘图风格失败:", e);
    });
}

function renderStyleGallery(styles) {
    const container = document.getElementById("styleGallery");
    if (!container || !styles) return;

    let html = "";
    styles.forEach((style) => {
        const hasImg = style.img && style.img.trim() !== "";
        const imgSrc = hasImg ? `${style.img}?t=${Date.now()}` : "";
        html += `
        <div class="style-card" data-style-en="${style.en}" data-style-name="${style.name}">
            <div class="style-card-img" id="styleImg-${style.en}">
                <img class="style-card-real-img" id="styleRealImg-${style.en}" src="${imgSrc}"
                     onload="this.style.display='';document.getElementById('stylePlaceholder-${style.en}').style.display='none'"
                     onerror="this.style.display='none';document.getElementById('stylePlaceholder-${style.en}').style.display='flex'"
                     onclick="showLargeImage(this.src)"
                     style="${hasImg ? '' : 'display:none;'}cursor:pointer">
                <div class="style-card-placeholder" id="stylePlaceholder-${style.en}" style="background: linear-gradient(135deg, hsl(${Math.floor(Math.random() * 360)}, 70%, 60%), hsl(${Math.floor(Math.random() * 360)}, 60%, 40%));${hasImg ? 'display:none' : 'display:flex'};">
                    <span class="style-card-img-label">${style.en.replace(/_/g, " ")}</span>
                </div>
            </div>
            <div class="style-card-name">${style.name}</div>
            <div class="style-card-desc">${style.desc}</div>
            <div class="style-card-actions">
                <button class="btn btn-small btn-accent" onclick="generateStyleSample('${style.en}','${style.name}')">生成示例图</button>
            </div>
        </div>`;
    });
    container.innerHTML = html;
}

function populateArtStyleDropdown() {
    apiFetch("/api/drawing-style/list?engine=agnes").then(data => {
        const select = document.getElementById("creativeArtStyle");
        if (!select) return;
        const currentVal = select.value;
        select.innerHTML = data.styles.map(s => `<option value="${s.name}">${s.name}</option>`).join("");
        // 恢复选中值
        if (currentVal) select.value = currentVal;
    }).catch(() => {});
}

async function generateStyleSample(styleEn, styleName) {
    const engine = currentStyleEngine;
    showStatus("characterLibraryStatus", `正在生成 ${styleName} 示例图（${engine}）...`, "loading");
    try {
        const result = await apiFetch("/api/drawing-style/generate", {
            method: "POST",
            body: JSON.stringify({ style_en: styleEn, style_name: styleName, engine: engine }),
        });
        if (result.success) {
            await loadDrawingStyleData();
            showStatus("characterLibraryStatus", `${styleName} 示例图生成完成`, "success");
        } else {
            showStatus("characterLibraryStatus", result.error || "生成失败", "error");
        }
    } catch (e) {
        showStatus("characterLibraryStatus", e.message || "生成失败", "error");
    }
}

async function generateAllStyles() {
    const engine = currentStyleEngine;
    if (!currentStyles.length) return;
    if (!confirm(`将为 ${engine} 引擎生成 ${currentStyles.length} 种风格的示例图，继续吗？`)) return;

    showStatus("characterLibraryStatus", `正在批量生成（共 ${currentStyles.length} 张）...`, "loading");
    let success = 0, fail = 0;
    for (let i = 0; i < currentStyles.length; i++) {
        const style = currentStyles[i];
        try {
            showStatus("characterLibraryStatus", `正在生成 [${i + 1}/${currentStyles.length}] ${style.name}...`, "loading");
            const result = await apiFetch("/api/drawing-style/generate", {
                method: "POST",
                body: JSON.stringify({ style_en: style.en, style_name: style.name, engine: engine }),
            });
            if (result.success) success++;
            else fail++;
        } catch (e) {
            fail++;
        }
    }
    await loadDrawingStyleData();
    showStatus("characterLibraryStatus", `批量生成完成：成功 ${success} 张，失败 ${fail} 张`, fail > 0 ? "error" : "success");
}

async function syncStyleImages() {
    showStatus("characterLibraryStatus", "正在同步图片路径...", "loading");
    try {
        const result = await apiFetch("/api/drawing-style/sync", { method: "POST" });
        if (result.success) {
            const parts = Object.entries(result.results).map(([k, v]) => `${k}:${v.with_img}/${v.total}`);
            await loadDrawingStyleData();
            showStatus("characterLibraryStatus", `同步完成：${parts.join(" | ")}`, "success");
        } else {
            showStatus("characterLibraryStatus", result.error || "同步失败", "error");
        }
    } catch (e) {
        showStatus("characterLibraryStatus", e.message || "同步失败", "error");
    }
}

function copyTemplate(elementId) {
    const textarea = document.getElementById(elementId);
    if (!textarea) return;
    textarea.select();
    navigator.clipboard.writeText(textarea.value).then(() => {
        showToast("提示词模版已复制");
    }).catch(() => {
        // 降级方案
        document.execCommand("copy");
        showToast("提示词模版已复制");
    });
}

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
        case "settings":
            await loadSettingsData();
            break;
        case "character-library":
            await loadCharacterLibraryData();
            break;
        case "drawing-style":
            loadDrawingStyleData();
            break;
    }
}

// ============ 项目管理 ============
let currentProjectId = null;

// 项目缓存（用于获取项目名称）
let projectCache = [];

async function loadProjectList() {
    try {
        const data = await apiFetch("/api/projects/list");
        currentProjectId = data.current_id;
        projectCache = data.projects || [];
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
    const nameEl = document.getElementById("currentProjectName");
    const modeEl = document.getElementById("currentProjectMode");

    if (currentProjectId) {
        // 查找当前项目的名称
        const project = projectCache.find((p) => p.id === currentProjectId);
        const projectName = project ? (project.creative_preview || project.name || currentProjectId) : currentProjectId;
        nameEl.textContent = projectName;
        nameEl.classList.remove("empty");
        nameEl.classList.add("active");
        modeEl.textContent = "(编辑模式)";
        modeEl.classList.remove("mode-new");
        modeEl.classList.add("mode-edit");
    } else {
        nameEl.textContent = "无";
        nameEl.classList.add("empty");
        nameEl.classList.remove("active");
        modeEl.textContent = "(新建项目模式)";
        modeEl.classList.add("mode-new");
        modeEl.classList.remove("mode-edit");
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

// ============ 诗词库选择弹窗 ============
let poemCache = [];

function renderPoemList(poems) {
    const listEl = document.getElementById("poemList");
    if (!poems || poems.length === 0) {
        listEl.innerHTML = '<p class="empty-hint">未找到匹配的诗词</p>';
        return;
    }
    listEl.innerHTML = poems.map((p) => {
        const content = (p.content || "").replace(/</g, "&lt;");
        return `
            <div class="poem-item" data-index="${p.index}">
                <div class="poem-item-title">${p.title}<span class="poem-item-score">${p.fame_score || ""}</span></div>
                <div class="poem-item-meta">${p.dynasty || ""} · ${p.author || ""}</div>
                <div class="poem-item-content">${content}</div>
            </div>
        `;
    }).join("");

    // 绑定点击事件
    listEl.querySelectorAll(".poem-item").forEach((item) => {
        item.addEventListener("click", () => {
            const idx = parseInt(item.getAttribute("data-index"), 10);
            const poem = poemCache.find((p) => p.index === idx);
            if (poem) {
                selectPoem(poem);
            }
        });
    });
}

function selectPoem(poem) {
    // 整理诗词全字段，作为剧本写作资源
    let text = `【诗词标题】${poem.title || ""}\n`;
    text += `【作者】${poem.author || ""}（${poem.dynasty || ""}）\n`;
    if (poem.author_intro) text += `【作者简介】${poem.author_intro}\n`;
    if (poem.writing_background) text += `【写作背景】${poem.writing_background}\n`;
    if (poem.translation) text += `【白话译文】${poem.translation}\n`;
    if (poem.theme) text += `【主旨情感】${poem.theme}\n`;
    if (poem.appreciation) text += `【艺术赏析】${poem.appreciation}\n`;
    document.getElementById("creativeInput").value = text;
    closePoemDialog();
    showStatus("creativeStatus", `已选择诗词《${poem.title}》，请继续创作`, "success");
}

function openPoemDialog() {
    const overlay = document.getElementById("poemDialogOverlay");
    overlay.style.display = "flex";
    document.getElementById("poemSearchInput").value = "";

    if (poemCache.length === 0) {
        apiFetch("/api/poems/list").then((data) => {
            poemCache = data.poems || [];
            renderPoemList(poemCache);
        }).catch((e) => {
            console.error("加载诗词库失败:", e);
            document.getElementById("poemList").innerHTML = '<p class="empty-hint">诗词库加载失败</p>';
        });
    } else {
        renderPoemList(poemCache);
    }

    setTimeout(() => {
        document.getElementById("poemSearchInput").focus();
    }, 100);
}

function closePoemDialog() {
    document.getElementById("poemDialogOverlay").style.display = "none";
}

document.getElementById("btnOpenPoemDialog").addEventListener("click", openPoemDialog);
document.getElementById("btnClosePoemDialog").addEventListener("click", closePoemDialog);
document.getElementById("poemDialogOverlay").addEventListener("click", (e) => {
    if (e.target.id === "poemDialogOverlay") closePoemDialog();
});
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
        const overlay = document.getElementById("poemDialogOverlay");
        if (overlay.style.display === "flex") closePoemDialog();
    }
});

document.getElementById("poemSearchInput").addEventListener("input", (e) => {
    const keyword = e.target.value.trim().toLowerCase();
    if (!keyword) {
        renderPoemList(poemCache);
        return;
    }
    const filtered = poemCache.filter((p) => {
        return (p.title && p.title.toLowerCase().includes(keyword)) ||
               (p.author && p.author.toLowerCase().includes(keyword)) ||
               (p.dynasty && p.dynasty.toLowerCase().includes(keyword)) ||
               (p.content && p.content.toLowerCase().includes(keyword));
    });
    renderPoemList(filtered);
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
        // 恢复绘图风格
        if (data.option && data.option.art_style) {
            document.getElementById("creativeArtStyle").value = data.option.art_style;
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
    const artStyle = document.getElementById("creativeArtStyle").value;

    showStatus("creativeStatus", "正在保存创意...", "loading");
    const result = await apiFetch("/api/creative/save", {
        method: "POST",
        body: JSON.stringify({ creative, option_id: optionId, aspect_ratio: aspectRatio, art_style: artStyle }),
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
    const artStyle = document.getElementById("creativeArtStyle").value;

    // 先保存创意
    showStatus("creativeStatus", "正在保存创意并生成剧本...", "loading");
    await apiFetch("/api/creative/save", {
        method: "POST",
        body: JSON.stringify({ creative, option_id: optionId, aspect_ratio: aspectRatio, art_style: artStyle }),
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
        // 加载剧本时默认切换到预览模式
        activatePreviewMode();
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

// ============ 剧本 Markdown 预览切换 ============
let isPreviewMode = false;

function resetPreviewMode() {
    if (!isPreviewMode) return;
    isPreviewMode = false;
    document.getElementById('scriptEditor').style.display = 'block';
    document.getElementById('scriptPreview').style.display = 'none';
    const btn = document.getElementById('btnTogglePreview');
    btn.textContent = '预览';
    btn.classList.remove('active');
}

function activatePreviewMode() {
    const editor = document.getElementById('scriptEditor');
    const preview = document.getElementById('scriptPreview');
    const btn = document.getElementById('btnTogglePreview');
    if (!editor.value) {
        resetPreviewMode();
        return;
    }
    isPreviewMode = true;
    preview.innerHTML = marked.parse(editor.value);
    editor.style.display = 'none';
    preview.style.display = 'block';
    btn.textContent = '编辑';
    btn.classList.add('active');
}

document.getElementById('btnTogglePreview').addEventListener('click', () => {
    const editor = document.getElementById('scriptEditor');
    const preview = document.getElementById('scriptPreview');
    const btn = document.getElementById('btnTogglePreview');

    isPreviewMode = !isPreviewMode;

    if (isPreviewMode) {
        const md = editor.value;
        preview.innerHTML = marked.parse(md || '_（暂无剧本内容）_');
        editor.style.display = 'none';
        preview.style.display = 'block';
        btn.textContent = '编辑';
        btn.classList.add('active');
    } else {
        editor.style.display = 'block';
        preview.style.display = 'none';
        btn.textContent = '预览';
        btn.classList.remove('active');
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
                ? `<img class="char-img" src="${char.img}?t=${Date.now()}" alt="${char.name_cn}" onmouseenter="showImagePreview(this.src)" onmouseleave="hideImagePreview()">`
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
let currentVideos = [];
let currentVideoIndex = -1;
let isPlayingAll = false;

// 渲染分镜时间轴
function renderStoryboardTimeline(storyboard) {
    const container = document.getElementById("storyboardTimeline");
    if (!storyboard || storyboard.length === 0) {
        container.innerHTML = '<p class="empty-hint">暂无视频数据，请先生成视频</p>';
        return;
    }

    let html = "";
    storyboard.forEach((scene, index) => {
        const hasVideo = scene.video && scene.video.trim() !== "";
        html += `
        <div class="timeline-item ${hasVideo ? '' : 'no-video'}" data-index="${index}" data-scene-id="${scene.scene_id}">
            <div class="timeline-thumb">
                ${hasVideo
                    ? `<video src="${scene.video}" muted preload="metadata"></video>`
                    : `<div class="no-video">无视频</div>`
                }
            </div>
            <div class="timeline-info">
                <div class="timeline-scene-id">${scene.scene_id}</div>
                <div class="timeline-duration">${scene.duration || 0}秒</div>
            </div>
        </div>`;
    });
    container.innerHTML = html;

    // 绑定点击事件
    container.querySelectorAll('.timeline-item').forEach(item => {
        item.addEventListener('click', () => {
            const index = parseInt(item.dataset.index);
            playVideoAtIndex(index);
        });
    });

    // 绑定鼠标悬停预览事件
    container.querySelectorAll('.timeline-item').forEach(item => {
        const index = parseInt(item.dataset.index);
        const scene = storyboard[index];

        item.addEventListener('mouseenter', (e) => {
            if (scene.img_start || scene.img_end) {
                showTimelinePreview(scene, e.target);
            }
        });

        item.addEventListener('mouseleave', () => {
            hideTimelinePreview();
        });
    });
}

// 播放指定索引的视频
function playVideoAtIndex(index) {
    if (!currentVideos || index < 0 || index >= currentVideos.length) return;

    const video = currentVideos[index];
    if (!video.video) {
        showStatus("videoStatus", "该分镜暂无视频", "error");
        return;
    }

    currentVideoIndex = index;
    const mainPlayer = document.getElementById("mainPlayer");
    const overlay = document.getElementById("playerOverlay");

    mainPlayer.src = video.video;
    mainPlayer.play();

    // 隐藏遮罩
    overlay.classList.add('hidden');

    // 更新时间轴高亮
    updateTimelineHighlight();

    // 更新播放信息
    updatePlaybackInfo();
}

// 更新时间轴高亮
function updateTimelineHighlight() {
    const items = document.querySelectorAll('.timeline-item');
    items.forEach((item, index) => {
        item.classList.remove('active', 'played');
        if (index === currentVideoIndex) {
            item.classList.add('active');
            // 滚动到可视区域
            item.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
        } else if (index < currentVideoIndex) {
            item.classList.add('played');
        }
    });
}

// 更新播放信息
function updatePlaybackInfo() {
    const currentSceneEl = document.getElementById("currentScene");
    const progressEl = document.getElementById("playbackProgress");

    if (currentVideoIndex >= 0 && currentVideos[currentVideoIndex]) {
        const scene = currentVideos[currentVideoIndex];
        currentSceneEl.textContent = `${scene.scene_id} - ${scene.desc || ''}`.slice(0, 40);
    } else {
        currentSceneEl.textContent = '未选择';
    }

    progressEl.textContent = `${currentVideoIndex + 1} / ${currentVideos.length}`;
}

// 播放下一个视频
function playNextVideo() {
    if (!isPlayingAll) return;

    const nextIndex = currentVideoIndex + 1;
    if (nextIndex < currentVideos.length) {
        // 跳过没有视频的分镜
        if (currentVideos[nextIndex].video) {
            playVideoAtIndex(nextIndex);
        } else {
            currentVideoIndex = nextIndex;
            playNextVideo();
        }
    } else {
        // 播放完毕
        isPlayingAll = false;
        document.getElementById("playerOverlay").classList.remove('hidden');
        showStatus("videoStatus", "全部播放完毕", "success");
    }
}

// 加载视频数据
async function loadVideoData() {
    try {
        const data = await apiFetch("/api/storyboard/load");
        currentVideos = await convertStoryboardMediaUrls(data.storyboard || []);
        renderStoryboardTimeline(currentVideos);

        // 重置播放器
        const mainPlayer = document.getElementById("mainPlayer");
        mainPlayer.src = "";
        currentVideoIndex = -1;
        isPlayingAll = false;
        document.getElementById("playerOverlay").classList.remove('hidden');
        updatePlaybackInfo();
    } catch (e) {
        console.error("加载视频数据失败:", e);
    }
}

// 刷新按钮
document.getElementById("btnRefreshVideos").addEventListener("click", () => {
    loadVideoData();
    showStatus("videoStatus", "视频列表已刷新", "success");
});

// 播放全部按钮
document.getElementById("btnPlayAll").addEventListener("click", () => {
    if (!currentVideos || currentVideos.length === 0) {
        showStatus("videoStatus", "暂无视频可播放", "error");
        return;
    }

    // 找到第一个有视频的分镜
    const firstVideoIndex = currentVideos.findIndex(v => v.video);
    if (firstVideoIndex === -1) {
        showStatus("videoStatus", "没有可播放的视频", "error");
        return;
    }

    isPlayingAll = true;
    playVideoAtIndex(firstVideoIndex);
});

// 主播放器事件监听
document.addEventListener("DOMContentLoaded", () => {
    const mainPlayer = document.getElementById("mainPlayer");

    mainPlayer.addEventListener('ended', () => {
        if (isPlayingAll) {
            playNextVideo();
        }
    });

    mainPlayer.addEventListener('error', () => {
        if (isPlayingAll) {
            // 出错时继续播放下一个
            playNextVideo();
        }
    });
});

// 保留旧函数兼容
function renderVideoList(videos) {
    currentVideos = videos || [];
    renderStoryboardTimeline(currentVideos);
}

// ============ 分镜缩略图预览浮层 ============
let timelinePreviewTimer = null;

function showTimelinePreview(scene, targetEl) {
    // 清除之前的定时器，防止闪烁
    if (timelinePreviewTimer) {
        clearTimeout(timelinePreviewTimer);
        timelinePreviewTimer = null;
    }

    // 如果预览已存在，只更新内容不重新创建
    let preview = document.getElementById('timelinePreview');
    const imgUrl = scene.img_start || scene.img_end;

    if (!preview) {
        preview = document.createElement('div');
        preview.id = 'timelinePreview';
        preview.className = 'timeline-preview';
        // 阻止预览层上的鼠标事件穿透到底层
        preview.addEventListener('mouseenter', () => {
            if (timelinePreviewTimer) {
                clearTimeout(timelinePreviewTimer);
                timelinePreviewTimer = null;
            }
        });
        preview.addEventListener('mouseleave', () => {
            hideTimelinePreview();
        });
        document.body.appendChild(preview);
    }

    preview.innerHTML = `
        <div class="preview-content">
            <img src="${imgUrl}?t=${Date.now()}" alt="${scene.scene_id}">
            <div class="preview-info">
                <div class="preview-scene-id">${scene.scene_id}</div>
                <div class="preview-desc">${scene.desc || ''}</div>
            </div>
        </div>
    `;

    // 计算位置 - 显示在目标元素上方
    const rect = targetEl.getBoundingClientRect();
    const previewWidth = 400;
    const previewHeight = 280;

    let left = rect.left + (rect.width / 2) - (previewWidth / 2);
    let top = rect.top - previewHeight - 10;

    // 边界检查
    if (left < 10) left = 10;
    if (left + previewWidth > window.innerWidth - 10) {
        left = window.innerWidth - previewWidth - 10;
    }
    if (top < 10) {
        // 如果上方空间不足，显示在下方
        top = rect.bottom + 10;
    }

    preview.style.left = `${left}px`;
    preview.style.top = `${top}px`;

    // 添加显示动画
    requestAnimationFrame(() => {
        preview.classList.add('show');
    });
}

function hideTimelinePreview() {
    // 延迟隐藏，避免快速移动时闪烁
    timelinePreviewTimer = setTimeout(() => {
        const preview = document.getElementById('timelinePreview');
        if (preview) {
            preview.remove();
        }
        timelinePreviewTimer = null;
    }, 100);
}

// ============ 图片预览 ============
let imagePreviewTimer = null;

function showImagePreview(src) {
    // 清除之前的定时器，防止闪烁
    if (imagePreviewTimer) {
        clearTimeout(imagePreviewTimer);
        imagePreviewTimer = null;
    }

    let preview = document.getElementById("imagePreview");
    if (!preview) {
        preview = document.createElement("div");
        preview.id = "imagePreview";
        preview.className = "image-preview";
        preview.innerHTML = '<img src="" alt="预览">';
        // 阻止预览层上的鼠标事件穿透到底层
        preview.addEventListener('mouseenter', () => {
            if (imagePreviewTimer) {
                clearTimeout(imagePreviewTimer);
                imagePreviewTimer = null;
            }
        });
        preview.addEventListener('mouseleave', () => {
            hideImagePreview();
        });
        document.body.appendChild(preview);
    }
    preview.querySelector("img").src = src;
    preview.classList.add("show");
}

function hideImagePreview() {
    // 延迟隐藏，避免快速移动时闪烁
    imagePreviewTimer = setTimeout(() => {
        const preview = document.getElementById("imagePreview");
        if (preview) {
            preview.classList.remove("show");
        }
        imagePreviewTimer = null;
    }, 100);
}

// ============ 大图预览 ============

function showLargeImage(src) {
    let overlay = document.getElementById("largeImageOverlay");
    if (!overlay) {
        overlay = document.createElement("div");
        overlay.id = "largeImageOverlay";
        overlay.className = "large-image-overlay";
        overlay.innerHTML = '<img src="" alt="大图预览"><button class="large-image-close" onclick="hideLargeImage()">×</button>';
        overlay.addEventListener("click", (e) => {
            if (e.target === overlay || e.target.tagName === 'IMG') hideLargeImage();
        });
        document.body.appendChild(overlay);
    }
    overlay.querySelector("img").src = src;
    overlay.classList.add("show");
    document.body.style.overflow = "hidden";
}

function hideLargeImage() {
    const overlay = document.getElementById("largeImageOverlay");
    if (overlay) {
        overlay.classList.remove("show");
        document.body.style.overflow = "";
    }
}

// ============ 设置页面 ============

// ---- 引擎切换逻辑 ----
function initEngineToggles() {
    document.querySelectorAll('.engine-toggle').forEach(toggle => {
        toggle.addEventListener('change', (e) => {
            const radio = e.target;
            if (radio.type !== 'radio') return;
            const value = radio.value;
            const container = toggle.closest('.settings-section') || toggle.closest('.form-group');

            // 更新 toggle 按钮 active 状态
            toggle.querySelectorAll('.engine-option').forEach(opt => {
                const match = opt.dataset.engine === value || opt.dataset.mode === value;
                opt.classList.toggle('active', match);
            });

            // 切换引擎字段显示（仅对引擎 toggle 生效）
            if (container) {
                container.querySelectorAll('.engine-fields').forEach(fields => {
                    fields.style.display = fields.dataset.engine === value ? 'block' : 'none';
                });
            }
        });
    });
}

async function loadSettingsData() {
    try {
        const data = await apiFetch("/api/settings/load");
        if (!data.settings) return;
        const s = data.settings;

        // 文本处理 - 引擎
        const txtEngine = s.text_engine || "agnes";
        const txtRadio = document.querySelector('input[name="textEngine"][value="' + txtEngine + '"]');
        if (txtRadio) txtRadio.checked = true;
        const txtToggle = document.getElementById("textEngineToggle");
        const txtSection = txtToggle.closest('.settings-section');
        txtToggle.querySelectorAll('.engine-option').forEach(opt => {
            opt.classList.toggle('active', opt.dataset.engine === txtEngine);
        });
        txtSection.querySelectorAll('.engine-fields').forEach(fields => {
            fields.style.display = fields.dataset.engine === txtEngine ? 'block' : 'none';
        });

        // 文本处理 - 字段
        document.getElementById("settingsDeepseekKey").value = s.deepseek_api_key || "";
        document.getElementById("settingsDeepseekBase").value = s.deepseek_api_base || "";
        document.getElementById("settingsDeepseekModel").value = s.deepseek_model || "";
        document.getElementById("settingsArkTextModel").value = s.ark_text_model || "deepseek-v4-flash-260425";
        document.getElementById("settingsArkTextEndpoint").value = s.ark_text_endpoint || "";
        document.getElementById("settingsAgnesKey").value = s.agnes_api_key || "";
        document.getElementById("settingsAgnesBase").value = s.agnes_api_base || "";
        document.getElementById("settingsAgnesTextModel").value = s.agnes_text_model || "agnes-2.0-flash";

        // 图片处理 - 引擎
        const imgEngine = s.image_engine || "agnes";
        const imgRadio = document.querySelector('input[name="imageEngine"][value="' + imgEngine + '"]');
        if (imgRadio) imgRadio.checked = true;
        // 触发切换显示
        const imgToggle = document.getElementById("imageEngineToggle");
        const imgSection = imgToggle.closest('.settings-section');
        imgToggle.querySelectorAll('.engine-option').forEach(opt => {
            opt.classList.toggle('active', opt.dataset.engine === imgEngine);
        });
        imgSection.querySelectorAll('.engine-fields').forEach(fields => {
            fields.style.display = fields.dataset.engine === imgEngine ? 'block' : 'none';
        });

        // 图片处理 - 字段
        document.getElementById("settingsArkKey").value = s.ark_api_key || "";
        document.getElementById("settingsArkImageModel").value = s.ark_image_model || "doubao-seedream-4-5-251128";
        document.getElementById("settingsArkImageEndpoint").value = s.ark_image_endpoint || "";
        document.getElementById("settingsComfyHost").value = s.comfyui_host || "";
        document.getElementById("settingsComfyOutputDir").value = s.comfyui_output_dir || "";
        document.getElementById("settingsComfyImageWorkflow").value = s.comfyui_image_workflow || "";
        document.getElementById("settingsAgnesImageKey").value = s.agnes_api_key || "";
        document.getElementById("settingsAgnesImageModel").value = s.agnes_image_model || "agnes-image-2.1-flash";
        document.getElementById("settingsAgnesImageEndpoint").value = s.agnes_image_endpoint || "";

        // 视频处理 - 引擎
        const vidEngine = s.video_engine || "agnes";
        const vidRadio = document.querySelector('input[name="videoEngine"][value="' + vidEngine + '"]');
        if (vidRadio) vidRadio.checked = true;
        const vidToggle = document.getElementById("videoEngineToggle");
        const vidSection = vidToggle.closest('.settings-section');
        vidToggle.querySelectorAll('.engine-option').forEach(opt => {
            opt.classList.toggle('active', opt.dataset.engine === vidEngine);
        });
        vidSection.querySelectorAll('.engine-fields').forEach(fields => {
            fields.style.display = fields.dataset.engine === vidEngine ? 'block' : 'none';
        });

        // 视频处理 - 字段
        document.getElementById("settingsVideoComfyHost").value = s.comfyui_host || "";
        document.getElementById("settingsVideoComfyOutputDir").value = s.comfyui_output_dir || "";
        document.getElementById("settingsComfyVideoWorkflow").value = s.comfyui_video_workflow || "";
        document.getElementById("settingsArkVideoModel").value = s.ark_video_model || "doubao-seedance-2-0-fast-260128";
        document.getElementById("settingsArkVideoEndpoint").value = s.ark_video_endpoint || "";
        document.getElementById("settingsAgnesVideoKey").value = s.agnes_api_key || "";
        document.getElementById("settingsAgnesVideoModel").value = s.agnes_video_model || "agnes-video-v2.0";
        document.getElementById("settingsAgnesVideoEndpoint").value = s.agnes_video_endpoint || "";

    } catch (e) {
        console.error("加载设置失败:", e);
    }
}

document.getElementById("btnSaveSettings").addEventListener("click", async () => {
    const settings = {
        // 文本处理
        text_engine: document.querySelector('input[name="textEngine"]:checked')?.value || "agnes",
        deepseek_api_key: document.getElementById("settingsDeepseekKey").value.trim(),
        deepseek_api_base: document.getElementById("settingsDeepseekBase").value.trim(),
        deepseek_model: document.getElementById("settingsDeepseekModel").value.trim(),
        ark_text_model: document.getElementById("settingsArkTextModel").value.trim(),
        ark_text_endpoint: document.getElementById("settingsArkTextEndpoint").value.trim(),
        agnes_api_key: document.getElementById("settingsAgnesKey").value.trim(),
        agnes_api_base: document.getElementById("settingsAgnesBase").value.trim(),
        agnes_text_model: document.getElementById("settingsAgnesTextModel").value.trim(),
        // 图片处理
        image_engine: document.querySelector('input[name="imageEngine"]:checked')?.value || "agnes",
        ark_api_key: document.getElementById("settingsArkKey").value.trim(),
        ark_image_model: document.getElementById("settingsArkImageModel").value,
        ark_image_endpoint: document.getElementById("settingsArkImageEndpoint").value.trim(),
        comfyui_host: document.getElementById("settingsComfyHost").value.trim(),
        comfyui_output_dir: document.getElementById("settingsComfyOutputDir").value.trim(),
        comfyui_image_workflow: document.getElementById("settingsComfyImageWorkflow").value.trim(),
        agnes_image_model: document.getElementById("settingsAgnesImageModel").value.trim(),
        agnes_image_endpoint: document.getElementById("settingsAgnesImageEndpoint").value.trim(),
        // 视频处理
        video_engine: document.querySelector('input[name="videoEngine"]:checked')?.value || "agnes",
        comfyui_video_workflow: document.getElementById("settingsComfyVideoWorkflow").value.trim(),
        ark_video_model: document.getElementById("settingsArkVideoModel").value.trim(),
        ark_video_endpoint: document.getElementById("settingsArkVideoEndpoint").value.trim(),
        agnes_video_model: document.getElementById("settingsAgnesVideoModel").value.trim(),
        agnes_video_endpoint: document.getElementById("settingsAgnesVideoEndpoint").value.trim(),
    };

    showStatus("settingsStatus", "正在保存设置...", "loading");
    const result = await apiFetch("/api/settings/save", {
        method: "POST",
        body: JSON.stringify(settings),
    });

    if (result.success) {
        showStatus("settingsStatus", result.message || "设置已保存", "success");
    } else {
        showStatus("settingsStatus", result.error || "保存失败", "error");
    }
});

document.getElementById("btnTestConnection").addEventListener("click", async () => {
    showStatus("settingsStatus", "正在测试连接...", "loading");
    const result = await apiFetch("/api/settings/test", { method: "POST" });
    if (result.success) {
        showStatus("settingsStatus", result.message || "连接测试通过", "success");
    } else {
        showStatus("settingsStatus", result.error || "连接测试失败", "error");
    }
});

// 初始化引擎切换
initEngineToggles();

// ============ 双击复制 ============
document.addEventListener('dblclick', async (e) => {
    const el = e.target.closest('input[type="text"], input[type="password"], textarea');
    if (!el) return;

    const value = el.value;
    if (!value) return;

    try {
        await navigator.clipboard.writeText(value);
        showToast('已复制到剪贴板');
    } catch {
        // 降级方案
        el.select();
        document.execCommand('copy');
        showToast('已复制到剪贴板');
    }
});

// Toast 提示
function showToast(message) {
    let toast = document.getElementById('toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast';
        toast.className = 'toast';
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.remove('show'), 1500);
}

// ============ 主题切换 ============
const THEMES = ['default', 'light', 'macos', 'macos-dark'];
const THEME_ICONS = {
    'default': '🎋',
    'light': '☀️',
    'macos': '🍎',
    'macos-dark': '🌑'
};

function initTheme() {
    const themeToggle = document.getElementById('themeToggle');
    const themeDropdown = document.getElementById('themeDropdown');
    const root = document.documentElement;

    // 从localStorage读取主题设置
    const savedTheme = localStorage.getItem('theme') || 'default';
    applyTheme(savedTheme);

    // 切换下拉菜单显示
    themeToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        themeDropdown.classList.toggle('show');
    });

    // 点击外部关闭下拉菜单
    document.addEventListener('click', () => {
        themeDropdown.classList.remove('show');
    });

    // 主题选项点击事件
    document.querySelectorAll('.theme-option').forEach(option => {
        option.addEventListener('click', (e) => {
            e.stopPropagation();
            const theme = option.dataset.theme;
            applyTheme(theme);
            localStorage.setItem('theme', theme);
            themeDropdown.classList.remove('show');
        });
    });
}

function applyTheme(theme) {
    const root = document.documentElement;
    const themeToggle = document.getElementById('themeToggle');

    // 清除所有主题类
    root.classList.remove('light', 'macos', 'macos-dark');

    // 应用新主题
    if (theme !== 'default') {
        root.classList.add(theme);
    }

    // 更新按钮图标
    themeToggle.textContent = THEME_ICONS[theme] || '🎨';
}

// ============ 初始化 ============
document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    loadProjectList();
    loadTabData("creative");
    populateArtStyleDropdown();
});