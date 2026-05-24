#!/usr/bin/env python3
"""Write Twitter/X extracted content into a local Markdown note."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

SKILL_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = SKILL_ROOT / "config.json"


def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


CONFIG = load_config()
VAULT_ROOT = Path(str(CONFIG.get("obsidian_vault") or "")).expanduser()
SAVE_ROOT = VAULT_ROOT / str(CONFIG.get("save_root") or "00-Inbox/Twitter")
DEFAULT_CATEGORY = str(CONFIG.get("default_category") or "知识资源")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)


def compact_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def sanitize_filename(name: str, limit: int = 50) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return (name[:limit].rstrip() or "Twitter内容")


def sanitize_tag(tag: str) -> str:
    tag = str(tag or "").strip().lstrip("#")
    tag = re.sub(r"\s+", "-", tag)
    tag = re.sub(r"[#,\[\]{}]+", "", tag)
    return tag or "Twitter"


def normalize_tags(tags: Any, category: str) -> List[str]:
    raw = tags if isinstance(tags, list) else []
    out = ["Twitter"]
    for item in raw:
        tag = sanitize_tag(str(item))
        if tag and tag not in out and tag not in ("知识收集", "创作素材"):
            out.append(tag)
    if len(out) == 1:
        out.append("知识收集" if category == "知识资源" else "创作素材")
    final_category = "创作素材" if category == "创作素材" else "知识收集"
    if final_category in out:
        out = [tag for tag in out if tag != final_category]
    out.append(final_category)
    return out[:6]


def date_part(value: str) -> str:
    value = compact_ws(str(value or ""))
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    if match:
        return match.group(0)
    return datetime.now().strftime("%Y-%m-%d")


def metric(data: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = compact_ws(str(value))
        if text:
            return text
    return "-"


def markdown_link(url: str) -> str:
    url = compact_ws(url)
    return f"[{url}]({url})" if url else "-"


def guess_ext(url: str, content_type: str) -> str:
    parsed = urllib.parse.urlparse(url)
    ext = Path(parsed.path).suffix.lower()
    if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        return ext
    guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip()) if content_type else None
    return guessed if guessed in (".jpg", ".jpeg", ".png", ".webp", ".gif") else ".jpg"


def download_image(url: str, dest_without_ext: Path) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as response:
        content_type = response.headers.get("Content-Type", "")
        data = response.read()
    dest = dest_without_ext.with_suffix(guess_ext(url, content_type))
    dest.write_bytes(data)
    return dest


def image_items(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    raw = payload.get("images") or []
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, str]] = []
    for item in raw:
        if isinstance(item, str):
            out.append({"url": item})
        elif isinstance(item, dict):
            url = compact_ws(str(item.get("url") or item.get("src") or ""))
            if url:
                out.append({
                    "url": url,
                    "alt": compact_ws(str(item.get("alt") or "")),
                    "after_text": compact_ws(str(item.get("after_text") or item.get("after") or "")),
                })
    return out


def download_images(payload: Dict[str, Any], note_path: Path, dry_run: bool) -> List[str]:
    items = image_items(payload)
    if not items:
        return []
    attachment_dir = note_path.with_suffix("").name + "附件"
    attachment_path = note_path.parent / attachment_dir
    if not dry_run:
        attachment_path.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    for idx, item in enumerate(items, start=1):
        if dry_run:
            ext = guess_ext(item["url"], "")
            rel = f"{attachment_dir}/{idx:02d}{ext}"
        else:
            try:
                dest = download_image(item["url"], attachment_path / f"{idx:02d}")
                rel = os.path.relpath(dest, start=note_path.parent)
            except Exception:
                rel = item["url"]
        alt = item.get("alt") or f"图{idx}"
        lines.append(f"![{alt}]({rel})")
    return lines


def render_replies(payload: Dict[str, Any]) -> str:
    replies = payload.get("replies") or payload.get("comments") or []
    if not isinstance(replies, list) or not replies:
        return "当前页面未提取到可见回复。"
    rows = ["| # | 用户 | 回复内容 | 互动 |", "|---|------|---------|------|"]
    for idx, item in enumerate(replies[:10], start=1):
        if not isinstance(item, dict):
            continue
        user = compact_ws(str(item.get("user") or item.get("author") or "-"))
        text = compact_ws(str(item.get("text") or item.get("content") or "-")).replace("|", "\\|")
        interaction = compact_ws(str(item.get("interaction") or item.get("likes") or "-"))
        rows.append(f"| {idx} | {user} | {text} | {interaction or '-'} |")
    return "\n".join(rows) if len(rows) > 2 else "当前页面未提取到可见回复。"


def classify(payload: Dict[str, Any], override: Optional[str]) -> str:
    if override in ("创作素材", "知识资源"):
        return override
    text = " ".join(str(payload.get(key) or "") for key in ("title", "text", "summary", "note"))
    if re.search(r"写作|选题|文案|表达|传播|账号|内容|创作", text):
        return "创作素材"
    return DEFAULT_CATEGORY if DEFAULT_CATEGORY in ("创作素材", "知识资源") else "知识资源"


def build_note(payload: Dict[str, Any], model: str, category: str, image_lines: List[str], note_path: Path) -> str:
    title = compact_ws(str(payload.get("title") or payload.get("text") or "Twitter内容"))
    title = sanitize_filename(title, 80)
    author = compact_ws(str(payload.get("author") or payload.get("name") or "-"))
    handle = compact_ws(str(payload.get("handle") or payload.get("username") or ""))
    original_url = compact_ws(str(payload.get("original_url") or payload.get("url") or ""))
    published = compact_ws(str(payload.get("published_at") or payload.get("date") or ""))
    created = datetime.now().strftime("%Y-%m-%d")
    interactions = payload.get("interactions") if isinstance(payload.get("interactions"), dict) else {}
    tags = normalize_tags(payload.get("tags"), category)
    note_type = "创作素材" if category == "创作素材" else "知识收集"
    summary = compact_ws(str(payload.get("summary") or "待根据正文提炼。"))
    text = str(payload.get("text") or payload.get("body") or "").strip()
    transcript = str(payload.get("transcript") or "").strip()
    video_path = compact_ws(str(payload.get("video_path") or payload.get("media_path") or ""))
    if video_path and Path(video_path).exists():
        try:
            video_path = os.path.relpath(Path(video_path), start=note_path.parent)
        except Exception:
            pass
    author_line = f"{author}（{handle}）" if handle else author
    image_block = ""
    if image_lines:
        image_block = "\n\n## 图片\n\n" + "\n\n".join(image_lines)
    transcript_block = ""
    if transcript:
        transcript_block = f"\n---\n\n## 媒体文字内容\n\n{transcript}\n"
    video_block = ""
    if video_path:
        video_block = f"\n---\n\n## 视频\n\n<video src=\"{video_path}\" controls></video>\n"
    return f"""---
tags: [{", ".join(tags)}]
created: {created}
type: {note_type}
source: Twitter
author: {author}
url: {original_url}
date: {date_part(published)}
激活:
  写作素材: {"true" if note_type == "创作素材" else "false"}
  待试: false
  学习: {"false" if note_type == "创作素材" else "true"}
  策展: []
  个人用途: true
note: {compact_ws(str(payload.get("note") or summary))[:80]}
---

# {date_part(published)} {title}

**作者：** {author_line}
**来源：** Twitter/X
**原链接：** {markdown_link(original_url)}
**发布时间：** {published or date_part(published)}
**互动数据：** 回复 {metric(interactions, "reply", "replies", "reply_count")} | 转发 {metric(interactions, "repost", "retweet", "reposts", "repost_count")} | 喜欢 {metric(interactions, "like", "likes", "like_count")} | 浏览 {metric(interactions, "view", "views", "view_count")} | 书签 {metric(interactions, "bookmark", "bookmarks", "bookmark_count")}

---

## 正文内容

{text or "（无可见正文）"}{image_block}

---

## 内容摘要

{summary}

---

## 热门回复（Top 10）

{render_replies(payload)}
{transcript_block}{video_block}
---

*保存时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}*

---

*由 [twitter-reader](https://github.com/Jiaranbb/content-reader-skills/tree/main/twitter-reader) 提取保存 | 作者：嘉然 · 公众号「嘉然学习笔记」*
"""


def note_path_for(payload: Dict[str, Any], category: str) -> Path:
    title = sanitize_filename(compact_ws(str(payload.get("title") or payload.get("text") or "Twitter内容")), 50)
    date = date_part(str(payload.get("published_at") or payload.get("date") or ""))
    folder = SAVE_ROOT / category
    return folder / f"{date}-X-{title}.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a Twitter/X Obsidian note from browser-extracted JSON")
    parser.add_argument("--input-json", required=True, type=Path)
    parser.add_argument("--category", choices=("创作素材", "知识资源"), default=None)
    parser.add_argument("--model", default="GPT-5")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("input JSON must be an object")
    category = classify(payload, args.category)
    path = note_path_for(payload, category)
    images = download_images(payload, path, args.dry_run)
    note = build_note(payload, args.model, category, images, path)
    if args.dry_run:
        print(json.dumps({"path": str(path), "category": category, "preview": note[:1200]}, ensure_ascii=False, indent=2))
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(note, encoding="utf-8")
    print(json.dumps({"path": str(path), "category": category, "image_count": len(images)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
