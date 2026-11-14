---
name: podcast-clipper
description: Comedy podcast clipper. Finds the biggest recent comedy podcast episodes on YouTube (or takes links), listens to the whole episode on the user's own computer, has Claude pick the moments most likely to go viral (live moments with a real person on the spot, one-beat bits, hot takes, reactions, short stories) using the transcript plus where the room got loud (laughter), then makes ready-to-post 9:16 clips with a hook title bar and word-by-word captions, plus a POST.md with a caption and hashtags per clip. Runs through the Desktop Commander connector so it works on the user's Windows (or Mac/Linux) machine from Claude chat — no Claude Code and no API keys needed. Use whenever someone wants to clip podcasts, make Shorts/TikToks/Reels from a podcast episode, run podcast clipping campaigns, or says "clip this episode", "find the best moments", or "make clips from" a named show.
---

# Podcast Clipper

Episodes in, ready-to-post vertical clips out. **You (Claude) drive the whole thing from
chat; the user only gives links (or nothing: `--find`).** This runs on the user's own
computer — not in your sandboxed container — through the **Desktop Commander** MCP
connector, so it needs that connector connected. If it isn't, tell the user to connect it
(or run this from Claude Code / Cowork instead, where you have direct process/file tools).

`SKILL` = the folder this file is in. Everything it makes lands in
`~/podcast-clips/<date>/<show>__<episode title>/` on the user's machine.

Adapted from a GTA 6 stream clipper, then adapted again to run without Claude Code: the
original version shelled out to `claude -p` to pick moments; this version has **you** read
the transcript and pick them directly, since you're already the model in the loop.

## 0. Tools you'll use

Load Desktop Commander's process and file tools with `tool_search` if they aren't already
available: `start_process`, `interact_with_process`, `read_process_output`,
`list_processes`, `force_terminate`, `read_file`, `read_multiple_files`, `write_file`,
`create_directory`, `list_directory`, `get_file_info`, `move_file`. Everything below runs
**on the user's machine** through these, not through your own bash tool.

Detect the OS once (e.g. `start_process` with `cmd.exe /c ver` or check for `C:\Windows`
vs `/System`) and use the matching script pair for the rest of the session:
- **Windows**: `scripts\setup.ps1` / `scripts\podclip.ps1`, run via `powershell -File ...`
- **Mac/Linux**: `scripts/setup.sh` / `scripts/podclip` via `bash ...`

## 1. First use on a machine

Run the setup script for the detected OS until it prints **All set**:
- Windows: `powershell -File SKILL\scripts\setup.ps1`
- Mac/Linux: `bash SKILL/scripts/setup.sh`

It checks ffmpeg, Python, a JS runtime (deno/node/bun — YouTube needs one), disk space;
builds a private Python env (`~/.podcast-clipper/venv`), downloads Whisper tiny + base and
the facecam finder, and seeds `~/podcast-clips/podcasts.txt`. Install anything missing the
free, official way (`winget install Gyan.FFmpeg`, `winget install DenoLand.Deno` on
Windows; `brew install ffmpeg deno` on Mac). Ask before anything needing a password.

Windows fonts: the hook title bar uses Arial Bold (`arialbd.ttf`) and Segoe UI Emoji
(`seguiemj.ttf`), both ship with Windows. If a user has removed them, point `hook_font_file`
/ `emoji_font_file` in `~/podcast-clips/config.json` at fonts they do have.

## 2. What happens to each episode

1. **Audio only** of the whole episode is downloaded (video is NOT downloaded yet).
2. **Listen**: fast local transcript (Whisper tiny) + loudness per second. On a comedy
   podcast a loudness spike is usually **laughter** or shouting, so the line just before it
   is often the punchline. Chat speed is used only for live replays.
3. **Pick** (this is the part that changed — read carefully):
   - The script splits the transcript into ~12-minute chunks and writes each one to
     `~/podcast-clips/work/<key>/chunks/chunk_NN.txt` as a **complete, self-contained
     prompt** — the same picking criteria as below, with that chunk's transcript baked in,
     and the exact path it wants its answer written to at the bottom.
   - It then stops and tells you (in its printed output) which `chunk_NN.txt` files are
     still waiting. **Read each one with `read_file`, pick the moments yourself** — you are
     already the model doing the reading, there's no subprocess to call — and
     **`write_file` your answer as a JSON array** to the `chunk_NN.result.json` path the
     prompt names, in the exact schema the prompt asks for. Nothing else needs to run in
     between; this is just you reasoning over text and writing a file.
   - Run the **exact same command again** once every chunk for an episode has its
     `.result.json`. It snaps your picks onto real word boundaries, de-duplicates, caches
     the result as `moments.json`, and continues straight into rendering.
   - What the picking criteria reward (a hypothesis from a 100-clip study, 176M views
     total, see section 2b below): a live moment needing no setup, a real person put on the
     spot, one clear beat, an instantly understood topic. Weak: dark news commentary, the
     host's own career anecdote, long setup, chaos with no landing, intros/outros/ads.
4. **Make**: only that minute of video is downloaded (1080p), lined up with the audio to
   the frame, framed 9:16, hook bar on top, exact word-by-word captions (Whisper base),
   loudness -14 LUFS.
5. `POST.md` (caption + hashtags + where in the episode), `clips.json`, `report.json`.

Everything is cached step by step (audio, transcript chunks, picks, rendered clips), so
re-running the same command after an interruption — including the picking pause above —
resumes instead of redoing work.

## 2b. What the picker looks for (and why)

Based on 100 viral comedy-podcast clips (all 250k+ views, 176M total, median 1.0M). Clip
length, speech pace, hashtags and opening-word type did NOT predict views. What the top
clips shared (a hypothesis from reading the top 8 against the bottom 6, not a tested
result) — this is the same text baked into every `chunk_NN.txt` prompt, repeated here for
reference:
- **Live moment, no setup**: starts mid-exchange, needs no context.
- **A real person on the spot**: a kid, a parent on the phone, a stranger, a guest. Their
  answer is the joke.
- **One clear beat**, not a story.
- **Instantly understood topic**: family and kids, race, sports, everyday absurdity, big
  hot takes.
- **Weak in the data**: dark news commentary, the comedian's own career anecdote, long
  context before the joke, chaos with no landing.

Caveat: every clip in the study was already viral, so this says what winners share, not
what makes a clip fail. If clips come out weak, tune the `PROMPT` text in
`scripts/clipper/moments.py` (it's used both to build the chunk files and as the reference
copy here).

## 3. Run it

Launch with Desktop Commander's `start_process` (these are long jobs — downloading,
transcribing, encoding — so start it, then poll with `read_process_output` /
`interact_with_process` every so often and tell the user what's happening in plain words,
rather than blocking silently).

```
# Windows
powershell -File SKILL\scripts\podclip.ps1 URL
powershell -File SKILL\scripts\podclip.ps1 URL URL URL --clips 4
powershell -File SKILL\scripts\podclip.ps1 --find --list
powershell -File SKILL\scripts\podclip.ps1 --find --streams 5
powershell -File SKILL\scripts\podclip.ps1 URL --section "0:20:00-1:10:00"

# Mac/Linux
bash SKILL/scripts/podclip URL
```

| flag | use |
|---|---|
| `--clips N` | clips per episode (default 3) |
| `--streams N` | with `--find`: how many episodes (default 5) |
| `--parallel N` | episodes at the same time (default 2) |
| `--section A-B` | only that part (`h:mm:ss-h:mm:ss`) |
| `--cookies chrome\|edge\|...` | use the browser login: age-restricted or members-only videos |
| `--layout fit\|face\|auto\|stream` | force a look. **Default is `fit`** (see section 5) |
| `--min / --max` | clip length limits in seconds (defaults 20 / 75) |
| `--fast` | use a hardware encoder if ffmpeg reports a working one (NVENC/QSV/AMF on Windows, VideoToolbox on Mac) |
| `--redo` | pick the moments again — wipes `chunks/`, `moments.json`, `candidates.json` for that episode |
| `--keep-audio` | keep the audio after clipping |

Re-running the same command resumes: finished steps are cached in `~/podcast-clips/work/`.

## 4. Finding episodes (`--find`)

- **YouTube**: most-viewed long videos uploaded today for "comedy podcast full episode" (no
  key). Change the words with `"search"` in `~/podcast-clips/config.json`.
- **Watchlist** `~/podcast-clips/podcasts.txt` (`youtube:@handle`): each show's newest long
  episode from the last 96 hours. Edit it with the user. Twitch and Kick are not supported
  in this version (paste links by hand).
Videos under 20 minutes are skipped, since those are clips already.

## 5. Framing (the part that is not tuned yet)

The original layout code assumes a streamer: small facecam over gameplay, or one big face
to follow. Podcasts are usually a wide shot of two or more people, so:
- Default is **`fit`**: the whole 16:9 frame centered over a blurred copy. Safe, nobody
  gets cropped out, but the picture is small.
- `face` follows the LARGEST face, not the person speaking. Only use it for one-person shots.
- `auto` and `stream` can mistake a small face in a wide shot for a facecam. Avoid them for
  podcasts.
A better podcast look (crop to the active speaker, or stack two speakers) would need new
work in `scripts/clipper/layout.py`.

## 6. Before the user posts

Open each clip and check: captions readable, hook names the right show or guest, the clip
starts on the exchange and ends right after the payoff. The user posts; never post for
them. Only clip shows that allow it (many run clipping programs).

## 7. Problems

- **"Sign in to confirm your age"** or members-only: `--cookies chrome` (or `edge`, whatever
  browser the user is signed into on that machine).
- **"sound match weak"**: the clip may be a second off; `--redo` or check that clip.
- **Nothing in the chunk results**: low-energy episode, or a `.result.json` wasn't valid
  JSON — re-read the chunk and rewrite it.
- **Slow listening**: ~1-2 min per episode hour on a modern machine; use `--section`.
- **Disk**: ~0.1 GB per episode hour while working; audio is deleted after the clips are made.
- **ffmpeg/ffprobe not found on Windows**: `winget install Gyan.FFmpeg`, then open a new
  terminal (PATH changes need a fresh shell) before retrying.
- **No hardware encoder found with `--fast`**: ffmpeg's build doesn't have NVENC/QSV/AMF
  compiled in, or the GPU driver is too old — it falls back to libx264 automatically, just
  slower.
