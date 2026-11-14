# Podcast Clipper: a free Claude skill (Claude chat + Desktop Commander, or Claude Code)

Adapted from a GTA 6 stream clipper, then adapted again to run from **Claude chat on Windows**
via the Desktop Commander connector (Claude Code / Cowork / Mac still work too). Give it
comedy podcast episodes, or let it find the biggest recent ones, and it gives you vertical
clips with a hook title bar and word-by-word captions, plus a caption and hashtags per clip
to paste.

- Reads the whole episode: transcript, plus where the room got loud (laughter). **Claude
  picks the moments itself**, reading transcript chunks directly in chat — no `claude -p`
  subprocess, no API key, no Claude Code requirement.
- The picking prompt uses what the top clips in a 100-clip comedy-podcast study had in
  common (live moment, a real person on the spot, one clear beat, instantly understood
  topic). That finding is a hypothesis; see SKILL.md section 2b.
- $0 per clip: everything runs on the user's own computer. No API keys.
- Small downloads: audio of the episode, plus only the minutes that become clips.

## Get it

**Clone this repo** (recommended — easiest to update later):
```
git clone https://github.com/<your-username>/podcast-clipper.git ~/.claude/skills/podcast-clipper
```
Replace the URL with wherever you push this. If you don't use git, download the repo as a
ZIP from GitHub's "Code" button and unzip it into `~/.claude/skills/podcast-clipper` instead.

**Or get the packaged `.skill` file**, if you've attached one to a release on this repo, and
drag it straight into a Claude.ai or Cowork chat — a **Save skill** button installs it, if
your organization allows custom skills.

## Install

However you got the folder onto disk, place it at `~/.claude/skills/podcast-clipper` (or
wherever your client reads skills from), then run setup on the machine that will do the work:
- **Windows**: `powershell -File ~/.claude/skills/podcast-clipper/scripts/setup.ps1` until
  it prints "All set". Needs `ffmpeg` and `deno`/`node`/`bun` on PATH
  (`winget install Gyan.FFmpeg DenoLand.Deno`).
- **Mac/Linux**: `bash ~/.claude/skills/podcast-clipper/scripts/setup.sh` until it prints
  "All set". Needs `ffmpeg` and `deno`/`node`/`bun`.

In Claude chat, connect the **Desktop Commander** connector so Claude can run these scripts
and read/write files on your machine. Then say: *"clip this episode: <link>"* or *"find
today's biggest comedy podcast episodes and clip them"*.

## How picking moments works now (the main change from the Claude Code version)

The original version ran on Claude Code and had the script call `claude -p` as a
subprocess to pick moments — that only works inside Claude Code. This version instead:

1. The script writes each ~12-minute window of the episode's transcript to its own
   `chunk_NN.txt` prompt file and stops.
2. Claude (in your chat) reads each one and writes back a `chunk_NN.result.json` with its
   picks — the same reasoning a `claude -p` call would have done, just done directly by the
   assistant you're already talking to.
3. You run the exact same command again; it picks up the written results and renders.

See `SKILL.md` for the full step-by-step Claude follows.

## What changed from the GTA 6 version

| File | Change |
|---|---|
| `moments.py` | New picking prompt and clip kinds; `claude -p` subprocess replaced with chunk files Claude reads/writes directly |
| `find.py` | YouTube only; episodes not streams; skips videos under 20 min; Twitch API removed |
| `config.py` | Podcast search words, clips 20-75 s, default layout `fit`, 96 h watchlist window, platform-aware font/encoder defaults |
| `hook.py` | Emoji rendering handles both fixed-strike bitmap fonts (Apple Color Emoji) and scalable colour fonts (Segoe UI Emoji on Windows) |
| `render.py`, `util.py` | Hardware encoder is auto-detected from what ffmpeg reports (VideoToolbox / NVENC / QSV / AMF / VAAPI) instead of hardcoded to Mac's VideoToolbox |
| `run.py`, setup, launcher | Renamed (`podclip`, `~/podcast-clips`, `~/.podcast-clipper`); added Windows `setup.ps1` / `podclip.ps1`; dropped the `claude` binary requirement and `--model` flag |
| `podcasts.txt` | Comedy podcast YouTube handles (replaces the streamer list) |
| unchanged | `fetch.py`, `scan.py`, `captions.py`, `layout.py` (logic), `podclip` / `setup.sh` (Mac/Linux still work as before) |

## Not tested

Only offline checks were run: all files compile, the picking prompt fills in correctly, the
JSON parser and time snapping work, and the episode finder drops short videos and keeps the
biggest per show. Nothing was run against real downloads, Whisper, ffmpeg, or a live Desktop
Commander session on an actual Windows machine — in particular, double-check the Windows
font paths (`arialbd.ttf`, `seguiemj.ttf`) and the hardware-encoder names ffmpeg reports on
the user's GPU/driver before relying on `--fast`. Podcast framing (`layout.py`) is untouched
and defaults to `fit`.

## License

MIT — see [LICENSE](LICENSE). Only clip shows that allow clipping; you're responsible for
how you use this.

