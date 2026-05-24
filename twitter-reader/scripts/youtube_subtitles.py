#!/usr/bin/env python3
"""Download and clean YouTube subtitles for twitter-reader."""

from __future__ import annotations

import argparse
import glob
import html
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

LANG_PRIORITY = ["zh-Hans", "zh-CN", "zh-Hant", "zh", "en-orig", "en"]


def compact_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def find_ytdlp() -> str:
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        raise RuntimeError("yt-dlp not found")
    return ytdlp


def append_with_spacing(base: str, piece: str) -> str:
    if not base:
        return piece
    if not piece:
        return base
    if re.match(r"^[,.;:!?，。！？；：、)\\]\"'”’]", piece):
        return base + piece
    if base[-1].isalnum() and piece[0].isalnum():
        return base + " " + piece
    return base + piece


def choose_vtt(workdir: Path) -> Optional[Path]:
    candidates = [Path(p) for p in glob.glob(str(workdir / "*.vtt"))]
    if not candidates:
        return None
    for lang in LANG_PRIORITY:
        for candidate in candidates:
            if candidate.name.endswith(f".{lang}.vtt"):
                return candidate
    return sorted(candidates)[0]


def parse_vtt_cues(vtt_text: str) -> List[str]:
    cues: List[str] = []
    buf: List[str] = []
    in_cue = False

    def flush() -> None:
        nonlocal buf
        if not buf:
            return
        text = " ".join(buf)
        text = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", "", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        text = re.sub(r"\[(?:music|Music|applause|Applause)\]", " ", text)
        text = text.replace("\u200b", " ")
        text = compact_ws(text)
        if text:
            cues.append(text)
        buf = []

    for raw in vtt_text.splitlines():
        line = raw.strip("\ufeff").rstrip()
        stripped = line.strip()
        if not stripped:
            flush()
            in_cue = False
            continue
        if stripped.startswith(("WEBVTT", "NOTE", "Kind:", "Language:")):
            continue
        if "-->" in stripped:
            flush()
            in_cue = True
            continue
        if re.fullmatch(r"\d+", stripped):
            continue
        if in_cue or stripped:
            buf.append(stripped)

    flush()
    return cues


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
            if len(seg) > 260:
                out.extend(hard_wrap(seg, 220))
            else:
                out.append(seg)
    deduped: List[str] = []
    for line in out:
        if deduped and deduped[-1] == line:
            continue
        deduped.append(line)
    return deduped


def download_vtt(url: str, workdir: Path) -> Tuple[Path, List[Dict[str, Any]]]:
    ytdlp = find_ytdlp()
    attempts: List[Dict[str, Any]] = []
    lang_sets = [
        "zh-Hans,zh-CN,zh-Hant,zh,en-orig,en",
        "en-orig,en",
    ]

    for langs in lang_sets:
        cmd = [
            ytdlp,
            "--skip-download",
            "--write-auto-subs",
            "--write-subs",
            "--extractor-args",
            "youtube:player_client=android",
            "--sub-langs",
            langs,
            "--sub-format",
            "vtt",
            "-o",
            str(workdir / "%(id)s.%(ext)s"),
            url,
        ]
        p = run(cmd)
        attempts.append(
            {
                "langs": langs,
                "returncode": p.returncode,
                "stderr": compact_ws(p.stderr)[-800:],
            }
        )
        vtt = choose_vtt(workdir)
        if vtt is not None:
            return vtt, attempts

    raise RuntimeError("no YouTube subtitle file downloaded")


def clean_vtt_file(path: Path) -> List[str]:
    cues = parse_vtt_cues(path.read_text(encoding="utf-8", errors="ignore"))
    merged = merge_cues_with_overlap(cues)
    lines = split_lines(merged)
    if not lines:
        raise RuntimeError("subtitle cleaned to empty text")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and clean YouTube subtitles for twitter-reader")
    parser.add_argument("--url", required=True, help="YouTube URL")
    parser.add_argument("--out-dir", default="/tmp/twitter-youtube-subs", help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="twitter_youtube_subs_") as td:
        workdir = Path(td)
        vtt, attempts = download_vtt(args.url, workdir)
        lines = clean_vtt_file(vtt)

    txt_path = out_dir / "youtube_transcript.txt"
    meta_path = out_dir / "youtube_transcript.meta.json"
    txt_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    meta = {
        "source": args.url,
        "selected_vtt": vtt.name,
        "line_count": len(lines),
        "attempts": attempts,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"OK\t{txt_path}")
    print(f"META\t{meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
