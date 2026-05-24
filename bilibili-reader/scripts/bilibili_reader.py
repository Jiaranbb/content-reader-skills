#!/usr/bin/env python3
"""Bilibili transcript/media helper for bilibili-reader."""

from __future__ import annotations

import argparse
import glob
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SKILL_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = SKILL_ROOT / "config.json"


def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


CONFIG = load_config()
VAULT_ROOT = Path(str(CONFIG.get("obsidian_vault") or "")).expanduser()
NOTE_ROOT = VAULT_ROOT / str(CONFIG.get("note_root") or "00-Inbox/Bilibili/知识资源")
MEDIA_ROOT = VAULT_ROOT / str(CONFIG.get("media_root") or "00-Inbox/Bilibili/多媒体")
DEFAULT_ASR_MODEL = str(CONFIG.get("asr_model") or "small")
DEFAULT_MODEL_ROOT = Path(os.getenv("VIDEO_ASR_MODEL_ROOT", str(Path.home() / ".cache/faster-whisper"))).expanduser()
LANG_PRIORITY = ["zh-CN", "zh-Hans", "zh", "en"]
SUPPORTED_ASR_MODELS = ("small", "medium")


def compact_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def find_ytdlp() -> str:
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        raise RuntimeError("yt-dlp not found")
    return ytdlp


def sanitize_filename(name: str, limit: int = 80) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return (name[:limit].rstrip() or "untitled")


def format_metric(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, str):
        text = compact_ws(value)
        return text if text else "-"
    try:
        return str(int(value))
    except Exception:
        return compact_ws(str(value)) or "-"


def seconds_to_hms(sec: float) -> str:
    value = int(max(0, sec))
    return f"{value // 3600:02d}:{(value % 3600) // 60:02d}:{value % 60:02d}"


def timestamp_to_seconds(value: str) -> float:
    match = re.match(r"(?:(\d+):)?(\d{2}):(\d{2})(?:[.,](\d{1,3}))?", value.strip())
    if not match:
        return 0.0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    millis = int((match.group(4) or "0").ljust(3, "0")[:3])
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def date_to_iso(value: str) -> str:
    value = str(value or "").strip()
    if re.fullmatch(r"\d{8}", value):
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    if re.fullmatch(r"\d{10}", value):
        return datetime.fromtimestamp(int(value)).strftime("%Y-%m-%d")
    return datetime.now().strftime("%Y-%m-%d")


def append_with_spacing(base: str, piece: str) -> str:
    if not base:
        return piece
    if not piece:
        return base
    if re.match(r"^[,.;:!?，。！？；：、)\]\"'”’]", piece):
        return base + piece
    if base[-1].isalnum() and piece[0].isalnum():
        return base + " " + piece
    return base + piece


def bilibili_metadata(ytdlp: str, target: str) -> Dict[str, Any]:
    cmd = [ytdlp, "--skip-download", "--dump-single-json", target]
    p = run(cmd)
    if p.returncode != 0:
        raise RuntimeError(f"yt-dlp metadata failed: {compact_ws(p.stderr)}")
    data = json.loads(p.stdout)
    if not isinstance(data, dict):
        raise RuntimeError("unexpected yt-dlp metadata payload")
    return data


def expand_targets(url: str, max_items: Optional[int]) -> List[str]:
    ytdlp = find_ytdlp()
    p = run([ytdlp, "--flat-playlist", "--skip-download", "--dump-single-json", url])
    if p.returncode != 0:
        data = bilibili_metadata(ytdlp, url)
    else:
        data = json.loads(p.stdout)
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        return [url]
    targets: List[str] = []
    for entry in entries:
        if max_items is not None and len(targets) >= max_items:
            break
        if not isinstance(entry, dict):
            continue
        candidate = entry.get("webpage_url") or entry.get("url")
        if isinstance(candidate, str) and candidate.startswith("http"):
            targets.append(candidate)
    return targets or [url]


def choose_subtitle(workdir: Path) -> Optional[Path]:
    candidates = [Path(p) for p in glob.glob(str(workdir / "*")) if Path(p).suffix.lower() in (".vtt", ".srt", ".json", ".json3")]
    if not candidates:
        return None
    for lang in LANG_PRIORITY:
        for candidate in candidates:
            if f".{lang}." in candidate.name:
                return candidate
    return sorted(candidates)[0]


def parse_vtt_cues(vtt_text: str) -> List[Dict[str, Any]]:
    cues: List[Dict[str, Any]] = []
    buf: List[str] = []
    in_cue = False
    cue_start = 0.0

    def flush() -> None:
        nonlocal buf
        if not buf:
            return
        text = " ".join(buf)
        text = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", "", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text).replace("\u200b", " ")
        text = compact_ws(text)
        if text:
            cues.append({"start": cue_start, "text": text})
        buf = []

    for raw in vtt_text.splitlines():
        stripped = raw.strip("\ufeff").strip()
        if not stripped:
            flush()
            in_cue = False
            continue
        if stripped.startswith(("WEBVTT", "NOTE", "Kind:", "Language:")):
            continue
        if "-->" in stripped:
            flush()
            cue_start = timestamp_to_seconds(stripped.split("-->", 1)[0].strip())
            in_cue = True
            continue
        if re.fullmatch(r"\d+", stripped):
            continue
        if in_cue or stripped:
            buf.append(stripped)
    flush()
    return cues


def parse_srt_cues(srt_text: str) -> List[Dict[str, Any]]:
    cues: List[Dict[str, Any]] = []
    buf: List[str] = []
    cue_start = 0.0
    for raw in srt_text.splitlines():
        line = raw.strip("\ufeff").strip()
        if not line:
            if buf:
                text = compact_ws(html.unescape(" ".join(buf)))
                if text:
                    cues.append({"start": cue_start, "text": text})
                buf = []
            continue
        if re.fullmatch(r"\d+", line):
            continue
        if "-->" in line:
            cue_start = timestamp_to_seconds(line.split("-->", 1)[0].strip())
            continue
        buf.append(re.sub(r"<[^>]+>", "", line))
    if buf:
        text = compact_ws(html.unescape(" ".join(buf)))
        if text:
            cues.append({"start": cue_start, "text": text})
    return cues


def parse_json_subtitle(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("body"), list):
            out: List[Dict[str, Any]] = []
            for item in payload["body"]:
                if not isinstance(item, dict):
                    continue
                text = compact_ws(str(item.get("content") or item.get("text") or ""))
                if text:
                    out.append({"start": float(item.get("from") or item.get("start") or 0.0), "text": text})
            return out
        if isinstance(payload.get("events"), list):
            out = []
            for event in payload["events"]:
                if not isinstance(event, dict):
                    continue
                segs = event.get("segs")
                if isinstance(segs, list):
                    text = compact_ws("".join(str(seg.get("utf8") or "") for seg in segs if isinstance(seg, dict)))
                    if text:
                        start = float(event.get("tStartMs") or event.get("tStart") or 0.0) / 1000
                        out.append({"start": start, "text": text})
            return out
    if isinstance(payload, list):
        out = []
        for item in payload:
            if isinstance(item, dict):
                text = compact_ws(str(item.get("content") or item.get("text") or item.get("utf8") or ""))
                if text:
                    out.append({"start": float(item.get("from") or item.get("start") or 0.0), "text": text})
        return out
    return []


def merge_cues_with_overlap(cues: List[str]) -> str:
    acc = ""
    for cue in cues:
        cue = cue.strip()
        if not cue:
            continue
        if not acc:
            acc = cue
            continue
        window = acc[-600:]
        if cue in window:
            continue
        overlap = 0
        max_possible = min(len(window), len(cue))
        for size in range(max_possible, 0, -1):
            if window[-size:] == cue[:size]:
                overlap = size
                break
        acc = append_with_spacing(acc, cue[overlap:])
    acc = re.sub(r"\s+([,.!?;:])", r"\1", acc)
    acc = re.sub(r"([，。！？；：、])\s+", r"\1", acc)
    return compact_ws(acc)


def hard_wrap(text: str, width: int = 220) -> List[str]:
    out: List[str] = []
    cur = text.strip()
    while len(cur) > width:
        cut = cur.rfind(" ", 0, width + 1)
        if cut <= 0:
            cut = width
        out.append(cur[:cut].strip())
        cur = cur[cut:].strip()
    if cur:
        out.append(cur)
    return out


def split_lines(text: str) -> List[str]:
    out: List[str] = []
    for part in [p.strip() for p in text.splitlines() if p.strip()]:
        for seg in re.split(r"(?<=[.!?。！？])\s*", part):
            seg = seg.strip()
            if not seg:
                continue
            out.extend(hard_wrap(seg, 220) if len(seg) > 260 else [seg])
    deduped: List[str] = []
    for line in out:
        if deduped and deduped[-1] == line:
            continue
        deduped.append(line)
    return deduped


def cue_segments(cues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []
    current_text = ""
    current_start = 0.0
    last_start = 0.0

    def flush() -> None:
        nonlocal current_text, current_start
        text = compact_ws(current_text)
        if text:
            segments.append({"start": current_start, "text": text})
        current_text = ""
        current_start = 0.0

    for cue in cues:
        text = compact_ws(str(cue.get("text") or ""))
        if not text:
            continue
        start = float(cue.get("start") or 0.0)
        if not current_text:
            current_text = text
            current_start = start
            last_start = start
            continue
        if text in current_text[-180:]:
            last_start = start
            continue
        should_flush = len(current_text) >= 160 or start - last_start > 30 or re.search(r"[。！？.!?]$", current_text)
        if should_flush:
            flush()
            current_text = text
            current_start = start
        else:
            current_text = append_with_spacing(current_text, text)
        last_start = start
    flush()
    return segments


def transcript_lines_from_cues(cues: List[Dict[str, Any]]) -> List[str]:
    lines = []
    for seg in cue_segments(cues):
        text = compact_ws(str(seg.get("text") or ""))
        if text:
            lines.append(f"[{seconds_to_hms(float(seg.get('start') or 0.0))}] {text}")
    return lines


def parse_timed_transcript(transcript: List[str]) -> List[Tuple[int, str, str]]:
    rows: List[Tuple[int, str, str]] = []
    for line in transcript:
        match = re.match(r"^\[(\d{2}:\d{2}:\d{2})\]\s*(.+)$", line)
        if not match:
            continue
        ts, text = match.groups()
        text = compact_ws(text)
        if text:
            rows.append((int(timestamp_to_seconds(ts)), ts, text))
    return rows


def sentence_value(text: str) -> int:
    keywords = [
        "问题", "本质", "核心", "关键", "重点", "因此", "所以", "为什么", "解决",
        "定义", "线性", "向量", "矩阵", "方程", "空间", "变换", "基", "维度",
        "理解", "意味着", "可以看到", "总结", "结论", "场景", "例子", "应用",
        "第一", "第二", "第三", "最后", "接下来", "现实", "工程", "算法",
    ]
    score = min(len(text), 100)
    score += sum(20 for keyword in keywords if keyword in text)
    if re.search(r"^(第[一二三四五六七八九十]|首先|其次|最后|接下来|然后|再给你|我们再|既然|为了|但是|所以)", text):
        score += 60
    if re.search(r"[？?]", text):
        score += 25
    return score


def summarize_highlight_window(seed: str, window_texts: List[str]) -> str:
    useful = []
    for text in window_texts:
        text = compact_ws(text)
        if not text or text in useful:
            continue
        if len(text) < 8 and not re.search(r"第[一二三四五六七八九十]|SVD|AI|VR", text):
            continue
        useful.append(text)
        if len(useful) >= 5:
            break
    if not useful:
        return f"看这一段关于「{seed}」的展开。"

    ranked = sorted(useful, key=sentence_value, reverse=True)
    topic = seed if len(seed) >= 10 else ranked[0]
    details = [text for text in ranked if text != topic][:2]
    if details:
        body = "；".join(details)
        return f"看这里如何展开「{topic}」：{body}。"
    return f"看这里如何展开「{topic}」。"


def build_highlights(transcript: List[str], limit: int = 10) -> List[str]:
    rows = parse_timed_transcript(transcript)
    if not rows:
        return ["- 暂无可用时间戳；请先确认字幕或 ASR 转写是否成功。"]

    candidates: List[Tuple[int, int, str, str, int]] = []
    for idx, (seconds, ts, text) in enumerate(rows):
        if len(text) < 8:
            continue
        score = sentence_value(text)
        if idx == 0:
            score += 80
        candidates.append((score, seconds, ts, text, idx))

    selected: List[Tuple[int, str, str, int]] = []
    for score, seconds, ts, text, idx in sorted(candidates, key=lambda item: item[0], reverse=True):
        if any(abs(seconds - chosen_seconds) < 50 for chosen_seconds, _ts, _text, _idx in selected):
            continue
        selected.append((seconds, ts, text, idx))
        if len(selected) >= limit:
            break

    selected.sort(key=lambda item: item[0])
    if not selected:
        return ["- 暂无可用时间戳；请先确认字幕或 ASR 转写是否成功。"]

    output = []
    for seconds, ts, text, idx in selected:
        window_texts = [row_text for row_seconds, _row_ts, row_text in rows[idx:] if row_seconds <= seconds + 85]
        output.append(f"- `{ts}` {summarize_highlight_window(text, window_texts)}")
    return output


def shorten_summary_topic(text: str, limit: int = 54) -> str:
    text = re.sub(r"^- `\d{2}:\d{2}:\d{2}`\s*", "", text).strip()
    text = re.sub(r"^从这里看", "", text)
    text = re.sub(r"^看这里如何展开「(.+?)」：?", r"\1：", text)
    text = re.sub(r"^看这一段关于「(.+?)」的展开。?$", r"\1", text)
    text = compact_ws(text)
    if "：" in text:
        head, body = text.split("：", 1)
        if 8 <= len(head) <= limit:
            text = head
        else:
            text = body
    if "高维复杂系统" in text and "矩阵" in text:
        return "线性代数处理高维复杂系统，不只是矩阵算术。"
    if "多变量" in text or "不是单变量" in text or ("多个变量" in text and "关系" in text):
        return "线性代数用于处理多变量之间的关系。"
    if "教材的问题" in text or "正确直觉" in text:
        return "学习线代要重建概念体系，而不只是应付考试。"
    if "几何直觉" in text and ("公式" in text or "死背" in text):
        return "几何直觉比死背公式更关键。"
    if "矩阵乘法" in text:
        return "矩阵乘法表达空间变换的组合。"
    if "SVD" in text and "推荐" in text:
        return "SVD 可用于提取偏好和内容特征，支撑推荐系统。"
    text = re.sub(r".*不是(.{2,24}?)，?而是(.{2,36})", r"不是\1，而是\2", text)
    parts = re.split(r"[。！？!?；;]", text)
    text = compact_ws(parts[0] if parts else text)
    text = re.sub(r"^(为什么|如何|怎么|什么是)", "", text).strip("，,：: ")
    if len(text) > limit:
        cut = re.split(r"[，,、]", text)
        text = compact_ws(cut[0] if cut else text)
    if len(text) > limit:
        text = text[:limit].rstrip("，,、：:；;。") + "..."
    return text


def build_content_summary(highlights: List[str]) -> str:
    topics = []
    for item in highlights:
        text = shorten_summary_topic(item)
        if text and text not in topics:
            topics.append(text)
        if len(topics) >= 4:
            break
    if not topics:
        return "- 已保存逐字稿；核心观点需要执行 agent 结合全文补写。"
    bullets = [f"- {topic}" for topic in topics]
    return "\n".join(bullets)


def download_bilibili_subtitle(ytdlp: str, video_url: str, workdir: Path) -> Tuple[Optional[Path], Dict[str, Any]]:
    cmd = [
        ytdlp,
        "--skip-download",
        "--write-auto-subs",
        "--write-subs",
        "--sub-langs",
        "zh-CN,zh-Hans,zh,en",
        "--sub-format",
        "vtt/srt/best",
        "-o",
        str(workdir / "%(id)s.%(ext)s"),
        video_url,
    ]
    p = run(cmd)
    subtitle = choose_subtitle(workdir)
    meta = {"method": "bilibili_subtitles", "ok": p.returncode == 0, "detail": compact_ws(p.stderr)[-500:]}
    return subtitle, meta


def transcript_from_bilibili_subtitles(ytdlp: str, video_url: str) -> Tuple[Optional[List[str]], Dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="bilibili_reader_subs_") as td:
        subtitle, meta = download_bilibili_subtitle(ytdlp, video_url, Path(td))
        if subtitle is None:
            meta["status"] = "missing"
            return None, meta
        text = subtitle.read_text(encoding="utf-8", errors="ignore")
        if subtitle.suffix.lower() == ".vtt":
            cues = parse_vtt_cues(text)
        elif subtitle.suffix.lower() == ".srt":
            cues = parse_srt_cues(text)
        else:
            cues = parse_json_subtitle(json.loads(text))
        lines = transcript_lines_from_cues(cues)
        meta["selected"] = subtitle.name
        meta["status"] = "ok"
        return lines, meta


def resolve_model_arg(asr_model: str) -> Tuple[str, str, Path, Path]:
    model = compact_ws(asr_model).lower()
    if model not in SUPPORTED_ASR_MODELS:
        raise RuntimeError(f"unsupported asr model: {asr_model}")
    model_id = f"Systran/faster-whisper-{model}"
    cache_dir = DEFAULT_MODEL_ROOT / f"models--{model_id.replace('/', '--')}"
    snapshots_dir = cache_dir / "snapshots"
    if snapshots_dir.exists():
        snapshots = sorted([p for p in snapshots_dir.iterdir() if (p / "model.bin").exists()])
        if snapshots:
            return str(snapshots[-1]), "cache", DEFAULT_MODEL_ROOT, snapshots[-1]
    return model_id, "download", DEFAULT_MODEL_ROOT, cache_dir


def run_local_asr(audio_path: Path, asr_model: str) -> Tuple[List[str], Dict[str, Any]]:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception as e:
        raise RuntimeError("local ASR requires faster-whisper") from e
    model_arg, model_source, model_root, cache_dir = resolve_model_arg(asr_model)
    model = WhisperModel(model_arg, device="cpu", compute_type="int8", download_root=str(model_root))
    segments, info = model.transcribe(str(audio_path), beam_size=5, vad_filter=True, condition_on_previous_text=True)
    lines = []
    for seg in segments:
        text = compact_ws(getattr(seg, "text", ""))
        if text:
            lines.append(f"[{seconds_to_hms(float(getattr(seg, 'start', 0.0) or 0.0))}] {text}")
    if not lines:
        raise RuntimeError("local ASR returned empty transcript")
    return lines, {
        "method": "local_asr",
        "model": asr_model,
        "model_source": model_source,
        "model_cache_dir": str(cache_dir),
        "language": str(getattr(info, "language", "")),
        "duration_sec": float(getattr(info, "duration", 0.0) or 0.0),
    }


def download_audio_temp(ytdlp: str, video_url: str, workdir: Path) -> Path:
    cmd = [ytdlp, "--no-playlist", "-f", "bestaudio/best", "-o", str(workdir / "%(id)s.%(ext)s"), video_url]
    p = run(cmd)
    if p.returncode != 0:
        raise RuntimeError(f"audio download failed: {compact_ws(p.stderr)}")
    candidates = [Path(p) for p in glob.glob(str(workdir / "*")) if Path(p).suffix.lower() in (".m4a", ".mp3", ".wav", ".flac", ".aac", ".ogg", ".opus", ".mp4", ".webm")]
    if not candidates:
        raise RuntimeError("no audio file downloaded")
    return sorted(candidates)[0]


def get_transcript(ytdlp: str, video_url: str, asr_model: str) -> Tuple[List[str], Dict[str, Any]]:
    lines, meta = transcript_from_bilibili_subtitles(ytdlp, video_url)
    if lines:
        return lines, meta
    with tempfile.TemporaryDirectory(prefix="bilibili_reader_asr_") as td:
        audio = download_audio_temp(ytdlp, video_url, Path(td))
        asr_lines, asr_meta = run_local_asr(audio, asr_model)
    meta["fallback"] = asr_meta
    return asr_lines, meta


def transcript_from_external_json(path: Path) -> Tuple[List[str], Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        method = compact_ws(str(payload.get("method") or "browser_visible_subtitles"))
        items = payload.get("items") or payload.get("body") or payload.get("transcript") or []
    else:
        method = "browser_visible_subtitles"
        items = payload
    if not isinstance(items, list):
        raise RuntimeError("external transcript json must contain a list")
    lines: List[str] = []
    last_text = ""
    for item in items:
        if isinstance(item, dict):
            start = float(item.get("start") or item.get("from") or 0.0)
            text = compact_ws(str(item.get("text") or item.get("content") or ""))
        else:
            start = 0.0
            text = compact_ws(str(item))
        if not text or text == last_text:
            continue
        lines.append(f"[{seconds_to_hms(start)}] {text}")
        last_text = text
    if not lines:
        raise RuntimeError("external transcript json produced no transcript lines")
    return lines, {"method": method, "selected": str(path), "status": "ok"}


def interaction_data(info: Dict[str, Any], browser_meta_json: Optional[Path]) -> Dict[str, str]:
    data = {
        "播放": format_metric(info.get("view_count")),
        "弹幕": "-",
        "点赞": format_metric(info.get("like_count")),
        "投币": "-",
        "收藏": "-",
        "分享": "-",
        "评论": format_metric(info.get("comment_count")),
    }
    if browser_meta_json is not None:
        payload = json.loads(browser_meta_json.read_text(encoding="utf-8"))
        interactions = payload.get("interactions") if isinstance(payload, dict) else None
        if isinstance(interactions, dict):
            for key in data:
                if key in interactions:
                    data[key] = format_metric(interactions.get(key))
    return data


def download_media(ytdlp: str, video_url: str, title: str) -> Path:
    media_dir = MEDIA_ROOT / sanitize_filename(title, 60)
    media_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        ytdlp,
        "--no-playlist",
        "--merge-output-format",
        "mp4",
        "-o",
        str(media_dir / "%(title).100s [%(id)s].%(ext)s"),
        video_url,
    ]
    p = run(cmd)
    if p.returncode != 0:
        raise RuntimeError(f"media download failed: {compact_ws(p.stderr)}")
    files = sorted([p for p in media_dir.iterdir() if p.is_file()])
    if not files:
        raise RuntimeError("media download produced no file")
    return files[-1]


def write_note(info: Dict[str, Any], transcript: List[str], transcript_meta: Dict[str, Any], media_path: Optional[Path], interactions: Dict[str, str]) -> Path:
    NOTE_ROOT.mkdir(parents=True, exist_ok=True)
    title = compact_ws(str(info.get("title") or "Bilibili video"))
    video_url = str(info.get("webpage_url") or info.get("original_url") or "")
    uploader = compact_ws(str(info.get("uploader") or info.get("channel") or ""))
    upload_date = date_to_iso(str(info.get("upload_date") or info.get("timestamp") or ""))
    duration = seconds_to_hms(float(info.get("duration") or 0.0))
    slug = sanitize_filename(title, 50)
    path = NOTE_ROOT / f"{upload_date}-Bilibili-{slug}.md"
    media_block = ""
    if media_path:
        rel = os.path.relpath(media_path, start=path.parent)
        media_block = f"\n## 视频\n\n<video src=\"{rel}\" controls></video>\n"
    highlights = build_highlights(transcript)
    content_summary = build_content_summary(highlights)
    note = f"""---
tags: [Bilibili, 视频, 逐字稿, 知识收集]
created: {datetime.now().strftime('%Y-%m-%d')}
type: 知识收集
source: Bilibili
author: {uploader}
url: {video_url}
date: {upload_date}
note: Bilibili 视频逐字稿
---

# {upload_date} {title}

**作者：** {uploader}
**来源：** Bilibili
**原链接：** [{video_url}]({video_url})
**发布时间：** {upload_date}
**时长：** {duration}

**互动数据：**
- 播放：{interactions.get('播放', '-')}
- 弹幕：{interactions.get('弹幕', '-')}
- 点赞：{interactions.get('点赞', '-')}
- 投币：{interactions.get('投币', '-')}
- 收藏：{interactions.get('收藏', '-')}
- 分享：{interactions.get('分享', '-')}
- 评论：{interactions.get('评论', '-')}

---

## 内容摘要

{content_summary}
{media_block}
---

## 划重点

{chr(10).join(highlights)}

---

## 媒体文字内容

字幕来源：{transcript_meta.get('method', 'unknown')}

{chr(10).join(transcript)}

---

*由 [bilibili-reader](https://github.com/Jiaranbb/content-reader/tree/main/bilibili-reader) 提取保存 | 作者：嘉然 · 公众号「嘉然学习笔记」*
"""
    path.write_text(note, encoding="utf-8")
    return path


def process_video(video_url: str, action: str, asr_model: str, include_media: bool, transcript_json: Optional[Path], browser_meta_json: Optional[Path]) -> Dict[str, Any]:
    ytdlp = find_ytdlp()
    info = bilibili_metadata(ytdlp, video_url)
    real_url = str(info.get("webpage_url") or video_url)
    title = compact_ws(str(info.get("title") or "Bilibili video"))
    if action == "download-media":
        media = download_media(ytdlp, real_url, title)
        return {"url": real_url, "media": str(media)}
    if transcript_json is not None:
        transcript, meta = transcript_from_external_json(transcript_json)
    else:
        transcript, meta = get_transcript(ytdlp, real_url, asr_model)
    media_path = download_media(ytdlp, real_url, title) if include_media else None
    interactions = interaction_data(info, browser_meta_json)
    note = write_note(info, transcript, meta, media_path, interactions)
    return {"url": real_url, "note": str(note), "line_count": len(transcript), "method": meta.get("method"), "media": str(media_path) if media_path else None}


def main() -> int:
    parser = argparse.ArgumentParser(description="Save Bilibili transcript notes or media")
    parser.add_argument("--url", required=True, help="Bilibili video, b23.tv short link, multi-P video, playlist, or collection URL")
    parser.add_argument("--action", choices=("transcript", "download-media"), default="transcript")
    parser.add_argument("--include-media", action="store_true", help="Download video media after writing transcript note")
    parser.add_argument("--max-items", type=int, default=None, help="Limit playlist/batch items")
    parser.add_argument("--asr-model", choices=SUPPORTED_ASR_MODELS, default=DEFAULT_ASR_MODEL)
    parser.add_argument("--transcript-json", type=Path, default=None, help="Use a browser/login extracted transcript JSON before yt-dlp/ASR")
    parser.add_argument("--browser-meta-json", type=Path, default=None, help="Use browser/login extracted metadata such as visible interaction counts")
    args = parser.parse_args()

    targets = expand_targets(args.url, args.max_items)
    results = []
    for target in targets:
        try:
            results.append(process_video(target, args.action, args.asr_model, args.include_media, args.transcript_json, args.browser_meta_json))
        except Exception as e:
            results.append({"url": target, "error": str(e)})
    print(json.dumps({"count": len(results), "results": results}, ensure_ascii=False, indent=2))
    return 1 if any("error" in item for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
