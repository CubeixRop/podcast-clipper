"""Find the podcast episodes worth clipping right now, biggest first.

Sources (all free, no keys):
  1. YouTube: today's most-viewed long videos for "<search> full episode".
  2. Your watchlist (~/podcast-clips/podcasts.txt): each show's newest long
     episode on YouTube (youtube:@handle), if it is recent.
"""

import json
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .config import HOME
from .fetch import base_args
from .util import log, run

# YouTube search filter: sort by view count + uploaded today + longer than 20 min.
YT_TODAY_LONG = "CAMSBAgCGAI%253D"


def _flat(url, limit, args=()):
    try:
        raw = run(["yt-dlp", "--flat-playlist", "--playlist-end", str(limit), "-J", *args, url],
                  timeout=120)
        return json.loads(raw).get("entries") or []
    except (RuntimeError, ValueError) as exc:
        log(f"could not read {url[:60]}: {str(exc).splitlines()[0][:80]}", "warn")
        return []


def youtube_today(query, limit=15):
    url = ("https://www.youtube.com/results?search_query="
           f"{urllib.parse.quote_plus(query)}&sp={YT_TODAY_LONG}")
    out = []
    for e in _flat(url, limit, base_args("youtube")):
        if e.get("_type") not in (None, "url") or not e.get("id"):
            continue
        out.append({
            "url": f"https://www.youtube.com/watch?v={e['id']}", "platform": "youtube",
            "name": e.get("channel") or "?", "title": e.get("title") or "",
            "views": e.get("view_count") or 0, "duration": e.get("duration") or 0,
            "live": e.get("live_status") == "is_live", "source": "youtube search",
        })
    return out


def watchlist_file():
    path = HOME / "podcasts.txt"
    if not path.exists():
        HOME.mkdir(parents=True, exist_ok=True)
        default = Path(__file__).resolve().parent.parent.parent / "podcasts.txt"
        path.write_text(default.read_text() if default.exists() else "")
    return path


def _watch_entries():
    out = []
    for line in watchlist_file().read_text().splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        platform, _, handle = line.partition(":")
        if platform == "youtube" and handle:
            out.append((platform, handle.strip()))
    return out


def _latest(platform, handle, cfg):
    """Newest long episode of one show, if it's recent."""
    if platform != "youtube":
        return None
    listing = f"https://www.youtube.com/{handle if handle.startswith('@') else '@' + handle}/videos"
    args = base_args(listing)
    words = [w.lower() for w in cfg["title_words"]]
    for e in _flat(listing, 3, args):
        title = e.get("title") or ""
        if words and not any(w in title.lower() for w in words):
            continue
        url = e.get("url") or e.get("webpage_url")
        if url and not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={e.get('id')}"
        try:
            full = json.loads(run(["yt-dlp", "-J", "--no-playlist", *args, url], timeout=120))
        except (RuntimeError, ValueError):
            continue
        if (full.get("duration") or 0) < cfg["min_episode_minutes"] * 60:
            continue                      # a clip or a short, not a full episode
        ts = full.get("timestamp") or full.get("release_timestamp") or 0
        if ts and time.time() - ts > cfg["max_age_hours"] * 3600:
            return None
        return {
            "url": url, "platform": platform, "name": full.get("channel") or full.get("uploader") or handle,
            "title": title, "views": full.get("view_count") or 0, "duration": full.get("duration") or 0,
            "live": full.get("live_status") == "is_live", "source": "watchlist",
        }
    return None


def watchlist(cfg):
    entries = _watch_entries()
    if not entries:
        return []
    log(f"checking {len(entries)} show(s) on your watchlist...", "step")
    with ThreadPoolExecutor(max_workers=6) as pool:
        got = list(pool.map(lambda e: _latest(e[0], e[1], cfg), entries))
    return [g for g in got if g]


def find(cfg, limit=5):
    """Biggest episodes first, one per show."""
    found = watchlist(cfg) + youtube_today(cfg["search"] + " full episode")
    words = [w.lower() for w in cfg["title_words"]]
    best = {}
    for s in found:
        if words and not any(w in s["title"].lower() for w in words):
            continue
        if s["duration"] and s["duration"] < cfg["min_episode_minutes"] * 60:
            continue
        key = s["name"].lower()
        if key not in best or s["views"] > best[key]["views"]:
            best[key] = s
    ranked = sorted(best.values(), key=lambda s: -s["views"])
    return ranked[:limit]
