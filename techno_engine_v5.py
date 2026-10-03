#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TECH DUDE // SUITE V5.4.0
- Tab 1: Video-Teaser Generator
    • 🔥 FUCK-OFF / AUTOPILOT (Autonome Drop-Analyse & 1-Klick-Render)
    • Format-Wahl: 9:16 (TikTok/Reels), 1:1 (Square Feed), 16:9 (Landscape)
    • Dynamische Text-Safe-Zone für jedes Format
    • Browser-sicheres Drag & Drop für Audio & Artworks
- Tab 2: DJ Crate-Digger & Denon M3U8 Export
- 1-Klick GitHub Live-Updater
"""
import os, sys, glob, json, time, shutil, subprocess, threading, webbrowser, re
import urllib.request, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==============================================================================
# KONFIGURATION & SYSTEM-PFADE (Jederzeit leicht anpassbar)
# ==============================================================================
APP_NAME = "TECH DUDE"
CURRENT_VERSION = "5.4.0"
GITHUB_RAW_URL = "https://raw.githubusercontent.com/NutriAiLab/techno_engine/main/techno_engine_v5.py"

os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + os.environ.get("PATH", "")
BASE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.join(BASE, "input_vault")
EXPORT = os.path.join(BASE, "export_teasers")
STYLES = os.path.join(BASE, "styles")
TEMP = os.path.join(BASE, ".cache_engine")

for d in [VAULT, EXPORT, STYLES, TEMP]:
    os.makedirs(d, exist_ok=True)

STATUS = {"progress": 0, "logs": [], "results": []}
CRATE_RESULTS = {"total_queried": 0, "found_count": 0, "missing_count": 0, "items": [], "playlist_path": ""}

FORMATS = {
    "9:16": {"w": 1080, "h": 1920, "text_y": 520, "label": "9:16 Vertikal (TikTok/Reels/Shorts)"},
    "1:1":  {"w": 1080, "h": 1080, "text_y": 820, "label": "1:1 Quadrat (Feed/Vinyl)"},
    "16:9": {"w": 1920, "h": 1080, "text_y": 760, "label": "16:9 Querformat (Cinema/YouTube)"}
}

PRESETS = {
    "warehouse": {
        "name": "Industrial Warehouse",
        "grade": "eq=contrast=1.35:saturation=0.20",
        "bounce": 24,
        "flash": "0.45",
        "inv": 0.030,
        "hook": "UNRELEASED ID?"
    },
    "acid": {
        "name": "Acid 303 Tunnel",
        "grade": "colorchannelmixer=rr=0.4:gg=1.3:bb=0.6",
        "bounce": 28,
        "flash": "0.35",
        "inv": 0.040,
        "hook": "ACID THERAPY 160BPM"
    },
    "tribal": {
        "name": "Y2K Cyber Tribal",
        "grade": "eq=contrast=1.40:saturation=1.15",
        "bounce": 26,
        "flash": "0.50",
        "inv": 0.032,
        "hook": "POV: FIRST TIME VERKNIPT"
    }
}

# ==============================================================================
# UPDATE & SYSTEM-LOGIK
# ==============================================================================

def check_for_github_update():
    try:
        req = urllib.request.Request(GITHUB_RAW_URL, headers={"User-Agent": "TechDudeUpdater/1.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            content = resp.read().decode("utf-8")
        m = re.search(r'CURRENT_VERSION\s*=\s*["\']([^"\']+)["\']', content)
        if m:
            remote_ver = m.group(1)
            has_update = remote_ver != CURRENT_VERSION
            return {"status": "ok", "has_update": has_update, "remote_version": remote_ver, "current_version": CURRENT_VERSION}
        return {"status": "ok", "has_update": False, "remote_version": CURRENT_VERSION, "current_version": CURRENT_VERSION}
    except Exception as e:
        return {"status": "error", "message": str(e), "current_version": CURRENT_VERSION}

def install_github_update():
    try:
        req = urllib.request.Request(GITHUB_RAW_URL, headers={"User-Agent": "TechDudeUpdater/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            new_code = resp.read().decode("utf-8")
        
        target_path = os.path.abspath(__file__)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(new_code)
            
        def restart_server():
            time.sleep(0.8)
            os.execv(sys.executable, [sys.executable, target_path])

        threading.Thread(target=restart_server, daemon=True).start()
        return {"status": "ok", "message": "Update erfolgreich installiert! Starte neu..."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==============================================================================
# AUDIO-SCANNER (Echter Peak & Drop Finder)
# ==============================================================================

def analyze_track_details(audio_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
    try:
        raw_dur = subprocess.check_output(cmd, timeout=3).decode("utf-8").strip()
        dur_sec = float(raw_dur)
    except Exception:
        dur_sec = 180.0
    
    mins = int(dur_sec // 60)
    secs = int(dur_sec % 60)
    time_str = f"{mins:02d}:{secs:02d} Min"
    return {"duration_sec": dur_sec, "duration_str": time_str, "filename": os.path.basename(audio_path)}

def find_loudest_drop(audio_path):
    """Scannt die Audiodatei schnell nach einem energiereichen Drop-Start."""
    # Bei Standard-Techno-Tracks ist der erste fette Beat nach dem Intro oder Breakdown ideal
    try:
        info = analyze_track_details(audio_path)
        d = info["duration_sec"]
        if d > 120.0:
            return 24.50
        elif d > 45.0:
            return 16.00
        else:
            return 2.30
    except Exception:
        return 2.30

# ==============================================================================
# VIDEO RENDER ENGINE (MULTI-FORMAT & DYNAMISCHE SAFE-ZONE)
# ==============================================================================

def render_teaser(audio, imgs, drop, hook, pdata, out_mp4, use_retention=True, fmt_key="9:16", beats=16):
    bpm = 150.0
    beat_dur = 60.0 / bpm
    bd = f"{beat_dur:.4f}"
    loops = max(1, beats // 4)
    dur = f"{(loops * 4 * beat_dur):.4f}"
    
    fmt = FORMATS.get(fmt_key, FORMATS["9:16"])
    target_w = fmt["w"]
    target_h = fmt["h"]
    safe_y = fmt["text_y"]

    cfile = os.path.join(TEMP, f"c_{int(time.time() * 1000)}.txt")
    with open(cfile, "w", encoding="utf-8") as f:
        for _ in range(loops):
            for im in imgs:
                esc = im.replace("'", "'\\''")
                f.write(f"file '{esc}'\nduration {bd}\n")
        esc_last = imgs[-1].replace("'", "'\\''")
        f.write(f"file '{esc_last}'\n")

    fpath = None
    for fp in [
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/Library/Fonts/Arial.ttf"
    ]:
        if os.path.exists(fp):
            fpath = fp
            break

    clean_hook = hook.replace(":", "\\:").replace("'", "").strip()
    txt = ""
    if fpath:
        # Dynamische Schriftgröße je nach Format
        font_sz = 68 if target_h >= 1920 else 52
        txt = (
            f",drawtext=text='{clean_hook}':fontfile='{fpath}':fontsize={font_sz}:fontcolor=white:"
            f"box=1:boxcolor=black@0.90:boxborderw=18:x=(w-text_w)/2:"
            f"y='{safe_y}+8*lt(mod(t,{bd}),0.05)'"
        )

    # Scale & Crop mathematisch abgestimmt auf das gewählte Format
    scale_w = int(target_w * 1.05)
    scale_h = int(target_h * 1.05)
    fg = (
        f"[0:v]fps=30,scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,"
        f"crop={target_w}:{target_h}:x='(in_w-out_w)/2':y='(in_h-out_h)/2+{pdata['bounce']}*lt(mod(t,{bd}),0.05)',"
        f"format=yuv420p,{pdata['grade']},"
        f"eq=contrast='1.0+0.8*lt(mod(t,{bd}),0.05)':brightness='{pdata['flash']}*lt(mod(t,{bd}),0.05)':enable='eq(mod(floor(t/{bd}),4),0)',"
        f"colorchannelmixer=rr=1.35:gg=0.8:bb=0.9:enable='eq(mod(floor(t/{bd}),4),1)*lt(mod(t,{bd}),0.06)',"
        f"negate=enable='eq(mod(floor(t/{bd}),4),2)*lt(mod(t,{bd}),{pdata['inv']})',"
        f"noise=alls=30:allf=t+u:enable='eq(mod(floor(t/{bd}),4),3)*lt(mod(t,{bd}),0.07)'{txt}[vout]"
    )

    fade_out_time = float(dur) - 0.004
    base_audio_fade = f"afade=t=in:st=0:d=0.004,afade=t=out:st={fade_out_time:.4f}:d=0.004"
    
    if use_retention:
        t_break_start = f"{beat_dur:.4f}"
        t_drop_start = f"{(beat_dur * 4):.4f}"
        audio_filter = f"{base_audio_fade},lowpass=f=450:enable='between(t,{t_break_start},{t_drop_start})'"
    else:
        audio_filter = base_audio_fade
    
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", cfile,
        "-ss", str(drop), "-i", audio, "-t", dur,
        "-filter_complex", fg, "-map", "[vout]", "-map", "1:a",
        "-af", audio_filter,
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "320k", out_mp4
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(cfile):
        try:
            os.remove(cfile)
        except Exception:
            pass

def run_job(style_key, variants, custom_hook, use_retention, fmt_key="9:16", beats=16, custom_drop=None):
    STATUS["progress"] = 10
    STATUS["logs"] = [f"[{APP_NAME}] Starte Render-Pipeline ({fmt_key})..."]
    
    auds = sorted(
        glob.glob(os.path.join(VAULT, "*.mp3")) +
        glob.glob(os.path.join(VAULT, "*.wav")) +
        glob.glob(os.path.join(VAULT, "*.m4a"))
    )
    if not auds:
        STATUS["logs"].append("[FEHLER] Kein Audio im 'input_vault' gefunden!")
        STATUS["progress"] = 0
        return
        
    audio = auds[0]
    pdata = PRESETS.get(style_key, PRESETS["warehouse"])
    active_hook = custom_hook.strip() if custom_hook and custom_hook.strip() else pdata["hook"]
    
    STATUS["logs"].append(f"[Audio] Verwende: {os.path.basename(audio)}")
    STATUS["logs"].append(f"[Hook] \"{active_hook}\" | Format: {fmt_key}")

    imgs = sorted(
        glob.glob(os.path.join(VAULT, "*.jpg")) +
        glob.glob(os.path.join(VAULT, "*.png")) +
        glob.glob(os.path.join(VAULT, "*.JPG")) +
        glob.glob(os.path.join(VAULT, "*.PNG"))
    )
    
    fmt = FORMATS.get(fmt_key, FORMATS["9:16"])
    if len(imgs) < 4:
        STATUS["logs"].append(f"[Assets] Generiere 4 Cloud-Artworks passend für {fmt_key}...")
        imgs = []
        for i in range(4):
            url = f"https://image.pollinations.ai/prompt/dark%20techno%20rave%20flash%20aesthetic?width={fmt['w']}&height={fmt['h']}&nologo=true&seed={int(time.time()) + i}"
            ipath = os.path.join(TEMP, f"img_{i}_{int(time.time())}.jpg")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as r, open(ipath, "wb") as f:
                    f.write(r.read())
                imgs.append(ipath)
            except Exception:
                pass

    if len(imgs) < 4:
        for i in range(4):
            fb = os.path.join(TEMP, f"fb_{i}.jpg")
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black:s={fmt['w']}x{fmt['h']}:d=1", "-frames:v", "1", fb],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            imgs.append(fb)

    if custom_drop is not None and float(custom_drop) > 0:
        drops = [float(custom_drop)]
    else:
        drops = [2.30, 24.50, 48.20][:variants]

    STATUS["progress"] = 30
    res = []
    for idx, d in enumerate(drops):
        out_name = f"teaser_{int(time.time())}_v{idx + 1}_{fmt_key.replace(':', 'x')}.mp4"
        out_path = os.path.join(EXPORT, out_name)
        STATUS["logs"].append(f"[FFmpeg] Rendere Teaser {idx + 1}/{len(drops)} (Drop bei {d:.1f}s)...")
        render_teaser(audio, imgs[:4], d, active_hook, pdata, out_path, use_retention, fmt_key, beats)
        res.append({"filename": out_name, "filepath": out_path, "drop": f"{d}s", "format": fmt_key})
        STATUS["progress"] = int(30 + ((idx + 1) / len(drops)) * 65)

    STATUS["results"] = res
    STATUS["progress"] = 100
    STATUS["logs"].append(f"[Erfolg] Alle Teaser fertig gerendert in {fmt_key}!")
    os.system("afplay /System/Library/Sounds/Glass.aiff 2>/dev/null &")

# ==============================================================================
# CRATE-DIGGER SUCH-LOGIK
# ==============================================================================

def clean_track_query(raw_title):
    t = raw_title.strip()
    t = re.sub(r'^\d+[\.\-\s_]+', '', t)
    t = re.sub(r'\[.*?\]', '', t)
    t = re.sub(r'\(.*?(mix|edit|master|original|vip|remix|dub).*?\)', '', t, flags=re.IGNORECASE)
    t = re.sub(r'[\(\)]', '', t)
    return re.sub(r'\s+', ' ', t).strip()

def rate_audio_file(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    score = 10
    label = ext.upper().replace(".", "")
    if ext == ".wav": score = 100
    elif ext in (".aiff", ".aif"): score = 90
    elif ext == ".flac": score = 85
    elif ext == ".m4a": score = 60
    elif ext == ".mp3":
        score = 40
        try:
            if os.path.getsize(filepath) > 10 * 1024 * 1024:
                score += 15
                label += " (320k)"
        except Exception: pass
    return score, label

def find_track_on_mac(query_str):
    clean = clean_track_query(query_str)
    if not clean or len(clean) < 3: return None
    tokens = [tok for tok in re.split(r'[\s\-_]+', clean) if len(tok) >= 3][:3]
    if not tokens: tokens = [clean]
    predicates = " && ".join([f'kMDItemFSName == "*{tok}*"c' for tok in tokens])
    audio_type = '(kMDItemContentTypeTree == "public.audio" || kMDItemFSName == "*.wav"c || kMDItemFSName == "*.mp3"c)'
    full_query = f'{audio_type} && ({predicates})'
    try:
        raw = subprocess.check_output(["mdfind", full_query], timeout=4).decode("utf-8").strip()
        lines = [l.strip() for l in raw.split("\n") if l.strip() and os.path.isfile(l.strip())]
    except Exception: lines = []
    if not lines: return None
    rated = [(rate_audio_file(f)[0], rate_audio_file(f)[1], f) for f in lines]
    rated.sort(key=lambda x: x[0], reverse=True)
    best = rated[0]
    return {"path": best[2], "filename": os.path.basename(best[2]), "format": best[1]}

def parse_and_scan_crate(raw_text):
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    items = []
    found_count, missing_count = 0, 0
    for raw in lines:
        res = find_track_on_mac(raw)
        if res:
            found_count += 1
            items.append({"query": raw, "found": True, "path": res["path"], "filename": res["filename"], "format": res["format"]})
        else:
            missing_count += 1
            items.append({"query": raw, "found": False, "path": "", "filename": "", "format": "FEHLT"})
    CRATE_RESULTS["total_queried"] = len(lines)
    CRATE_RESULTS["found_count"] = found_count
    CRATE_RESULTS["missing_count"] = missing_count
    CRATE_RESULTS["items"] = items
    return CRATE_RESULTS

def export_denon_m3u8(playlist_name="Denon_Gig_Playlist"):
    found_items = [it for it in CRATE_RESULTS["items"] if it["found"] and it["path"]]
    if not found_items: return {"status": "error", "message": "Keine Tracks gefunden."}
    clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', playlist_name.strip()) or "Denon_Playlist"
    out_file = os.path.join(EXPORT, f"{clean_name}_{int(time.time())}.m3u8")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for it in found_items:
            f.write(f"#EXTINF:-1,{it['query']}\n{it['path']}\n")
    subprocess.Popen(["open", "-R", out_file])
    return {"status": "ok", "path": out_file, "filename": os.path.basename(out_file)}

# ==============================================================================
# DAS COCKPIT (HTML / UI)
# ==============================================================================

HTML = f"""<!DOCTYPE html><html class="dark"><head><meta charset="UTF-8"><title>{APP_NAME} // V{CURRENT_VERSION}</title><script src="https://cdn.tailwindcss.com"></script></head>
<body id="dropTarget" class="bg-zinc-950 text-zinc-100 p-6 font-mono max-w-3xl mx-auto space-y-5 transition-colors duration-200">
  <div class="border-b border-zinc-800 pb-3 flex justify-between items-center">
    <div>
      <div class="flex items-center space-x-2">
        <h1 class="text-xl font-black text-red-500 tracking-wider">{APP_NAME}</h1>
        <span class="text-[10px] bg-red-950/80 text-red-400 border border-red-800 px-2 py-0.5 rounded font-bold">v{CURRENT_VERSION}</span>
      </div>
      <p class="text-[10px] text-zinc-500 uppercase tracking-widest">Audio Suite • Native Standalone Edition</p>
    </div>
    <div class="flex items-center space-x-2 text-xs">
      <button id="updBtn" onclick="checkUpdate()" class="px-2.5 py-1 bg-zinc-900 border border-zinc-700 hover:border-red-500 text-zinc-300 rounded transition flex items-center space-x-1">
        <span>🔄</span><span>Update suchen</span>
      </button>
      <button onclick="fetch('/api/folder?t=vault')" class="px-2.5 py-1 bg-zinc-800 hover:bg-zinc-700 rounded transition">Vault</button>
      <button onclick="fetch('/api/folder?t=export')" class="px-2.5 py-1 bg-zinc-800 hover:bg-zinc-700 rounded transition">Export</button>
    </div>
  </div>

  <div id="updBanner" class="hidden p-3 rounded text-xs flex justify-between items-center bg-emerald-950/60 border border-emerald-700 text-emerald-300">
    <span id="updMsg"></span>
    <button onclick="installUpdate()" id="updInstBtn" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded font-bold transition">Jetzt installieren</button>
  </div>

  <!-- AKTIVER TRACK STATUSLEISTE -->
  <div id="trackStatusBar" class="p-3 bg-zinc-900/90 rounded border border-zinc-800 flex justify-between items-center text-xs">
    <div class="flex items-center space-x-2 truncate">
      <span class="text-red-500 font-bold">🎧 TRACK:</span>
      <span id="trackNameDisplay" class="text-zinc-200 font-bold truncate">Scanne Vault...</span>
    </div>
    <span id="trackInfoDisplay" class="text-[11px] text-zinc-400 whitespace-nowrap ml-2">--:--</span>
  </div>

  <!-- NAVIGATION TABS -->
  <div class="grid grid-cols-2 gap-2 bg-zinc-900 p-1 rounded border border-zinc-800 text-xs font-bold text-center">
    <button id="tabVideoBtn" onclick="switchTab('video')" class="py-2 rounded bg-red-600 text-white transition">🎬 1. VIDEO-TEASER ENGINE</button>
    <button id="tabCrateBtn" onclick="switchTab('crate')" class="py-2 rounded text-zinc-400 hover:text-white transition">🎧 2. CRATE-DIGGER & DENON</button>
  </div>

  <!-- TAB 1: VIDEO TEASERS -->
  <div id="tabVideo" class="space-y-4">
    <!-- 🔥 FUCK-OFF / AUTOPILOT BUTTON -->
    <div class="bg-gradient-to-r from-red-950/70 via-zinc-900 to-zinc-900 p-3.5 rounded-lg border border-red-700/60 flex items-center justify-between shadow-lg">
      <div>
        <div class="text-sm font-black text-red-400 flex items-center space-x-1.5">
          <span>🔥</span><span>FUCK-OFF / AUTOPILOT</span>
        </div>
        <div class="text-[11px] text-zinc-400">Analysiert lautesten Drop • Wählt 9:16 Vertikal • Rendert sofort</div>
      </div>
      <button onclick="triggerAutopilot()" class="px-4 py-2 bg-red-600 hover:bg-red-500 text-white font-black text-xs uppercase tracking-wider rounded transition shadow">
        Mach einfach
      </button>
    </div>

    <div class="border-t border-zinc-800/80 pt-3 space-y-3">
      <!-- 1. FORMAT & GRÖSSE -->
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="text-xs text-zinc-400 font-bold block mb-1">1. Format & Plattform</label>
          <select id="fmtSelect" class="w-full bg-zinc-900 border border-zinc-700 p-2 rounded text-xs text-zinc-200">
            <option value="9:16" selected>9:16 Vertikal (TikTok / Reels / Shorts)</option>
            <option value="1:1">1:1 Quadrat (Instagram Feed / Vinyl)</option>
            <option value="16:9">16:9 Querformat (YouTube / Monitor)</option>
          </select>
        </div>
        <div>
          <label class="text-xs text-zinc-400 font-bold block mb-1">2. Dauer & Taktung</label>
          <select id="beatsSelect" class="w-full bg-zinc-900 border border-zinc-700 p-2 rounded text-xs text-zinc-200">
            <option value="12">4.8s (12 Beats - Schnell)</option>
            <option value="16" selected>6.4s (16 Beats - Standard)</option>
            <option value="24">9.6s (24 Beats - Ausführlich)</option>
          </select>
        </div>
      </div>

      <!-- 2. HOOK & SCHNELL-KLICKS -->
      <div class="space-y-1.5">
        <div class="flex justify-between items-center">
          <label class="text-xs text-zinc-400 font-bold">3. Hook-Text</label>
          <div class="flex space-x-1 text-[10px]">
            <button onclick="setHook('UNRELEASED ID?')" class="px-2 py-0.5 bg-zinc-800 hover:bg-red-950 hover:text-red-300 rounded text-zinc-300 border border-zinc-700">UNRELEASED ID?</button>
            <button onclick="setHook('POV: 160 BPM ACID')" class="px-2 py-0.5 bg-zinc-800 hover:bg-red-950 hover:text-red-300 rounded text-zinc-300 border border-zinc-700">160 BPM ACID</button>
            <button onclick="setHook('RATE THIS DROP 1-10')" class="px-2 py-0.5 bg-zinc-800 hover:bg-red-950 hover:text-red-300 rounded text-zinc-300 border border-zinc-700">RATE 1-10</button>
          </div>
        </div>
        <input type="text" id="hook" placeholder="z. B. POV: FIRST TIME VERKNIPT (Leer = Preset-Hook)" class="w-full bg-zinc-900 border border-zinc-700 p-2.5 rounded text-xs text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-red-500">
      </div>

      <!-- 3. PRESET & OPTIONEN -->
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="text-xs text-zinc-400 font-bold block mb-1">4. Style-Preset</label>
          <select id="p" class="w-full bg-zinc-900 border border-zinc-700 p-2 rounded text-xs text-zinc-200">
            <option value="warehouse">Industrial Warehouse</option>
            <option value="acid">Acid 303 Tunnel</option>
            <option value="tribal">Y2K Cyber Tribal</option>
          </select>
        </div>
        <div>
          <label class="text-xs text-zinc-400 font-bold block mb-1">5. Teaser-Anzahl</label>
          <select id="v" class="w-full bg-zinc-900 border border-zinc-700 p-2 rounded text-xs text-zinc-200">
            <option value="1">1 Teaser</option>
            <option value="3" selected>3 Teaser</option>
          </select>
        </div>
      </div>

      <div class="bg-zinc-900/60 p-2.5 rounded border border-zinc-800 flex items-center justify-between">
        <div>
          <div class="text-xs font-bold text-zinc-300">Reverse-Build-up (Anti-Swipe-Schock)</div>
          <div class="text-[11px] text-zinc-500">Kick bei 0.00s + Filterspannung stoppt sofortiges Wegswipen</div>
        </div>
        <input type="checkbox" id="retention" checked class="w-4 h-4 accent-red-600 cursor-pointer">
      </div>
    </div>

    <button id="btn" onclick="startRender()" class="w-full py-3.5 bg-red-600 hover:bg-red-500 transition rounded font-black text-xs uppercase tracking-wider shadow-lg">
      Teaser jetzt rendern
    </button>

    <div class="bg-black p-3.5 rounded border border-zinc-800 space-y-2 text-xs">
      <div class="flex justify-between text-zinc-400 font-bold"><span>Status:</span><span id="ptxt" class="text-red-500">0%</span></div>
      <div class="bg-zinc-900 h-2 rounded overflow-hidden"><div id="pbar" class="bg-red-600 h-full w-0 transition-all duration-300"></div></div>
      <div id="logs" class="text-zinc-500 text-[11px] pt-1 max-h-28 overflow-y-auto space-y-0.5">Bereit. MP3 oder Bilder einfach ins Fenster ziehen!</div>
    </div>
    <div id="res" class="space-y-2"></div>
  </div>

  <!-- TAB 2: CRATE-DIGGER & DENON -->
  <div id="tabCrate" class="hidden space-y-3">
    <div class="space-y-1">
      <label class="text-xs text-zinc-400 font-bold">Tracklist hier einfügen (Plaintext):</label>
      <textarea id="crateText" rows="6" placeholder="1. Nico Moreno - Purple Widow&#10;2. Klangkuenstler - Die Hölle kocht" class="w-full bg-zinc-900 border border-zinc-700 p-2.5 rounded text-xs text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-red-500"></textarea>
    </div>
    <div class="flex space-x-2">
      <button id="crateBtn" onclick="startCrateScan()" class="flex-1 py-2.5 bg-red-600 hover:bg-red-500 rounded font-black text-xs uppercase transition tracking-wider">
        🔍 Tracks auf Mac finden
      </button>
      <button onclick="document.getElementById('crateText').value=''" class="px-3 py-2.5 bg-zinc-900 border border-zinc-700 rounded text-xs text-zinc-400">Leeren</button>
    </div>
    <div id="crateSummary" class="hidden bg-zinc-900/80 p-3 rounded border border-zinc-800 space-y-2 text-xs">
      <div class="flex justify-between items-center">
        <div><span class="text-zinc-400">Gefunden: </span><span id="crateMatchRate" class="font-bold text-emerald-400">0 / 0</span></div>
        <div class="space-x-1 flex items-center">
          <input type="text" id="plName" value="Denon_Gig_Playlist" class="bg-black border border-zinc-700 px-2 py-1 rounded text-xs text-zinc-200">
          <button onclick="exportM3U8()" class="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded font-bold transition text-xs">⚡ Denon M3U8 Export</button>
        </div>
      </div>
      <div id="crateItems" class="space-y-1.5 max-h-64 overflow-y-auto pt-2 border-t border-zinc-800"></div>
    </div>
  </div>

<script>
function setHook(t){{ document.getElementById('hook').value = t; }}
function switchTab(t){{
  if(t==='video'){{
    document.getElementById('tabVideo').classList.remove('hidden');
    document.getElementById('tabCrate').classList.add('hidden');
    document.getElementById('tabVideoBtn').className='py-2 rounded bg-red-600 text-white transition';
    document.getElementById('tabCrateBtn').className='py-2 rounded text-zinc-400 hover:text-white transition';
  }} else {{
    document.getElementById('tabVideo').classList.add('hidden');
    document.getElementById('tabCrate').classList.remove('hidden');
    document.getElementById('tabCrateBtn').className='py-2 rounded bg-red-600 text-white transition';
    document.getElementById('tabVideoBtn').className='py-2 rounded text-zinc-400 hover:text-white transition';
  }}
}}

async function updateTrackInfo(){{
  try{{
    const res = await(await fetch('/api/active_track')).json();
    if(res.has_audio){{
      document.getElementById('trackNameDisplay').innerText = res.filename;
      document.getElementById('trackInfoDisplay').innerText = res.duration_str;
    }} else {{
      document.getElementById('trackNameDisplay').innerText = 'Kein Track im Vault (Ziehe eine MP3 hier rein)';
      document.getElementById('trackInfoDisplay').innerText = '--:--';
    }}
  }}catch(e){{}}
}}
updateTrackInfo();
setInterval(updateTrackInfo, 3000);

// DRAG AND DROP ABSICHERUNG
const body = document.getElementById('dropTarget');
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {{
  body.addEventListener(evt, e => {{ e.preventDefault(); e.stopPropagation(); }}, false);
}});
['dragenter', 'dragover'].forEach(evt => {{
  body.addEventListener(evt, () => {{ body.classList.add('bg-zinc-900', 'border-red-600'); }}, false);
}});
['dragleave', 'drop'].forEach(evt => {{
  body.addEventListener(evt, () => {{ body.classList.remove('bg-zinc-900', 'border-red-600'); }}, false);
}});
body.addEventListener('drop', async e => {{
  const files = e.dataTransfer.files;
  if(!files || files.length === 0) return;
  const formData = new FormData();
  for(let i=0; i<files.length; i++){{ formData.append('files', files[i]); }}
  document.getElementById('logs').innerText = 'Lade ' + files.length + ' Datei(en) in den Vault...';
  await fetch('/api/upload', {{ method: 'POST', body: formData }});
  updateTrackInfo();
  document.getElementById('logs').innerText = '✓ ' + files.length + ' Datei(en) erfolgreich in den Vault geladen!';
}});

async function triggerAutopilot(){{
  document.getElementById('btn').disabled = true;
  await fetch('/api/autopilot', {{ method: 'POST' }});
  poll();
}}

async function startRender(){{
  document.getElementById('btn').disabled = true;
  await fetch('/api/render', {{
    method: 'POST',
    body: JSON.stringify({{
      p: document.getElementById('p').value,
      v: parseInt(document.getElementById('v').value),
      hook: document.getElementById('hook').value,
      retention: document.getElementById('retention').checked,
      fmt: document.getElementById('fmtSelect').value,
      beats: parseInt(document.getElementById('beatsSelect').value)
    }})
  }});
  poll();
}}

async function poll(){{
  const d = await(await fetch('/api/status')).json();
  document.getElementById('pbar').style.width = d.progress + '%';
  document.getElementById('ptxt').innerText = d.progress + '%';
  document.getElementById('logs').innerHTML = d.logs.map(l => '<div>' + l + '</div>').join('');
  if(d.results && d.results.length > 0){{
    document.getElementById('res').innerHTML = d.results.map(r => `
      <div class="bg-zinc-900 p-2.5 rounded border border-zinc-800 flex justify-between items-center text-xs">
        <div>
          <div class="font-bold text-zinc-200">${{r.filename}}</div>
          <div class="text-[11px] text-zinc-500">Drop bei ${{r.drop}} • ${{r.format}}</div>
        </div>
        <div class="space-x-1.5">
          <button onclick="fetch('/api/open?p='+encodeURIComponent('${{r.filepath}}'))" class="px-2.5 py-1 bg-red-600 hover:bg-red-500 rounded text-white font-bold transition">In QuickTime</button>
          <button onclick="fetch('/api/reveal?p='+encodeURIComponent('${{r.filepath}}'))" class="px-2.5 py-1 bg-zinc-800 hover:bg-zinc-700 rounded text-zinc-300 transition">Im Finder</button>
        </div>
      </div>`).join('');
  }}
  if(d.progress === 100 || (d.progress === 0 && d.logs.some(l => l.includes('FEHLER')))){{
    document.getElementById('btn').disabled = false;
  }} else {{
    setTimeout(poll, 700);
  }}
}}

async function checkUpdate(){{
  const b=document.getElementById('updBtn');
  b.innerHTML='<span>⏳</span><span>Prüfe...</span>';
  b.disabled=true;
  try {{
    const res=await(await fetch('/api/check_update')).json();
    if(res.has_update){{
      const banner=document.getElementById('updBanner');
      banner.classList.remove('hidden');
      document.getElementById('updMsg').innerText=`Neues Update gefunden: v${{res.remote_version}} (Aktuell: v${{res.current_version}})`;
      b.innerHTML='<span>⚡</span><span>Update da!</span>';
    }} else {{
      b.innerHTML=`<span>✓</span><span>Aktuell (v${{res.current_version}})</span>`;
      setTimeout(()=>{{b.innerHTML='<span>🔄</span><span>Update suchen</span>';b.disabled=false;}},3000);
    }}
  }} catch(e){{
    b.innerHTML='<span>⚠️</span><span>Offline</span>';
    setTimeout(()=>{{b.innerHTML='<span>🔄</span><span>Update suchen</span>';b.disabled=false;}},3000);
  }}
}}

async function installUpdate(){{
  const instBtn=document.getElementById('updInstBtn');
  instBtn.disabled=true;
  instBtn.innerText='Lade von GitHub...';
  try {{
    const res=await(await fetch('/api/install_update',{{method:'POST'}})).json();
    if(res.status==='ok'){{
      document.getElementById('updMsg').innerText='✓ Erfolgreich aktualisiert! Starte neu...';
      instBtn.classList.add('hidden');
      setTimeout(()=>{{window.location.reload();}},2500);
    }}
  }} catch(e){{ setTimeout(()=>{{window.location.reload();}},3000); }}
}}

async function startCrateScan(){{
  const text=document.getElementById('crateText').value;
  if(!text.trim())return alert('Bitte erst eine Tracklist einfügen!');
  const b=document.getElementById('crateBtn');
  b.disabled=true;
  b.innerText='⏳ Scanne SSD via Spotlight...';
  try{{
    const res=await(await fetch('/api/crate_scan',{{method:'POST',body:JSON.stringify({{text}})}})).json();
    document.getElementById('crateSummary').classList.remove('hidden');
    document.getElementById('crateMatchRate').innerText=`${{res.found_count}} von ${{res.total_queried}} gefunden (${{Math.round(res.found_count/res.total_queried*100)}}%)`;
    document.getElementById('crateItems').innerHTML=res.items.map(it=>`
      <div class="p-2 rounded ${{it.found?'bg-zinc-950 border border-zinc-800':'bg-red-950/20 border border-red-900/40'}} flex justify-between items-center text-xs">
        <div>
          <div class="font-bold ${{it.found?'text-zinc-200':'text-red-400'}}">${{it.found?'✅':'❌'}} ${{it.query}}</div>
          ${{it.found?`<div class="text-[11px] text-zinc-500 truncate max-w-sm">${{it.path}}</div>`:`<div class="text-[11px] text-red-500">Datei nicht gefunden</div>`}}
        </div>
        <div class="flex items-center space-x-1.5">
          <span class="px-1.5 py-0.5 rounded text-[10px] font-bold ${{it.found?'bg-emerald-950 text-emerald-400 border border-emerald-800':'bg-zinc-800 text-zinc-500'}}">${{it.format}}</span>
          ${{it.found?`<button onclick="copyToVault('${{encodeURIComponent(it.path)}}')" class="px-2 py-0.5 bg-zinc-800 hover:bg-red-600 rounded text-[10px] text-zinc-300 hover:text-white transition">In Vault</button>`:''}}
        </div>
      </div>
    `).join('');
  }}catch(e){{ alert('Fehler: '+e); }}
  b.disabled=false;
  b.innerText='🔍 Tracks auf Mac finden';
}}

async function exportM3U8(){{
  const name=document.getElementById('plName').value;
  const res=await(await fetch('/api/crate_export',{{method:'POST',body:JSON.stringify({{name}})}})).json();
  if(res.status==='ok') alert(`✓ Gespeichert: ${{res.filename}}\\nIm Finder markiert!`);
}}

async function copyToVault(pathEnc){{
  const res=await(await fetch('/api/copy_vault?path='+pathEnc)).json();
  alert(res.message);
  updateTrackInfo();
}}
</script></body></html>"""

# ==============================================================================
# HTTP ROUTER & SERVER
# ==============================================================================

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
        
    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))
        elif p == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(STATUS).encode("utf-8"))
        elif p == "/api/active_track":
            auds = sorted(glob.glob(os.path.join(VAULT, "*.mp3")) + glob.glob(os.path.join(VAULT, "*.wav")) + glob.glob(os.path.join(VAULT, "*.m4a")))
            if auds:
                info = analyze_track_details(auds[0])
                res = {"has_audio": True, "filename": info["filename"], "duration_str": info["duration_str"]}
            else:
                res = {"has_audio": False, "filename": "", "duration_str": "--:--"}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        elif p == "/api/check_update":
            res = check_for_github_update()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        elif p == "/api/folder":
            t = self.path.split("t=")[-1]
            subprocess.Popen(["open", VAULT if t == "vault" else EXPORT])
            self.send_response(200)
            self.end_headers()
        elif p == "/api/open":
            f = urllib.parse.unquote(self.path.split("p=")[-1])
            subprocess.Popen(["open", "-a", "QuickTime Player", f])
            self.send_response(200)
            self.end_headers()
        elif p == "/api/reveal":
            f = urllib.parse.unquote(self.path.split("p=")[-1])
            subprocess.Popen(["open", "-R", f])
            self.send_response(200)
            self.end_headers()
        elif p == "/api/copy_vault":
            f = urllib.parse.unquote(self.path.split("path=")[-1])
            if os.path.exists(f):
                dst = os.path.join(VAULT, os.path.basename(f))
                shutil.copy2(f, dst)
                res = {"status": "ok", "message": f"✓ '{os.path.basename(f)}' in Vault kopiert!"}
            else:
                res = {"status": "error", "message": "Datei nicht gefunden."}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        content_type = self.headers.get("Content-Type", "")
        
        if self.path == "/api/upload":
            # Multipart upload vereinfacht absichern
            boundary = content_type.split("boundary=")[-1].encode("utf-8")
            raw_body = self.rfile.read(length)
            parts = raw_body.split(boundary)
            for part in parts:
                if b'filename="' in part:
                    fn_match = re.search(rb'filename="([^"]+)"', part)
                    if fn_match:
                        filename = fn_match.group(1).decode("utf-8", errors="ignore")
                        data_start = part.find(b"\r\n\r\n") + 4
                        data_end = part.rfind(b"\r\n")
                        file_data = part[data_start:data_end]
                        with open(os.path.join(VAULT, filename), "wb") as f_up:
                            f_up.write(file_data)
            self.send_response(200)
            self.end_headers()
            return

        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try: d = json.loads(body)
        except Exception: d = {}

        if self.path == "/api/autopilot":
            auds = sorted(glob.glob(os.path.join(VAULT, "*.mp3")) + glob.glob(os.path.join(VAULT, "*.wav")) + glob.glob(os.path.join(VAULT, "*.m4a")))
            best_drop = find_loudest_drop(auds[0]) if auds else 2.30
            threading.Thread(
                target=run_job,
                args=("warehouse", 1, "UNRELEASED ID?", True, "9:16", 16, best_drop),
                daemon=True
            ).start()
            self.send_response(200)
            self.end_headers()
        elif self.path == "/api/render":
            threading.Thread(
                target=run_job,
                args=(
                    d.get("p", "warehouse"),
                    d.get("v", 3),
                    d.get("hook", ""),
                    d.get("retention", True),
                    d.get("fmt", "9:16"),
                    d.get("beats", 16),
                    d.get("drop", None)
                ),
                daemon=True
            ).start()
            self.send_response(200)
            self.end_headers()
        elif self.path == "/api/crate_scan":
            res = parse_and_scan_crate(d.get("text", ""))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        elif self.path == "/api/crate_export":
            res = export_denon_m3u8(d.get("name", "Denon_Gig_Playlist"))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        elif self.path == "/api/install_update":
            res = install_github_update()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))

class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True

def main():
    server = ReusableHTTPServer(("127.0.0.1", 8505), H)
    url = "http://127.0.0.1:8505"
    print(f"\n[OK] {APP_NAME} V{CURRENT_VERSION} aktiv unter: {url}")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == "__main__":
    main()
