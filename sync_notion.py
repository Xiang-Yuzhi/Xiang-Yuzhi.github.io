import os
import json
import requests
from slugify import slugify
from datetime import datetime

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

def get_page_content(page_id):
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        print(f"获取页面正文失败! 状态码: {res.status_code}, 详情: {res.text}")
        res.raise_for_status()
    return res.json()["results"]

def block_to_html(block):
    type = block["type"]
    if type == "paragraph":
        text = "".join([t["plain_text"] for t in block["paragraph"]["rich_text"]])
        return f"<p>{text}</p>"
    elif type == "heading_1":
        text = "".join([t["plain_text"] for t in block["heading_1"]["rich_text"]])
        return f"<h1>{text}</h1>"
    elif type == "heading_2":
        text = "".join([t["plain_text"] for t in block["heading_2"]["rich_text"]])
        return f"<h2>{text}</h2>"
    elif type == "heading_3":
        text = "".join([t["plain_text"] for t in block["heading_3"]["rich_text"]])
        return f"<h3>{text}</h3>"
    elif type == "bulleted_list_item":
        text = "".join([t["plain_text"] for t in block["bulleted_list_item"]["rich_text"]])
        return f"<li>{text}</li>"
    elif type == "numbered_list_item":
        text = "".join([t["plain_text"] for t in block["numbered_list_item"]["rich_text"]])
        return f"<li>{text}</li>"
    # 更多 Block 类型可以在以后扩展
    return ""

def generate_html(title, date, category, content_html):
    template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8" />
    <title>{title} | Rayne</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="stylesheet" href="../../styles.css" />
    <style>
        .post-container {{
            max-width: 800px;
            margin: 2rem auto;
            padding: 0 1.5rem 3rem;
        }}
        .post-container h1 {{ font-size: 2rem; margin-bottom: 0.5rem; }}
        .post-meta {{ font-size: 0.85rem; color: var(--muted); margin-bottom: 1.5rem; }}
        .post-container p {{ margin: 0.8rem 0; line-height: 1.7; }}
        .back-link {{ font-size: 0.85rem; margin-top: 2rem; }}
        .back-link a {{ color: var(--accent); text-decoration: none; }}
        .post-content img {{ max-width: 100%; border-radius: 8px; margin: 1rem 0; }}
        .post-content ul, .post-content ol {{ padding-left: 1.5rem; margin: 1rem 0; }}
    </style>
</head>
<body>
    <div class="post-container">
        <h1>{title}</h1>
        <div class="post-meta">{date} · {category}</div>
        <div class="post-content">
            {content_html}
        </div>
        <div class="back-link">
            ← <a href="../../index.html#{lower_category}">返回 {category} 列表</a>
        </div>
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

    for row in rows:
        props = row["properties"]
        
        # 提取属性
        try:
            title = props["Name"]["title"][0]["plain_text"] if props.get("Name") and props["Name"]["title"] else None
            if not title:
                print(f"跳过行 {row['id']}: 找不到标题(Name)")
                continue
                
            date_val = props.get("Date", {}).get("date")
            date = date_val["start"] if date_val else datetime.now().strftime("%Y-%m-%d")
            
            tags = [t["name"] for t in props.get("Tags", {}).get("multi_select", [])]
            
            excerpt_list = props.get("Excerpt", {}).get("rich_text", [])
            excerpt = "".join([t["plain_text"] for t in excerpt_list])
            
            cat_val = props.get("Category", {}).get("select")
            if not cat_val:
                print(f"跳过行 {title}: 找不到分类(Category)")
                continue
            category = cat_val["name"]
            
            slug_list = props.get("Slug", {}).get("rich_text", [])
            slug = "".join([t["plain_text"] for t in slug_list])
            if not slug:
                slug = slugify(title)
                
            print(f"正在处理文章: {title} ({category})")
        except Exception as e:
            print(f"处理行 {row['id']} 时出错: {str(e)}")
            continue

        # 获取正文
        blocks = get_page_content(row["id"])
        content_parts = []
        in_list = False
        for b in blocks:
            html = block_to_html(b)
            if b["type"] in ["bulleted_list_item", "numbered_list_item"]:
                if not in_list:
                    content_parts.append("<ul>" if b["type"] == "bulleted_list_item" else "<ol>")
                    in_list = True
                content_parts.append(html)
            else:
                if in_list:
                    content_parts.append("</ul>" if "bulleted" in content_parts[-1] else "</ol>")
                    in_list = False
                content_parts.append(html)
        if in_list:
            content_parts.append("</ul>")

        content_html = "\n".join(content_parts)
        
        # 生成 HTML 文件
        folder = "posts/blogs" if category.lower() == "blog" else "posts/notes"
        os.makedirs(folder, exist_ok=True)
        file_path = f"{folder}/{slug}.html"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(generate_html(title, date, category, content_html))
        
        # 准备 JSON 数据
        item = {
            "id": f"{category.lower()}-{slug}",
            "title": title,
            "date": date,
            "tags": tags,
            "excerpt": excerpt,
            "contentUrl": file_path
        }
        
        # 根据分类添加特定字段
        if category.lower() == "blog":
            item["badge"] = tags[0] if tags else "Blog"
            item["badgeStyle"] = "default"
            blog_data.append(item)
        else:
            item["category"] = "all" # 默认先设为 all，因为 Notion 里的 Category 可能是 Note
            notes_data.append(item)

    # 写入 JSON 文件
    with open("data/blog.json", "w", encoding="utf-8") as f:
        json.dump(blog_data, f, ensure_ascii=False, indent=2)
    
    with open("data/notes.json", "w", encoding="utf-8") as f:
        json.dump(notes_data, f, ensure_ascii=False, indent=2)

    print(f"同步完成！共同步 {len(rows)} 篇文章。")

if __name__ == "__main__":
    sync()
