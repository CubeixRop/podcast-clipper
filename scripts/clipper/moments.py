"""Pick the moments worth clipping.

In Claude Code this used to shell out to `claude -p`. In Claude chat there is no such
CLI, so instead:

  1. prepare_chunks() writes each ~12-minute window of the transcript to its own
     <workdir>/chunks/chunk_NN.txt — a self-contained prompt with the same picking
     criteria as before (see the PROMPT text below, and SKILL.md section 2).
  2. Claude (the assistant, in this conversation) reads each chunk_NN.txt and writes
     back chunk_NN.result.json with a JSON array of picks, in the exact schema the
     prompt asks for. No subprocess, no API call: Claude just reasons over the text,
     the same way it would answer any other question, and writes the file via its
     file tools (Desktop Commander on the user's machine).
  3. find() (called again, e.g. by re-running podclip) notices every chunk has a
     .result.json, snaps the picks onto real word boundaries, de-duplicates and
     caches the result as moments.json, same as the rest of this project's caching.

If any chunk is still missing its .result.json, find() raises NeedsPicking so the
caller can tell Claude exactly what is left to do instead of failing outright.
"""

import json
import re

import numpy as np

from .util import log

PROMPT = """You clip comedy podcasts for TikTok, Reels and YouTube Shorts and you are paid per \
view. This is part of an episode of {streamer}, titled "{title}".

Below is a timestamped transcript (seconds) with NO speaker labels, so work out who is \
talking from context (host, guest, someone off-camera, a stranger on a call). Markers on a line:
- [LOUD +NdB] the audio jumped N dB above the last two minutes. On a comedy podcast this is \
usually LAUGHTER or a shout: the line just before it is often the punchline.
- [CHAT xN] (live replays only) chat was moving N times faster than usual.
Markers are strong hints, not proof.

Find the {want} STRONGEST standalone clips in this excerpt.

What went viral in a study of 100 comedy-podcast clips (176M views total). Score highly \
when a clip has MOST of these:
1. LIVE MOMENT, NO SETUP: it drops into the middle of a real exchange and needs zero \
context. The best clips open on a question, an answer, or a reaction, not on an intro.
2. A REAL PERSON IS PUT ON THE SPOT: someone other than the comedian answers, reacts or \
gets asked something (a kid, a parent on the phone, a stranger, a guest, a friend). Their \
answer or reaction is the joke; the comedian mostly steers.
3. ONE CLEAR BEAT: a question and a punchy reply, a single sincere line, or one bit with \
one payoff. Not a story with chapters.
4. INSTANTLY UNDERSTOOD TOPIC: family and kids, race, sports, everyday absurdity, a big \
conspiracy or hot take anyone has an opinion on.

Kinds: live_moment (a real exchange with a non-host), bit (one self-contained joke or \
riff), hot_take (a strong opinion that starts an argument), reaction (shock, losing it, \
speechless), story (a SHORT anecdote that pays off in under a minute).

Rejection list (these did worst in the study): dark news commentary (murders, tragedies), \
the comedian's own career or audition anecdote, long context before the joke, chaotic \
crosstalk with nothing landing, intros and outros, ad reads and sponsor reads, anything \
whose payoff is outside this excerpt. Length by itself did not matter, so do not pad or \
trim to hit a number.

Rules:
- start and end are seconds inside {lo:.0f}-{hi:.0f}, {min_d}-{max_d} s long, no overlaps.
- Start ~1 s before the hook so it does not feel cut off; end right after the payoff.
- Fewer than {want} is fine if fewer are genuinely strong.

Write the result as a JSON array, and ONLY a JSON array (no prose, no code fence), to the
file named at the end of this prompt:
[{{"start": 1312.5, "end": 1349.0, "kind": "live_moment",
  "title": "short internal name",
  "hook_text": "She asks a 7 year old what he does for FUN 😭",
  "caption": "a post caption that drives comments, under 150 chars",
  "hashtags": ["#comedy", "#podcast", "#theovon"],
  "score": 88,
  "reason": "one sentence on why this will hold attention"}}]

score is 1-100 predicted retention; be harsh, 85+ only for clips you would bet on. A clip \
that fails the rejection list scores under 50.
hook_text is the title bar on top of the video and decides if people stop scrolling: \
4-12 words, casual, name the guest or show when that helps, CAPITALISE the 2-3 words \
carrying the drama, tease the payoff instead of stating it, a 😭 or 💀 only when it is \
funny. No "INSANE MOMENT YOU WON'T BELIEVE" clickbait without specifics.

Write your JSON array to: {result_path}

TRANSCRIPT:
{transcript}
"""


def _lines(words, loud, chat, cfg, line_seconds=8):
    """~8 s lines with [LOUD]/[CHAT] markers. Cheap in tokens, easy to read."""
    lines, cur, start = [], [], None
    chat_base = float(np.median([c for c in chat if c > 0])) if chat and any(chat) else 0

    def flush(t0, t1, text):
        tags = []
        if len(loud):
            a, b = int(t0), max(int(t0) + 1, int(np.ceil(t1)))
            peak = float(np.max(loud[a:b])) if a < len(loud) else 0
            if peak >= cfg["loud_db"]:
                tags.append(f"[LOUD +{peak:.0f}dB]")
        if chat_base:
            a, b = int(t0 // 5), int(t1 // 5) + 2      # chat lags the moment a little
            seg = chat[a:b]
            if seg:
                ratio = max(seg) / chat_base
                if ratio >= 2.5:
                    tags.append(f"[CHAT x{ratio:.0f}]")
        lines.append((t0, (" ".join(tags) + " " if tags else "") + text))

    for w in words:
        if start is None:
            start = w["s"]
        cur.append(w["w"])
        if w["e"] - start >= line_seconds:
            flush(start, w["e"], " ".join(cur))
            cur, start = [], None
    if cur:
        flush(start, words[-1]["e"], " ".join(cur))
    return lines


def _parse(raw):
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    if not text.startswith("["):
        m = re.search(r"\[\s*\{.*\}\s*\]", text, re.S)
        if not m:
            return []
        text = m.group(0)
    try:
        out = json.loads(text)
    except json.JSONDecodeError:
        return []
    return out if isinstance(out, list) else []


def _snap(m, words, cfg):
    """Move the rough times onto real word edges; enforce the length limits."""
    start, end = float(m["start"]), float(m["end"])
    near = [w for w in words if w["s"] >= start - 1.5]
    if not near:
        return None
    first = min(near, key=lambda w: abs(w["s"] - start))
    inside = [w for w in words if first["s"] <= w["s"] and w["e"] <= end + 1.5]
    if not inside:
        return None
    last = min(inside, key=lambda w: abs(w["e"] - end))
    lo, hi = cfg["min_duration"], cfg["max_duration"]
    if last["e"] - first["s"] > hi:
        fit = [w for w in inside if w["e"] - first["s"] <= hi]
        if not fit:
            return None
        ends = [w for w in fit if w["w"].rstrip().endswith((".", "!", "?"))]
        last = ends[-1] if ends else fit[-1]
    if last["e"] - first["s"] < lo:
        after = [w for w in words if w["e"] > last["e"] and w["e"] - first["s"] <= hi]
        reach = [w for w in after if w["e"] - first["s"] >= lo]
        if reach:
            last = reach[0]
        elif after:
            last = after[-1]
        if last["e"] - first["s"] < lo:
            return None
    m["start"] = round(max(0.0, first["s"] - 0.6), 2)
    m["end"] = round(min(last["e"] + 0.6, m["start"] + hi), 2)
    return m


def _dedupe(cands):
    kept = []
    for m in sorted(cands, key=lambda m: -float(m.get("score", 0))):
        span = m["end"] - m["start"]
        if all(min(m["end"], k["end"]) - max(m["start"], k["start"])
               <= 0.3 * min(span, k["end"] - k["start"]) for k in kept):
            kept.append(m)
    return kept


class NeedsPicking(RuntimeError):
    """Raised when one or more transcript chunks are waiting to be picked.

    `chunks_dir` holds chunk_NN.txt (the prompt to read) for every chunk, and this
    is raised whenever any of them is still missing its chunk_NN.result.json.
    `pending` lists the .txt files still needing a .result.json written next to them.
    """

    def __init__(self, chunks_dir, pending):
        self.chunks_dir = chunks_dir
        self.pending = pending
        names = "\n".join(f"  - {p.name}" for p in pending)
        super().__init__(
            f"{len(pending)} transcript chunk(s) still need picking in {chunks_dir}:\n{names}\n"
            "Read each chunk_NN.txt and write chunk_NN.result.json next to it (a JSON array "
            "of picks, per the schema inside the prompt), then run this exact command again."
        )


def prepare_chunks(scan, loud_rel, chat, workdir, cfg, stream):
    """Write (or resume) the transcript chunks Claude picks moments from.
    Returns the list of chunk_NN.txt paths still missing a chunk_NN.result.json."""
    chunks_dir = workdir / "chunks"
    chunks_dir.mkdir(exist_ok=True)

    words = scan["words"]
    lines = _lines(words, loud_rel, chat or [], cfg)
    first, total = words[0]["s"], words[-1]["e"]
    window = cfg["chunk_minutes"] * 60
    raw_chunks = []
    for i in range(int(np.ceil((total - first) / window))):
        lo, hi = first + i * window, min(first + (i + 1) * window, total)
        body = [f"[{t:.1f}] {text}" for t, text in lines if lo <= t < hi]
        if sum(len(b.split()) for b in body) >= 30:
            raw_chunks.append((lo, hi, "\n".join(body)))
    if not raw_chunks:
        raise RuntimeError("not enough talking in this episode to clip")

    want = max(2, min(5, round(cfg["clips_per_stream"] / len(raw_chunks)) + 2))

    manifest_path = chunks_dir / "manifest.json"
    manifest = {"chunks": []}
    pending = []
    for i, (lo, hi, body) in enumerate(raw_chunks):
        prompt_path = chunks_dir / f"chunk_{i:02d}.txt"
        result_path = chunks_dir / f"chunk_{i:02d}.result.json"
        manifest["chunks"].append({"index": i, "lo": lo, "hi": hi})
        if not prompt_path.exists():
            prompt_path.write_text(PROMPT.format(
                streamer=stream["name"], title=stream["title"], want=want, lo=lo, hi=hi,
                min_d=cfg["min_duration"], max_d=cfg["max_duration"],
                result_path=result_path, transcript=body), encoding="utf-8")
        if not result_path.exists():
            pending.append(prompt_path)
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return pending


def find(scan, loud_rel, chat, workdir, cfg, stream):
    cache = workdir / "moments.json"
    if cache.exists():
        found = json.loads(cache.read_text())
        log(f"reusing {len(found)} picked moment(s)", "ok")
        return found

    pending = prepare_chunks(scan, loud_rel, chat, workdir, cfg, stream)
    chunks_dir = workdir / "chunks"
    if pending:
        raise NeedsPicking(chunks_dir, pending)

    words = scan["words"]
    manifest = json.loads((chunks_dir / "manifest.json").read_text())
    cands = []
    for entry in manifest["chunks"]:
        result_path = chunks_dir / f"chunk_{entry['index']:02d}.result.json"
        got = _parse(result_path.read_text())
        lo, hi = entry["lo"], entry["hi"]
        for m in got:
            try:
                if lo - 5 <= float(m["start"]) < hi + 30:
                    s = _snap(m, words, cfg)
                    if s:
                        cands.append(s)
            except (KeyError, TypeError, ValueError):
                continue
    if not cands:
        raise RuntimeError(
            "no usable moments came back from the picked chunks in "
            f"{chunks_dir} — check that the .result.json files are valid JSON arrays")

    chosen = _dedupe(cands)[: cfg["clips_per_stream"]]
    log(f"picked {len(chosen)} of {len(cands)} candidate moments", "ok")
    cache.write_text(json.dumps(chosen, indent=2))
    (workdir / "candidates.json").write_text(json.dumps(cands, indent=2))
    return chosen
