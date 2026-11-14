# One-time setup for podcast-clipper on Windows. Safe to run again. Prints "All set" at the end.
$ErrorActionPreference = "Stop"
$EnvDir = Join-Path $HOME ".podcast-clipper"
$Venv = Join-Path $EnvDir "venv"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Missing = $false

function Ok($msg)  { Write-Host "[OK] $msg" -ForegroundColor Green }
function Bad($msg) { Write-Host "[X]  $msg" -ForegroundColor Red; $script:Missing = $true }

Write-Host "podcast-clipper setup (Windows)"

if (Get-Command ffmpeg -ErrorAction SilentlyContinue) { Ok "ffmpeg" }
else { Bad "ffmpeg missing: winget install Gyan.FFmpeg  (or add it to PATH)" }

if (Get-Command ffprobe -ErrorAction SilentlyContinue) { Ok "ffprobe" }
else { Bad "ffprobe missing (usually installed alongside ffmpeg)" }

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) { $pythonCmd = Get-Command py -ErrorAction SilentlyContinue }
if ($pythonCmd) { Ok "Python ($($pythonCmd.Source))" }
else { Bad "Python missing: winget install Python.Python.3.11" }

$jsRuntime = $null
foreach ($name in @("deno", "node", "bun")) {
    if (Get-Command $name -ErrorAction SilentlyContinue) { $jsRuntime = $name; break }
}
if ($jsRuntime) { Ok "JavaScript runtime ($jsRuntime) — YouTube needs one" }
else { Bad "no deno/node/bun found: winget install DenoLand.Deno  (YouTube downloads need it)" }

$drive = Get-PSDrive -Name ($HOME.Substring(0, 1))
$freeGb = [math]::Round($drive.Free / 1GB, 1)
if ($freeGb -ge 2) { Ok "disk: $freeGb GB free" }
else { Bad "only $freeGb GB free; setup needs ~1 GB, clipping ~0.1 GB per stream hour" }

if ($Missing) {
    Write-Host ""
    Write-Host "Fix the [X] lines above, then run this again."
    exit 1
}

New-Item -ItemType Directory -Force -Path $EnvDir | Out-Null
$VenvPython = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    $pyExe = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
    & $pyExe -m venv $Venv
}

$pkgs = @("faster-whisper", "opencv-python-headless<5", "pillow", "numpy", "yt-dlp")
& $VenvPython -m pip install -q -U pip
& $VenvPython -m pip install -q -U @pkgs
Ok "Python packages (private env in $EnvDir)"

& $VenvPython -c @"
from faster_whisper import WhisperModel
for name in ('tiny', 'base'):
    WhisperModel(name, device='cpu', compute_type='int8')
print('Whisper models downloaded (tiny = listening, base = captions)')
"@
Ok "Whisper models"

$modelsDir = Join-Path $EnvDir "models"
New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null
$yunet = Join-Path $modelsDir "yunet.onnx"
if (-not (Test-Path $yunet) -or (Get-Item $yunet).Length -eq 0) {
    try {
        Invoke-WebRequest -UseBasicParsing -Uri `
          "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx" `
          -OutFile $yunet
        Ok "facecam finder (OpenCV YuNet, 0.2 MB)"
    } catch {
        Write-Host "! facecam model download failed; clips fall back to a simpler face finder"
    }
} else {
    Ok "facecam finder (already downloaded)"
}

$clipsHome = Join-Path $HOME "podcast-clips"
New-Item -ItemType Directory -Force -Path $clipsHome | Out-Null
$watchlist = Join-Path $clipsHome "podcasts.txt"
if (-not (Test-Path $watchlist)) {
    $default = Join-Path $Here "..\podcasts.txt"
    if (Test-Path $default) { Copy-Item $default $watchlist } else { New-Item -ItemType File $watchlist | Out-Null }
}
Ok "watchlist: $watchlist"

$arialBold = "C:\Windows\Fonts\arialbd.ttf"
if (Test-Path $arialBold) { Ok "caption/hook font (Arial Bold)" }
else { Write-Host "! Arial Bold not found at $arialBold — set hook_font_file in config.json to a font you have" }
$emojiFont = "C:\Windows\Fonts\seguiemj.ttf"
if (Test-Path $emojiFont) { Ok "emoji font (Segoe UI Emoji)" }
else { Write-Host "! Segoe UI Emoji not found — hook emoji will be skipped unless emoji_font_file is set in config.json" }

Write-Host ""
Write-Host "All set. Try:  powershell -File `"$Here\podclip.ps1`" --find --list"
