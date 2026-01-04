import os
import json
import requests
from slugify import slugify
from datetime import datetime
import re

# --- 配置区 ---
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

if not NOTION_TOKEN or not DATABASE_ID:
    print("错误: 缺少环境变量 NOTION_TOKEN 或 DATABASE_ID")
    exit(1)

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

def get_db_rows():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {
        "filter": {
            "property": "Status",
            "select": {
                "equals": "Published"
            }
        }
    }
    print(f"正在查询数据库: {DATABASE_ID}...")
    res = requests.post(url, json=payload, headers=HEADERS)
    if res.status_code != 200:
        print(f"查询失败! 状态码: {res.status_code}, 详情: {res.text}")
        res.raise_for_status()
    return res.json()["results"]

def get_children(block_id):
    url = f"https://api.notion.com/v1/blocks/{block_id}/children"
    params = {"page_size": 100}
    results = []
    
    while True:
        res = requests.get(url, headers=HEADERS, params=params)
        if res.status_code != 200:
            print(f"获取子内容失败! 状态码: {res.status_code}, 详情: {res.text}")
            res.raise_for_status()
        data = res.json()
        results.extend(data["results"])
        if not data.get("has_more"):
            break
        params["start_cursor"] = data["next_cursor"]
        
    return results

def rich_text_to_html(rich_text):
    html = ""
    for rt in rich_text:
        text = rt["plain_text"]
        annot = rt["annotations"]
        if annot["bold"]: text = f"<b>{text}</b>"
        if annot["italic"]: text = f"<i>{text}</i>"
        if annot["strikethrough"]: text = f"<s>{text}</s>"
        if annot["underline"]: text = f"<u>{text}</u>"
        if annot["code"]: text = f"<code>{text}</code>"
        if rt.get("href"):
            text = f'<a href="{rt["href"]}">{text}</a>'
        html += text
    return html

def download_image(url, folder, filename):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    # 如果文件已经存在且不是空的，就不重复下载了（节省流量/时间）
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
        
    try:
        print(f"    -> 下载图片: {filename}")
        res = requests.get(url, stream=True, timeout=10)
        res.raise_for_status()
        with open(path, "wb") as f:
            for chunk in res.iter_content(chunk_size=8192):
                f.write(chunk)
        return path
    except Exception as e:
        print(f"下载图片失败: {e}")
        return url

def block_to_html(block, page_slug, assets_folder):
    type = block["type"]
    
    # 递归处理容器块（列、分栏等）
    if type == "column_list":
        cols = get_children(block["id"])
        html = '<div class="column-list" style="display: flex; gap: 1rem; flex-wrap: wrap;">'
        for col in cols:
            html += f'<div class="column" style="flex: 1; min-width: 250px;">'
            col_children = get_children(col["id"])
            for child in col_children:
                html += block_to_html(child, page_slug, assets_folder)
            html += '</div>'
        html += '</div>'
        return html
    
    if type == "paragraph":
        text = rich_text_to_html(block["paragraph"]["rich_text"])
        return f"<p>{text}</p>"
    elif type == "heading_1":
        text = rich_text_to_html(block["heading_1"]["rich_text"])
        return f"<h1>{text}</h1>"
    elif type == "heading_2":
        text = rich_text_to_html(block["heading_2"]["rich_text"])
        return f"<h2>{text}</h2>"
    elif type == "heading_3":
        text = rich_text_to_html(block["heading_3"]["rich_text"])
        return f"<h3>{text}</h3>"
    elif type == "bulleted_list_item":
        text = rich_text_to_html(block["bulleted_list_item"]["rich_text"])
        return f"<li>{text}</li>"
    elif type == "numbered_list_item":
        text = rich_text_to_html(block["numbered_list_item"]["rich_text"])
        return f"<li>{text}</li>"
    elif type == "quote":
        text = rich_text_to_html(block["quote"]["rich_text"])
        return f"<blockquote>{text}</blockquote>"
    elif type == "code":
        text = "".join([t["plain_text"] for t in block["code"]["rich_text"]])
        lang = block["code"].get("language", "")
        return f'<pre><code class="language-{lang}">{text}</code></pre>'
    elif type == "image":
        img_url = ""
        if block["image"]["type"] == "external":
            img_url = block["image"]["external"]["url"]
        else:
            img_url = block["image"]["file"]["url"]
        
        # 提取扩展名
        img_ext = "png"
        if ".jpg" in img_url.lower() or ".jpeg" in img_url.lower(): img_ext = "jpg"
        elif ".gif" in img_url.lower(): img_ext = "gif"
        elif ".svg" in img_url.lower(): img_ext = "svg"
        
        img_name = f"{page_slug}-{block['id'][:8]}.{img_ext}"
        download_image(img_url, assets_folder, img_name)
        
        rel_path = f"../../assets/posts/{img_name}"
        return f'<div class="post-image"><img src="{rel_path}" alt="Notion Image" loading="lazy"></div>'
    elif type == "table":
        rows = get_children(block["id"])
        has_header = block["table"]["has_column_header"]
        html = "<table>\n"
        if has_header:
            html += "<thead>\n"
        else:
            html += "<tbody>\n"
            
        for i, row in enumerate(rows):
            if has_header and i == 1:
                html += "</thead>\n<tbody>\n"
            
            html += "<tr>\n"
            for cell in row["table_row"]["cells"]:
                cell_content = rich_text_to_html(cell)
                tag = "th" if (has_header and i == 0) else "td"
                html += f"  <{tag}>{cell_content}</{tag}>\n"
            html += "</tr>\n"
        
        html += "</tbody>\n</table>"
        return html
    elif type == "callout":
        text = rich_text_to_html(block["callout"]["rich_text"])
        icon = ""
        if block["callout"].get("icon"):
            if block["callout"]["icon"]["type"] == "emoji":
                icon = f'<span class="callout-icon">{block["callout"]["icon"]["emoji"]}</span>'
        return f'<div class="callout">{icon}<div class="callout-text">{text}</div></div>'
    elif type == "divider":
        return "<hr>"
    
    return f"<!-- Unsupported block type: {type} -->"

def generate_html(title, date, category, content_html):
    template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8" />
    <title>{title} | Rayne</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="stylesheet" href="../../assets/styles.css" />
    <style>
        body {{
            background:
                radial-gradient(circle at 0% 0%, rgba(56,189,248,0.15), transparent 50%),
                radial-gradient(circle at 100% 0%, rgba(94,234,212,0.15), transparent 50%),
                #020617;
            color: var(--text);
            line-height: 1.7;
        }}
        .post-container {{
            max-width: 820px;
            margin: 0 auto;
            padding: 4rem 1.5rem 8rem;
        }}
        .post-container h1 {{ 
            font-size: 1.7rem; 
            margin-bottom: 0.5rem; 
            color: #fff;
            letter-spacing: -0.012em;
            line-height: 1.2;
        }}
        .post-meta {{ 
            font-size: 0.8rem; 
            color: var(--muted); 
            margin-bottom: 2.8rem; 
            padding-bottom: 0.9rem; 
            border-bottom: 1px solid rgba(148,163,184,0.1); 
        }}
        .post-content {{ 
            color: #d1d5db; 
            font-size: 0.88rem; 
            line-height: 1.62;
        }}
        .post-content p {{ margin: 0.9rem 0; }}
        .post-content h1 {{ margin: 2rem 0 0.8rem; font-size: 1.45rem; color: #fff; border-bottom: 1px solid var(--border); padding-bottom: 0.4rem; }}
        .post-content h2 {{ 
            margin: 2.22rem 0 0.8rem; 
            font-size: 1.3rem; 
            color: #fff;
            border-left: 3px solid var(--accent); 
            padding-left: 0.9rem; 
        }}
        .post-content h3 {{ margin: 1.7rem 0 0.6rem; font-size: 1.05rem; color: #fff; }}
        
        /* 列表 */
        .post-content ul, .post-content ol {{ padding-left: 1.4rem; margin: 1.1rem 0; }}
        .post-content li {{ margin: 0.45rem 0; }}
        
        /* 图片 */
        .post-image {{ margin: 1.8rem 0; text-align: center; }}
        .post-image img {{ 
            max-width: 100%; 
            border-radius: 10px; 
            border: 1px solid rgba(148, 163, 184, 0.12);
            box-shadow: 0 12px 35px rgba(0,0,0,0.3); 
        }}
        
        /* 表格 */
        table {{ 
            width: 100%; 
            border-collapse: separate; 
            border-spacing: 0;
            margin: 1.8rem 0; 
            font-size: 0.86rem; 
            border: 1px solid var(--border);
            border-radius: 10px;
            overflow: hidden;
            background: rgba(15, 23, 42, 0.35);
        }}
        th, td {{ 
            border-bottom: 1px solid var(--border); 
            border-right: 1px solid var(--border); 
            padding: 0.75rem; 
            text-align: left; 
        }}
        th {{ background: rgba(56, 189, 248, 0.04); font-weight: 600; color: var(--accent); }}
        tr:last-child td {{ border-bottom: none; }}
        td:last-child, th:last-child {{ border-right: none; }}
        
        /* 引用 */
        blockquote {{ 
            margin: 1.8rem 0; 
            padding: 0.9rem 1.4rem; 
            border-left: 2px solid var(--accent); 
            background: rgba(56, 189, 248, 0.04); 
            font-style: italic; 
            border-radius: 4px; 
            color: #94a3b8;
        }}
        
        /* 代码 */
        pre {{ 
            background: #0f172a; 
            padding: 1.1rem; 
            border-radius: 10px; 
            overflow-x: auto; 
            margin: 1.4rem 0; 
            border: 1px solid rgba(148, 163, 184, 0.1);
        }}
        code {{ font-family: 'Fira Code', monospace; font-size: 0.82rem; }}
        p code {{ 
            background: rgba(56, 189, 248, 0.08); 
            padding: 0.15rem 0.35rem; 
            border-radius: 4px; 
            color: var(--accent); 
            font-size: 0.88em;
        }}
        
        /* Callout */
        .callout {{ 
            display: flex; 
            align-items: flex-start; 
            gap: 0.9rem; 
            padding: 1rem; 
            background: rgba(148, 163, 184, 0.03); 
            border-radius: 8px; 
            margin: 1.4rem 0; 
            border: 1px solid rgba(148, 163, 184, 0.1); 
        }}
        .callout-icon {{ font-size: 1.3rem; line-height: 1; }}
        
        /* 返回链接 - 恢复并优化前几版的好看风格 */
        .back-link {{ font-size: 0.85rem; margin-top: 5rem; padding-top: 2rem; border-top: 1px solid rgba(148,163,184,0.1); }}
        .back-link a {{ 
            color: var(--accent); 
            text-decoration: none; 
            font-weight: 500; 
            padding: 0.6rem 1.3rem;
            background: rgba(56, 189, 248, 0.06);
            border: 1px solid rgba(56, 189, 248, 0.2);
            border-radius: 999px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .back-link a:hover {{ 
            background: rgba(56, 189, 248, 0.12);
            border-color: rgba(56, 189, 248, 0.4);
            box-shadow: 0 0 25px rgba(56, 189, 248, 0.25);
            transform: translateX(-4px);
        }}
    </style>
</head>
<body>
    <div class="post-container">
        <nav class="back-link" style="margin-top: 0; margin-bottom: 3.5rem; border-top: none; padding-top: 0;">
             <a href="../../index.html#{lower_category}">← 返回 {category} 列表</a>
        </nav>
        <header>
            <h1>{title}</h1>
            <div class="post-meta">{date} · {category}</div>
        </header>
        <article class="post-content">
            {content_html}
        </article>
        <footer class="back-link">
            <a href="../../index.html#{lower_category}">← 返回 {category} 列表</a>
        </footer>
    </div>
</body>
</html>"""
    lower_category = category.lower() if category.lower() != "note" else "notes"
    return template.format(
        title=title, 
        date=date, 
        category=category, 
        content_html=content_html,
        lower_category=lower_category
    )

def sync():
    rows = get_db_rows()
    blog_data = []
    notes_data = []
    
    ASSETS_FOLDER = "assets/posts"
    os.makedirs(ASSETS_FOLDER, exist_ok=True)

    for row in rows:
        props = row["properties"]
        
        try:
            title = props["Name"]["title"][0]["plain_text"] if props.get("Name") and props["Name"]["title"] else None
            if not title:
                continue
                
            date_val = props.get("Date", {}).get("date")
            date = date_val["start"] if date_val else datetime.now().strftime("%Y-%m-%d")
            
            tags = [t["name"] for t in props.get("Tags", {}).get("multi_select", [])]
            
            excerpt_list = props.get("Excerpt", {}).get("rich_text", [])
            excerpt = "".join([t["plain_text"] for t in excerpt_list])
            
            cat_val = props.get("Category", {}).get("select")
            if not cat_val:
                continue
            category = cat_val["name"]
            
            slug_list = props.get("Slug", {}).get("rich_text", [])
            slug = "".join([t["plain_text"] for t in slug_list])
            if not slug:
                slug = slugify(title)
                
            print(f"📡 正在拉取内容: {title} ({category})...")
        except Exception as e:
            print(f"处理行 {row['id']} 时出错: {str(e)}")
            continue

        # 获取正文（处理所有块）
        blocks = get_children(row["id"])
        content_parts = []
        in_list = False
        current_list_type = None

        for b in blocks:
            html = block_to_html(b, slug, ASSETS_FOLDER)
            
            # 列表处理逻辑
            is_list_item = b["type"] in ["bulleted_list_item", "numbered_list_item"]
            if is_list_item:
                list_type = "ul" if b["type"] == "bulleted_list_item" else "ol"
                if not in_list:
                    content_parts.append(f"<{list_type}>")
                    in_list = True
                    current_list_type = list_type
                elif current_list_type != list_type:
                    content_parts.append(f"</{current_list_type}><{list_type}>")
                    current_list_type = list_type
                content_parts.append(html)
            else:
                if in_list:
                    content_parts.append(f"</{current_list_type}>")
                    in_list = False
                    current_list_type = None
                content_parts.append(html)
        
        if in_list:
            content_parts.append(f"</{current_list_type}>")

        content_html = "\n".join(content_parts)
        
        # 生成 HTML 文件
        folder = "posts/blogs" if category.lower() == "blog" else "posts/notes"
        os.makedirs(folder, exist_ok=True)
        filename = f"{slug}.html"
        file_path = f"{folder}/{filename}"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(generate_html(title, date, category, content_html))
        
        # 准备 JSON 数据
        rel_content_url = f"posts/{'blogs' if category.lower() == 'blog' else 'notes'}/{filename}"
        item = {
            "id": f"{category.lower()}-{slug}",
            "title": title,
            "date": date,
            "tags": tags,
            "excerpt": excerpt,
            "contentUrl": rel_content_url
        }
        
        if category.lower() == "blog":
            item["badge"] = tags[0] if tags else "Blog"
            item["badgeStyle"] = "default"
            blog_data.append(item)
        else:
            item["category"] = "all"
            notes_data.append(item)

    # 写入 JSON 文件
    with open("data/blog.json", "w", encoding="utf-8") as f:
        json.dump(blog_data, f, ensure_ascii=False, indent=2)
    
    with open("data/notes.json", "w", encoding="utf-8") as f:
        json.dump(notes_data, f, ensure_ascii=False, indent=2)

    print(f"🎉 同步完成！共同步 {len(rows)} 篇文章。")

if __name__ == "__main__":
    sync()
