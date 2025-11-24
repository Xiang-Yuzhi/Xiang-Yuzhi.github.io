document.addEventListener("DOMContentLoaded", function () {
    const yearSpan = document.getElementById("year");
    if (yearSpan) {
        yearSpan.textContent = new Date().getFullYear();
    }

    // 先加载数据，再初始化搜索和过滤
    Promise.all([loadBlog(), loadNotes()]).then(() => {
        setupGlobalSearch();
        setupBlogSearch();
        setupNotesFilter();
        setupNotesSearch();
    });
});

/* ========== 加载 Blog 数据 ========== */
function loadBlog() {
    const list = document.getElementById("blog-list");
    const loading = document.getElementById("blog-loading");
    if (!list) return Promise.resolve();

    return fetch("data/blog.json")
        .then((res) => res.json())
        .then((posts) => {
            list.innerHTML = "";
            posts.forEach((post) => {
                const article = document.createElement("article");
                article.className = "blog-card";
                article.setAttribute("data-tags", (post.tags || []).join(","));
                article.setAttribute("data-id", post.id || "");

                article.innerHTML = `
                    <div class="card-meta">
                        <span class="badge ${post.badgeStyle === "soft" ? "badge-soft" : ""}">
                            ${post.badge || "Blog"}
                        </span>
                        <span class="date">${post.date || ""}</span>
                    </div>
                    <h3 class="card-title">${post.title}</h3>
                    <p class="card-excerpt">${post.excerpt || ""}</p>
                    <div class="card-tags">
                        ${(post.tags || [])
                            .map((tag) => `<span>#${tag}</span>`)
                            .join("")}
                    </div>
                    ${
                        post.contentUrl
                            ? `<div style="margin-top:0.4rem;">
                                    <a href="${post.contentUrl}" class="btn secondary" style="font-size:0.78rem; padding:0.25rem 0.8rem;" target="_blank" rel="noopener">
                                        阅读全文 →
                                    </a>
                               </div>`
                            : ""
                    }
                `;
                list.appendChild(article);
            });
        })
        .catch((err) => {
            console.error("加载 blog.json 失败:", err);
            if (loading) loading.textContent = "Failed to load blog posts.";
        });
}

/* ========== 加载 Notes 数据 ========== */
function loadNotes() {
    const list = document.getElementById("notes-list");
    const loading = document.getElementById("notes-loading");
    if (!list) return Promise.resolve();

    return fetch("data/notes.json")
        .then((res) => res.json())
        .then((notes) => {
            list.innerHTML = "";
            notes.forEach((note) => {
                const article = document.createElement("article");
                article.className = "note-card";
                article.setAttribute("data-category", note.category || "all");
                article.setAttribute("data-id", note.id || "");

                const linksHtml = (note.links || [])
                    .map(
                        (link) => `
                        <a href="${link.url}" target="_blank" rel="noopener">
                            ${link.label}
                        </a>`
                    )
                    .join("");

                article.innerHTML = `
                    <h3 class="card-title">${note.title}</h3>
                    <p class="card-excerpt">${note.excerpt || ""}</p>
                    ${
                        linksHtml
                            ? `<div class="note-links">${linksHtml}</div>`
                            : ""
                    }
                    <div class="card-tags">
                        ${(note.tags || [])
                            .map((tag) => `<span>#${tag}</span>`)
                            .join("")}
                    </div>
                    ${
                        note.contentUrl
                            ? `<div style="margin-top:0.4rem;">
                                    <a href="${note.contentUrl}" class="btn secondary" style="font-size:0.78rem; padding:0.25rem 0.8rem;" target="_blank" rel="noopener">
                                        查看详细笔记 →
                                    </a>
                               </div>`
                            : ""
                    }
                `;
                list.appendChild(article);
            });
        })
        .catch((err) => {
            console.error("加载 notes.json 失败:", err);
            if (loading) loading.textContent = "Failed to load notes.";
        });
}

/* ========== 工具函数：显示全部卡片 ========== */
function showAllBlogCards() {
    document.querySelectorAll(".blog-card").forEach((card) => {
        card.style.display = "";
    });
}

function showAllNoteCards() {
    document.querySelectorAll(".note-card").forEach((card) => {
        card.style.display = "";
    });
}

/* ========== 顶部全局搜索：搜索 Blog + Notes ========== */
function setupGlobalSearch() {
    const globalInput = document.getElementById("global-search");
    if (!globalInput) return;

    globalInput.addEventListener("input", function () {
        const keyword = this.value.toLowerCase().trim();

        const blogInput = document.getElementById("blog-search");
        const notesInput = document.getElementById("notes-search");
        if (keyword && blogInput) blogInput.value = "";
        if (keyword && notesInput) notesInput.value = "";

        const blogCards = document.querySelectorAll(".blog-card");
        const noteCards = document.querySelectorAll(".note-card");

        if (!keyword) {
            showAllBlogCards();
            showAllNoteCards();
            return;
        }

        blogCards.forEach((card) => {
            const text = card.textContent.toLowerCase();
            card.style.display = text.includes(keyword) ? "" : "none";
        });

        noteCards.forEach((card) => {
            const text = card.textContent.toLowerCase();
            card.style.display = text.includes(keyword) ? "" : "none";
        });
    });
}

/* ========== Blog 区域搜索 ========== */
function setupBlogSearch() {
    const searchInput = document.getElementById("blog-search");
    if (!searchInput) return;

    searchInput.addEventListener("input", function () {
        const keyword = this.value.toLowerCase().trim();

        const globalInput = document.getElementById("global-search");
        if (keyword && globalInput) globalInput.value = "";

        const blogCards = document.querySelectorAll(".blog-card");
        blogCards.forEach((card) => {
            const title =
                (card.querySelector(".card-title")?.textContent || "").toLowerCase();
            const tagsText =
                (card.querySelector(".card-tags")?.textContent || "").toLowerCase();
            const dataTags = (card.getAttribute("data-tags") || "").toLowerCase();
            const excerpt =
                (card.querySelector(".card-excerpt")?.textContent || "").toLowerCase();

            const matched =
                !keyword ||
                title.includes(keyword) ||
                tagsText.includes(keyword) ||
                dataTags.includes(keyword) ||
                excerpt.includes(keyword);

            card.style.display = matched ? "" : "none";
        });
    });
}

/* ========== Notes 分类 Filter ========== */
function setupNotesFilter() {
    const filterSelect = document.getElementById("notes-filter");
    if (!filterSelect) return;

    filterSelect.addEventListener("change", function () {
        const value = this.value;
        const keyword =
            (document.getElementById("notes-search")?.value || "")
                .toLowerCase()
                .trim();
        const globalInput = document.getElementById("global-search");

        const noteCards = document.querySelectorAll(".note-card");
        noteCards.forEach((card) => {
            const category = card.getAttribute("data-category") || "all";
            const text = card.textContent.toLowerCase();
            const matchCategory = value === "all" || value === category;
            const matchKeyword = !keyword || text.includes(keyword);
            const matchGlobal = !globalInput || !globalInput.value;

            const show = matchCategory && matchKeyword && matchGlobal;
            card.style.display = show ? "" : "none";
        });
    });
}

/* ========== Notes 搜索（配合 Filter） ========== */
function setupNotesSearch() {
    const searchInput = document.getElementById("notes-search");
    const filterSelect = document.getElementById("notes-filter");
    if (!searchInput) return;

    searchInput.addEventListener("input", function () {
        const keyword = this.value.toLowerCase().trim();
        const filterValue = filterSelect ? filterSelect.value : "all";

        const globalInput = document.getElementById("global-search");
        if (keyword && globalInput) globalInput.value = "";

        const noteCards = document.querySelectorAll(".note-card");
        noteCards.forEach((card) => {
            const category = card.getAttribute("data-category") || "all";
            const text = card.textContent.toLowerCase();
            const matchCategory = filterValue === "all" || filterValue === category;
            const matchKeyword = !keyword || text.includes(keyword);
            const show = matchCategory && matchKeyword;
            card.style.display = show ? "" : "none";
        });
    });
}
