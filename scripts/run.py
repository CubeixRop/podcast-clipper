#!/usr/bin/env python3
"""podclip: comedy podcast episodes in, ready-to-post vertical clips out.

  podclip URL [URL ...]        clip these streams (several run at the same time)
  podclip --find                find today's biggest comedy podcast episodes and clip them
  podclip --find --list         only show what it would clip

Clips land in ~/podcast-clips/<date>/<show>__<episode title>/ with a POST.md
(caption + hashtags per clip). Re-running the same command resumes; nothing is redone.

Picking the moments happens in two passes (see clipper/moments.py and SKILL.md):
the first run on a new episode stops after writing transcript chunks to
~/podcast-clips/work/<key>/chunks/ and tells you what is pending; once those
chunks have a .result.json written next to them, running the exact same command
again continues straight to rendering.
"""

import argparse
import datetime
import json
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from clipper import config, fetch, find, moments, render, scan  # noqa: E402
from clipper.util import (  # noqa: E402
    Timer, die, hhmmss, log, minutes, pick_hw_encoder, probe, require, set_tag, slugify,
)


def parse(argv):
    p = argparse.ArgumentParser(prog="podclip", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("urls", nargs="*", help="episode links (YouTube)")
    p.add_argument("--find", action="store_true", help="find today's biggest comedy podcast episodes")
    p.add_argument("--list", action="store_true", help="with --find: only list them")
    p.add_argument("--streams", type=int, default=5, help="with --find: how many episodes (default 5)")
    p.add_argument("--clips", type=int, help="clips per episode (default 3)")
    p.add_argument("--parallel", type=int, default=2, help="episodes processed at once (default 2)")
    p.add_argument("--section", metavar="RANGE",
                   help='only part of the stream, e.g. "1:00:00-3:30:00" (long streams, re-runs)')
    p.add_argument("--cookies", choices=["chrome", "safari", "firefox", "brave", "edge", "chromium"],
                   help="use your browser login (age-restricted or members-only videos)")
    p.add_argument("--layout", choices=["auto", "stream", "face", "fit"])
    p.add_argument("--min", dest="min_duration", type=int, help="shortest clip in seconds")
    p.add_argument("--max", dest="max_duration", type=int, help="longest clip in seconds")
    p.add_argument("--fast", action="store_true",
                   help="use a hardware encoder if ffmpeg reports one that works "
                        "(VideoToolbox on Mac, NVENC/QSV/AMF on Windows, VAAPI on Linux)")
    p.add_argument("--keep-audio", action="store_true", help="keep the stream audio after clipping")
    p.add_argument("--redo", action="store_true", help="pick the moments again (keeps the audio)")
    return p.parse_args(argv)


def seconds(stamp):
    total = 0.0
    for part in stamp.strip().split(":"):
        total = total * 60 + float(part)
    return total


def one_stream(url, cfg, opts):
    """Everything for one stream. Returns a summary dict (or raises)."""
    timer = Timer()
    args = fetch.base_args(url, opts.cookies)
    key = re.sub(r"[^A-Za-z0-9_-]", "_", url.split("://")[-1])[-80:]
    work = config.HOME / "work" / key          # the episode's audio, loudness, chat
    work.mkdir(parents=True, exist_ok=True)

    with timer.stage("look up"):
        info = fetch.info(url, args, work)
    set_tag(info["name"][:18])
    if info.get("live_status") == "is_live":
        log("this is still live: clipping what has aired so far", "warn")

    with timer.stage("download audio"):
        audio = fetch.audio(url, args, work)
    length = probe(audio)["duration"]
    lo, hi = 0.0, length
    if opts.section:
        a, _, b = opts.section.lstrip("*").partition("-")
        lo, hi = seconds(a), min(seconds(b), length) if b else length
    pick_dir = work if not opts.section else work / f"part_{int(lo)}_{int(hi)}"
    pick_dir.mkdir(exist_ok=True)
    if opts.redo:
        for f in ("moments.json", "candidates.json"):
            (pick_dir / f).unlink(missing_ok=True)
        shutil.rmtree(pick_dir / "chunks", ignore_errors=True)
    log(f"{info['title'][:70]}  ·  {minutes(length)} of episode"
        + (f", clipping {hhmmss(lo)}-{hhmmss(hi)}" if opts.section else ""), "ok")

    with timer.stage("listen"):
        heard = scan.transcript(audio, lo, hi, pick_dir, cfg)
        loud = scan.relative(scan.loudness(audio, work))
        chat = scan.chat_rate(url, args, work, cfg, info)
    stream = {"name": info["name"], "title": info["title"], "url": url}
    with timer.stage("pick"):
        picked = moments.find(heard, loud, chat, pick_dir, cfg, stream)

    day = datetime.date.today().isoformat()
    outdir = config.HOME / day / f"{slugify(info['name'], 24)}__{slugify(info['title'], 40)}"
    outdir.mkdir(parents=True, exist_ok=True)
    made, ready, known = [], [], {}
    with timer.stage("make clips"):
        for i, m in enumerate(picked, 1):
            try:
                ready.append(render.prepare(url, args, audio, m, i, pick_dir, cfg,
                                            heard.get("language")))
            except Exception as exc:
                log(f"[clip {i}] failed: {str(exc)[:300]}", "err")
        for p in ready:              # learn where this stream's facecam sits from every clip
            render.learn(p, cfg, known)
        for p in ready:
            try:
                made.append(render.finish(p, outdir, pick_dir, cfg, known))
            except Exception as exc:
                log(f"[clip {p['index']}] failed: {str(exc)[:300]}", "err")

    summary = (f"{minutes(hi - lo)} of episode -> {len(made)} clip(s) in {minutes(timer.total())} "
               f"(" + ", ".join(f"{k} {minutes(v)}" for k, v in timer.stages.items()) + ")")
    render.post_sheet(outdir, stream, made, summary)
    (outdir / "report.json").write_text(json.dumps({
        "stream": stream, "stream_seconds": round(hi - lo), "clips": len(made),
        "total_seconds": round(timer.total()),
        "stages_seconds": {k: round(v) for k, v in timer.stages.items()},
        "scan_model": cfg["scan_model"]}, indent=2))
    if not opts.keep_audio and made:
        audio.unlink(missing_ok=True)
    log(summary, "ok")
    set_tag("")
    return {"name": info["name"], "title": info["title"], "outdir": outdir, "clips": made,
            "summary": summary}


def main(argv=None):
    opts = parse(argv if argv is not None else sys.argv[1:])
    for tool, hint in (("yt-dlp", "run scripts/setup.sh (Mac/Linux) or scripts/setup.ps1 (Windows)"),
                       ("ffmpeg", "install ffmpeg and put it on PATH")):
        require(tool, hint)
    encoder = None
    if opts.fast:
        encoder = pick_hw_encoder()
        if encoder:
            log(f"using hardware encoder: {encoder}", "ok")
        else:
            log("no working hardware encoder found (checked VideoToolbox/NVENC/QSV/AMF/VAAPI); "
                "staying on libx264", "warn")
    cfg = config.load({
        "clips_per_stream": opts.clips, "layout": opts.layout,
        "min_duration": opts.min_duration, "max_duration": opts.max_duration,
        "encoder": encoder,
    })
    config.HOME.mkdir(parents=True, exist_ok=True)
    free_gb = shutil.disk_usage(config.HOME).free / 1e9
    if free_gb < 2:
        log(f"only {free_gb:.1f} GB free on this disk; long streams need ~0.1 GB per hour", "warn")

    urls = list(opts.urls)
    if opts.find:
        log("finding today's biggest comedy podcast episodes...", "step")
        found = find.find(cfg, limit=opts.streams)
        if not found:
            die("no episodes found right now. Add shows to ~/podcast-clips/podcasts.txt "
                "or paste episode links.")
        print()
        for i, s in enumerate(found, 1):
            live = "LIVE " if s["live"] else ""
            print(f"  {i}. {s['name'][:22]:22} {s['views']:>10,} {live}· {s['title'][:60]}  ({s['source']})")
            print(f"     {s['url']}")
        print()
        if opts.list:
            return
        urls += [s["url"] for s in found]
    if not urls:
        die("give me episode links, or use --find")

    results, needs_picking = [], []
    with ThreadPoolExecutor(max_workers=max(1, opts.parallel)) as pool:
        futures = {pool.submit(one_stream, u, cfg, opts): u for u in urls}
        for fut, url in futures.items():
            try:
                results.append(fut.result())
            except moments.NeedsPicking as exc:
                needs_picking.append((url, exc))
            except Exception as exc:
                msg = str(exc)
                if "confirm your age" in msg or "Sign in to confirm" in msg:
                    msg = ("YouTube wants a login for this one (age-restricted or members-only). "
                           "Run it again with --cookies chrome (or the browser you're signed into).")
                log(f"{url}: {msg[:400]}", "err")

    if needs_picking:
        print()
        log(f"{len(needs_picking)} episode(s) are waiting for moments to be picked:", "step")
        for url, exc in needs_picking:
            print(f"\n  {url}\n  chunks: {exc.chunks_dir}")
            for p in exc.pending:
                print(f"    - {p.name}")
        print("\n  Read each chunk_NN.txt above and write chunk_NN.result.json next to it "
              "(a JSON array of picks, per the schema inside the prompt), then run this exact "
              "command again to continue straight to rendering.\n")

    print()
    total = sum(len(r["clips"]) for r in results)
    log(f"done: {total} clip(s) from {len(results)} stream(s)", "ok")
    for r in results:
        print(f"\n  {r['name']} · {r['title'][:60]}\n  {r['summary']}\n  {r['outdir']}")
        for c in r["clips"]:
            print(f"    [{c['score']}] {c['duration']:>3.0f}s @{hhmmss(c['stream_start'])}  {c['hook_text']}")
    print()


if __name__ == "__main__":
    main()
