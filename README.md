# Podcast Clipper: a free Claude skill (Claude chat + Desktop Commander, or Claude Code)

Give it comedy podcast episodes, or let it find the biggest recent ones, and it gives you vertical
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
git clone https://github.com/<CubeixRop>/podcast-clipper.git ~/.claude/skills/podcast-clipper
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

