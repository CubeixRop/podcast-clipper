"""Settings. Defaults below; override any of them in ~/podcast-clips/config.json."""

import json
import platform
from pathlib import Path

HOME = Path.home() / "podcast-clips"

_WINDOWS = platform.system() == "Windows"


def _default_hook_font():
    if _WINDOWS:
        # Windows ships Arial Bold under this name; Impact is a heavier, more
        # TikTok-ish alternative if the user has it.
        return r"C:\Windows\Fonts\arialbd.ttf"
    return "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def _default_emoji_font():
    if _WINDOWS:
        return r"C:\Windows\Fonts\seguiemj.ttf"   # Segoe UI Emoji
    return "/System/Library/Fonts/Apple Color Emoji.ttc"


def _default_emoji_strike():
    # Apple Color Emoji only renders at a fixed 160px bitmap strike, so hook.py
    # renders at that size and scales down. Segoe UI Emoji (Windows) is a scalable
    # colour font and can be rendered directly at the size needed, so this is None.
    return 160 if not _WINDOWS else None


def _default_encoder():
    # A safe cross-platform default; run.py --fast probes for real hardware
    # encoders (h264_videotoolbox / h264_nvenc / h264_qsv / h264_amf) at startup
    # and overrides this when one is found and working.
    return "libx264"


DEFAULTS = {
    # --- finding streams ---
    "search": "comedy podcast",      # YouTube search words (adds " full episode")
    "title_words": [],               # optional: a video must have one of these in its title
    "max_age_hours": 96,             # ignore watchlist episodes older than this
    "min_episode_minutes": 20,       # shorter videos are clips already, not episodes

    # --- download ---
    "max_height": 1080,

    # --- listening to the episode ---
    "scan_model": "tiny",            # fast pass over the whole stream (what Claude reads)
    "caption_model": "base",         # careful pass over each chosen clip (the captions)
    "language": None,                # None = detect, or "en"
    "scan_block_minutes": 20,        # audio is decoded in blocks, so 10-hour streams fit in memory
    "loud_db": 6.0,                  # louder than the last 2 minutes by this much = a spike
    "chat": True,                    # YouTube replays: count chat messages per 5 s
    "chat_timeout": 420,

    # --- picking moments ---
    # NOTE: picking is no longer done by a `claude -p` subprocess (that only exists
    # inside Claude Code). In Claude chat, the assistant itself reads the transcript
    # chunks this tool writes to <workdir>/chunks/ and writes back the JSON picks —
    # see SKILL.md section 2 and clipper/moments.py.
    "clips_per_stream": 3,
    "min_duration": 20,
    "max_duration": 75,
    "chunk_minutes": 12,             # transcript window per picking pass
    "claude_model": None,            # unused outside Claude Code; kept for config compatibility

    # --- framing (podcasts: "fit" keeps everyone in frame; "auto"/"stream" assume a facecam over gameplay) ---
    "layout": "fit",                 # fit (default, safe for 2-shots) | face | auto | stream
    "output_width": 1080,
    "output_height": 1920,
    "cam_height": 760,               # stream layout: height of the facecam panel on top
    "fit_aspect": 1.7778,            # fit layout: 1.7778 keeps the whole 16:9 frame (cams sit on edges)
    "track_smoothing": 5,

    # --- hook (the title bar) ---
    "hook_font_file": _default_hook_font(),
    "hook_font_size": 54,
    "hook_y": 0.09,
    "hook_margin_x": 150,
    "emoji_font_file": _default_emoji_font(),
    "emoji_font_strike": _default_emoji_strike(),   # fixed bitmap size to render+scale, or None to render directly

    # --- captions ---
    "font": "Arial Black" if not _WINDOWS else "Arial",   # "Arial Black" isn't bundled on most Windows installs
    "font_size": 82,
    "words_per_group": 4,
    "uppercase": True,
    "text_color": "FFFFFF",
    "highlight_color": "FFE13B",
    "outline_width": 6,
    "caption_y": 0.72,
    "word_pop": True,

    # --- encoding ---
    "encoder": _default_encoder(),   # libx264 by default; --fast probes for real hardware encoders
    "crf": 20,
    "preset": "medium",
    "audio_bitrate": "192k",
    "loudnorm": True,
}


def load(overrides=None):
    cfg = dict(DEFAULTS)
    path = HOME / "config.json"
    if path.exists():
        try:
            cfg.update(json.loads(path.read_text()))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path} is not valid JSON: {exc}")
    for key, value in (overrides or {}).items():
        if value is not None:
            cfg[key] = value
    return cfg
