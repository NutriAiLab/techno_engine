#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HARD-TECHNO ENGINE V5.3.0
- Tab 1: Video-Teaser Generator (TikTok/Reels Safe-Zone, Reverse-Build-up, Bass-Bounce)
- Tab 2: DJ Crate-Digger (Spotlight-Suche via mdfind, Best-Version WAV > MP3, Denon .m3u8 Export)
- 1-Klick GitHub Live-Updater
"""
import os, sys, glob, json, time, shutil, subprocess, threading, webbrowser, re
import urllib.request, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + os.environ.get("PATH", "")
BASE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.join(BASE, "input_vault")
EXPORT = os.path.join(BASE, "export_teasers")
STYLES = os.path.join(BASE, "styles")
TEMP = os.path.join(BASE, ".cache_engine")

CURRENT_VERSION = "5.3.0"
GITHUB_RAW_URL = "https://raw.githubusercontent.com/NutriAiLab/techno_engine/main/techno_engine_v5.py"

for d in [VAULT, EXPORT, STYLES, TEMP]:
    os.makedirs(d, exist_ok=True)

# Status-Speicher
STATUS = {"progress": 0, "logs": [], "results": []}
CRATE_RESULTS = {"total_queried": 0, "found_count": 0, "missing_count": 0, "items": [], "playlist_path": ""}

def check_for_github_update():
    """Prüft online auf GitHub, ob eine neuere Version hinterlegt ist."""
    try:
        req = urllib.request.Request(GITHUB_RAW_URL, headers={"User-Agent": "TechnoEngineUpdater/1.0"})
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
    """Lädt den neuesten Code direkt von GitHub herunter und aktualisiert die Datei."""
    try:
        req = urllib.request.Request(GITHUB_RAW_URL, headers={"User-Agent": "TechnoEngineUpdater/1.0"})
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
# 1. CRATE-DIGGER & SPOTLIGHT SUCH-LOGIK
# ==============================================================================

def clean_track_query(raw_title):
    """Bereinigt Track-Titel von Playlisten-Nummerierungen und Zusätzen."""
    t = raw_title.strip()
    t = re.sub(r'^\d+[\.\-\s_]+', '', t)
    t = re.sub(r'\[.*?\]', '', t)
    t = re.sub(r'\(.*?(mix|edit|master|original|vip|remix|dub).*?\)', '', t, flags=re.IGNORECASE)
    t = re.sub(r'[\(\)]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def rate_audio_file(filepath):
    """Bewertet gefundene Dateien nach Audioqualität (WAV > AIFF > FLAC > MP3)."""
    ext = os.path.splitext(filepath)[1].lower()
    score = 10
    label = ext.upper().replace(".", "")
    if ext == ".wav":
        score = 100
    elif ext in (".aiff", ".aif"):
        score = 90
    elif ext == ".flac":
        score = 85
    elif ext == ".m4a":
        score = 60
    elif ext == ".mp3":
        score = 40
        try:
            sz = os.path.getsize(filepath)
            if sz > 10 * 1024 * 1024:
                score += 15
                label += " (320k)"
            else:
                label += " (Standard)"
        except Exception:
            pass
    return score, label

def find_track_on_mac(query_str):
    """Sucht via macOS Spotlight (mdfind) blitzschnell nach der besten Audio-Datei."""
    clean = clean_track_query(query_str)
    if not clean or len(clean) < 3:
        return None
    
    tokens = [tok for tok in re.split(r'[\s\-_]+', clean) if len(tok) >= 3][:3]
    if not tokens:
        tokens = [clean]
    
    predicates = " && ".join([f'kMDItemFSName == "*{tok}*"c' for tok in tokens])
    audio_type = '(kMDItemContentTypeTree == "public.audio" || kMDItemFSName == "*.wav"c || kMDItemFSName == "*.mp3"c || kMDItemFSName == "*.aiff"c || kMDItemFSName == "*.flac"c)'
    full_query = f'{audio_type} && ({predicates})'
    
    try:
        raw = subprocess.check_output(["mdfind", full_query], timeout=4).decode("utf-8").strip()
        lines = [line.strip() for line in raw.split("\n") if line.strip() and os.path.isfile(line.strip())]
        if not lines:
            fallback_query = f'{audio_type} && kMDItemFSName == "*{tokens[0]}*"c'
            raw = subprocess.check_output(["mdfind", fallback_query], timeout=4).decode("utf-8").strip()
            lines = [line.strip() for line in raw.split("\n") if line.strip() and os.path.isfile(line.strip())]
    except Exception:
        lines = []

    if not lines:
        return None
    
    rated = []
    for f in lines:
        sc, lbl = rate_audio_file(f)
        rated.append((sc, lbl, f))
    rated.sort(key=lambda x: x[0], reverse=True)
    best = rated[0]
    return {"path": best[2], "filename": os.path.basename(best[2]), "format": best[1], "score": best[0]}

def parse_and_scan_crate(raw_text):
    """Verarbeitet eine Liste aus dem Textfeld und ordnet Dateien zu."""
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    items = []
    found_count = 0
    missing_count = 0
    
    for raw in lines:
        res = find_track_on_mac(raw)
        if res:
            found_count += 1
            items.append({
                "query": raw,
                "found": True,
                "path": res["path"],
                "filename": res["filename"],
                "format": res["format"]
            })
        else:
            missing_count += 1
            items.append({
                "query": raw,
                "found": False,
                "path": "",
                "filename": "",
                "format": "FEHLT"
            })
            
    CRATE_RESULTS["total_queried"] = len(lines)
    CRATE_RESULTS["found_count"] = found_count
    CRATE_RESULTS["missing_count"] = missing_count
    CRATE_RESULTS["items"] = items
    return CRATE_RESULTS

def export_denon_m3u8(playlist_name="Denon_Gig_Playlist"):
    """Erzeugt eine Standard M3U8 Playlist, die Denon Engine DJ direkt einliest."""
    found_items = [it for it in CRATE_RESULTS["items"] if it["found"] and it["path"]]
    if not found_items:
        return {"status": "error", "message": "Keine gefundenen Tracks zum Exportieren vorhanden."}
    
    clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', playlist_name.strip()) or "Denon_Playlist"
    out_file = os.path.join(EXPORT, f"{clean_name}_{int(time.time())}.m3u8")
    
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for it in found_items:
            f.write(f"#EXTINF:-1,{it['query']}\n")
            f.write(f"{it['path']}\n")
            
    CRATE_RESULTS["playlist_path"] = out_file
    subprocess.Popen(["open", "-R", out_file])
    return {"status": "ok", "path": out_file, "filename": os.path.basename(out_file)}

# ==============================================================================
# 2. VIDEO-RENDER-PIPELINE (UNVERÄNDERT STABIL)
# ==============================================================================

def render_teaser(audio, imgs, drop, hook, pdata, out_mp4, use_retention_hook=True):
    bpm, loops = 150.0, 4
    beat_dur = 60.0 / bpm
    bd = "{:.4f}".format(beat_dur)
    dur = "{:.4f}".format(loops * 4 * beat_dur)
    
    cfile = os.path.join(TEMP, "c_{}.txt".format(int(time.time() * 1000)))
    with open(cfile, "w", encoding="utf-8") as f:
        for _ in range(loops):
            for im in imgs:
                esc = im.replace("'", "'\\''")
                f.write("file '{}'\nduration {}\n".format(esc, bd))
        esc_last = imgs[-1].replace("'", "'\\''")
        f.write("file '{}'\n".format(esc_last))

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
        txt = (
            ",drawtext=text='{}':fontfile='{}':fontsize=68:fontcolor=white:"
            "box=1:boxcolor=black@0.9:boxborderw=20:x=(w-text_w)/2:"
            "y='520+8*lt(mod(t,{}),0.05)'".format(clean_hook, fpath, bd)
        )

    fg = (
        "[0:v]fps=30,scale=1120:1990:force_original_aspect_ratio=increase,"
        "crop=1080:1920:x='(in_w-out_w)/2':y='(in_h-out_h)/2+{}*lt(mod(t,{}),0.05)',"
        "format=yuv420p,{},"
        "eq=contrast='1.0+0.8*lt(mod(t,{}),0.05)':brightness='{}*lt(mod(t,{}),0.05)':enable='eq(mod(floor(t/{}),4),0)',"
        "colorchannelmixer=rr=1.35:gg=0.8:bb=0.9:enable='eq(mod(floor(t/{}),4),1)*lt(mod(t,{}),0.06)',"
        "negate=enable='eq(mod(floor(t/{}),4),2)*lt(mod(t,{}),{})',"
        "noise=alls=30:allf=t+u:enable='eq(mod(floor(t/{}),4),3)*lt(mod(t,{}),0.07)'{}[vout]"
    ).format(
        pdata["bounce"], bd, pdata["grade"],
        bd, pdata["flash"], bd, bd,
        bd, bd,
        bd, bd, pdata["inv"],
        bd, bd, txt
    )

    fade_out_time = float(dur) - 0.004
    base_audio_fade = "afade=t=in:st=0:d=0.004,afade=t=out:st={:.4f}:d=0.004".format(fade_out_time)
    
    if use_retention_hook:
        t_break_start = "{:.4f}".format(beat_dur)
        t_drop_start = "{:.4f}".format(beat_dur * 4)
        audio_filter = (
            "{},"
            "lowpass=f=450:enable='between(t,{},{})'"
        ).format(base_audio_fade, t_break_start, t_drop_start)
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

def run_job(style_key, variants, custom_hook, use_retention):
    STATUS["progress"] = 10
    STATUS["logs"] = ["[System] Starte optimierte Teaser-Pipeline..."]
    
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
    STATUS["logs"].append("[Audio] Verwende: " + os.path.basename(audio))
    STATUS["logs"].append("[Hookline] Text gesetzt: \"" + active_hook + "\"")
    if use_retention:
        STATUS["logs"].append("[Retention] Reverse-Build-up Hebel AKTIVIERT (Schock-Intro).")

    imgs = sorted(
        glob.glob(os.path.join(VAULT, "*.jpg")) +
        glob.glob(os.path.join(VAULT, "*.png")) +
        glob.glob(os.path.join(VAULT, "*.JPG")) +
        glob.glob(os.path.join(VAULT, "*.PNG"))
    )
    
    if len(imgs) < 4:
        STATUS["logs"].append("[Assets] Zu wenige lokale Bilder -> Lade Cloud-Artworks...")
        imgs = []
        for i in range(4):
            url = "https://image.pollinations.ai/prompt/dark%20techno%20rave%20flash%20aesthetic%209:16?width=1080&height=1920&nologo=true&seed={}".format(int(time.time()) + i)
            ipath = os.path.join(TEMP, "img_{}_{}.jpg".format(i, int(time.time())))
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as r, open(ipath, "wb") as f:
                    f.write(r.read())
                imgs.append(ipath)
            except Exception:
                pass

    if len(imgs) < 4:
        for i in range(4):
            fb = os.path.join(TEMP, "fb_{}.jpg".format(i))
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=1", "-frames:v", "1", fb],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            imgs.append(fb)

    drops = [2.30, 24.50, 48.20][:variants]
    STATUS["progress"] = 30
    res = []
    
    for idx, d in enumerate(drops):
        out_name = "teaser_{}_v{}.mp4".format(int(time.time()), idx + 1)
        out_path = os.path.join(EXPORT, out_name)
        STATUS["logs"].append("[FFmpeg] Rendere Teaser {}/{} (Drop bei {:.1f}s)...".format(idx + 1, len(drops), d))
        render_teaser(audio, imgs[:4], d, active_hook, pdata, out_path, use_retention)
        res.append({"filename": out_name, "filepath": out_path, "drop": "{}s".format(d)})
        STATUS["progress"] = int(30 + ((idx + 1) / len(drops)) * 65)

    STATUS["results"] = res
    STATUS["progress"] = 100
    STATUS["logs"].append("[Erfolg] Alle Teaser fertig gerendert!")
    os.system("afplay /System/Library/Sounds/Glass.aiff 2>/dev/null &")

# ==============================================================================
# 3. DAS COCKPIT (HTML & TABS)
# ==============================================================================

HTML = f"""<!DOCTYPE html><html class="dark"><head><meta charset="UTF-8"><title>Hard Techno Engine & Crate-Digger V{CURRENT_VERSION}</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-zinc-950 text-zinc-100 p-6 md:p-8 font-mono max-w-3xl mx-auto space-y-6">
  <div class="border-b border-zinc-800 pb-4 flex justify-between items-center">
    <div>
      <div class="flex items-center space-x-2">
        <h1 class="text-xl font-black text-red-500">HARD-TECHNO SUITE</h1>
        <span class="text-[11px] bg-red-950/70 text-red-400 border border-red-800/80 px-2 py-0.5 rounded font-bold">v{CURRENT_VERSION}</span>
      </div>
      <p class="text-[10px] text-zinc-500 uppercase tracking-widest">MacBook Air Edition • Crate-Digger & Video-Engine</p>
    </div>
    <div class="flex items-center space-x-2 text-xs">
      <button id="updBtn" onclick="checkUpdate()" class="px-3 py-1 bg-zinc-900 border border-zinc-700 hover:border-red-500 text-zinc-300 hover:text-white rounded transition flex items-center space-x-1">
        <span>🔄</span><span>Update suchen</span>
      </button>
      <button onclick="fetch('/api/folder?t=vault')" class="px-3 py-1 bg-zinc-800 hover:bg-zinc-700 rounded transition">Vault</button>
      <button onclick="fetch('/api/folder?t=export')" class="px-3 py-1 bg-zinc-800 hover:bg-zinc-700 rounded transition">Export</button>
    </div>
  </div>

  <div id="updBanner" class="hidden p-3 rounded text-xs flex justify-between items-center">
    <span id="updMsg"></span>
    <button onclick="installUpdate()" id="updInstBtn" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded font-bold transition">Jetzt installieren</button>
  </div>

  <!-- NAVIGATION TABS -->
  <div class="grid grid-cols-2 gap-2 bg-zinc-900 p-1 rounded border border-zinc-800 text-xs font-bold text-center">
    <button id="tabVideoBtn" onclick="switchTab('video')" class="py-2.5 rounded bg-red-600 text-white transition">🎬 1. VIDEO-TEASER ENGINE</button>
    <button id="tabCrateBtn" onclick="switchTab('crate')" class="py-2.5 rounded text-zinc-400 hover:text-white transition">🎧 2. CRATE-DIGGER & DENON</button>
  </div>

  <!-- TAB 1: VIDEO TEASERS -->
  <div id="tabVideo" class="space-y-4">
    <div class="space-y-1">
      <label class="text-xs text-zinc-400 block font-bold">1. Eigener Text-Hook (Optional)</label>
      <input type="text" id="hook" placeholder="z. B. POV: FIRST TIME VERKNIPT (Leer = Preset-Hook)" class="w-full bg-zinc-900 border border-zinc-700 p-2.5 rounded text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-red-500">
    </div>

    <div class="grid grid-cols-2 gap-4">
      <div>
        <label class="text-xs text-zinc-400 block mb-1 font-bold">2. Style-Preset</label>
        <select id="p" class="w-full bg-zinc-900 border border-zinc-700 p-2.5 rounded text-sm text-zinc-200">
          <option value="warehouse">Industrial Warehouse</option>
          <option value="acid">Acid 303 Tunnel</option>
          <option value="tribal">Y2K Cyber Tribal</option>
        </select>
      </div>
      <div>
        <label class="text-xs text-zinc-400 block mb-1 font-bold">3. Teaser-Anzahl</label>
        <select id="v" class="w-full bg-zinc-900 border border-zinc-700 p-2.5 rounded text-sm text-zinc-200">
          <option value="1">1 Teaser</option>
          <option value="3" selected>3 Teaser</option>
        </select>
      </div>
    </div>

    <div class="bg-zinc-900/60 p-3 rounded border border-zinc-800 flex items-center justify-between">
      <div>
        <div class="text-xs font-bold text-zinc-300">Reverse-Build-up (Anti-Swipe-Schock)</div>
        <div class="text-[11px] text-zinc-500">Kick bei 0.00s + Filter-Spannung stoppt sofortiges Abbrechen</div>
      </div>
      <input type="checkbox" id="retention" checked class="w-5 h-5 accent-red-600 cursor-pointer">
    </div>

    <button id="btn" onclick="startRender()" class="w-full py-4 bg-red-600 hover:bg-red-500 transition rounded font-black text-sm uppercase tracking-wider shadow-lg">Teaser jetzt rendern</button>

    <div class="bg-black p-4 rounded border border-zinc-800 space-y-2 text-xs">
      <div class="flex justify-between text-zinc-400 font-bold"><span>Status:</span><span id="ptxt" class="text-red-500">0%</span></div>
      <div class="bg-zinc-900 h-2 rounded overflow-hidden"><div id="pbar" class="bg-red-600 h-full w-0 transition-all duration-300"></div></div>
      <div id="logs" class="text-zinc-500 text-[11px] pt-2 max-h-32 overflow-y-auto space-y-0.5">Bereit.</div>
    </div>
    <div id="res" class="space-y-2"></div>
  </div>

  <!-- TAB 2: CRATE-DIGGER & DENON -->
  <div id="tabCrate" class="hidden space-y-4">
    <div class="space-y-1">
      <div class="flex justify-between items-center">
        <label class="text-xs text-zinc-400 font-bold">Tracklist hier einfügen (Plaintext aus Notizen / Rekordbox / SoundCloud):</label>
        <span class="text-[11px] text-zinc-500">Nutzt schnellen Mac-Spotlight-Index</span>
      </div>
      <textarea id="crateText" rows="6" placeholder="1. Nico Moreno - Purple Widow&#10;2. Klangkuenstler - Die Hölle kocht&#10;3. Alignment - Attack" class="w-full bg-zinc-900 border border-zinc-700 p-3 rounded text-xs text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-red-500"></textarea>
    </div>

    <div class="flex space-x-3">
      <button id="crateBtn" onclick="startCrateScan()" class="flex-1 py-3 bg-red-600 hover:bg-red-500 rounded font-black text-xs uppercase transition tracking-wider">
        🔍 Tracks auf dem Mac aufspüren
      </button>
      <button onclick="document.getElementById('crateText').value=''" class="px-4 py-3 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 rounded text-xs text-zinc-400">
        Leeren
      </button>
    </div>

    <!-- ERGEBNIS-BOX -->
    <div id="crateSummary" class="hidden bg-zinc-900/80 p-4 rounded border border-zinc-800 space-y-3">
      <div class="flex justify-between items-center text-xs">
        <div>
          <span class="text-zinc-400">Gefunden: </span>
          <span id="crateMatchRate" class="font-bold text-emerald-400">0 / 0</span>
        </div>
        <div class="space-x-2 flex items-center">
          <input type="text" id="plName" value="Denon_Gig_Playlist" class="bg-black border border-zinc-700 px-2 py-1 rounded text-xs text-zinc-200">
          <button onclick="exportM3U8()" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded font-bold transition text-xs">
            ⚡ Denon M3U8 Exportieren
          </button>
        </div>
      </div>
      <div id="crateItems" class="space-y-2 max-h-80 overflow-y-auto pt-2 border-t border-zinc-800 text-xs"></div>
    </div>
  </div>

<script>
function switchTab(t){{
  if(t==='video'){{
    document.getElementById('tabVideo').classList.remove('hidden');
    document.getElementById('tabCrate').classList.add('hidden');
    document.getElementById('tabVideoBtn').className='py-2.5 rounded bg-red-600 text-white transition';
    document.getElementById('tabCrateBtn').className='py-2.5 rounded text-zinc-400 hover:text-white transition';
  }} else {{
    document.getElementById('tabVideo').classList.add('hidden');
    document.getElementById('tabCrate').classList.remove('hidden');
    document.getElementById('tabCrateBtn').className='py-2.5 rounded bg-red-600 text-white transition';
    document.getElementById('tabVideoBtn').className='py-2.5 rounded text-zinc-400 hover:text-white transition';
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
      banner.className='bg-emerald-950/60 border border-emerald-700 text-emerald-300 p-3 rounded text-xs flex justify-between items-center';
      document.getElementById('updMsg').innerText=`Neues Update gefunden: v${{res.remote_version}} (Aktuell: v${{res.current_version}})`;
      banner.classList.remove('hidden');
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
    }} else {{
      document.getElementById('updMsg').innerText='Fehler: '+res.message;
      instBtn.disabled=false;
      instBtn.innerText='Wiederholen';
    }}
  }} catch(e){{
    setTimeout(()=>{{window.location.reload();}},3000);
  }}
}}

// TAB 1 RENDER
async function startRender(){{
  document.getElementById('btn').disabled=true;
  await fetch('/api/render',{{
    method:'POST',
    body:JSON.stringify({{
      p: document.getElementById('p').value,
      v: parseInt(document.getElementById('v').value),
      hook: document.getElementById('hook').value,
      retention: document.getElementById('retention').checked
    }})
  }});
  poll();
}}
async function poll(){{
  const d=await(await fetch('/api/status')).json();
  document.getElementById('pbar').style.width=d.progress+'%';
  document.getElementById('ptxt').innerText=d.progress+'%';
  document.getElementById('logs').innerHTML=d.logs.map(l=>'<div>'+l+'</div>').join('');
  if(d.results&&d.results.length>0){{
    document.getElementById('res').innerHTML=d.results.map(r=>`
      <div class="bg-zinc-900 p-3 rounded border border-zinc-800 flex justify-between items-center text-xs">
        <div>
          <div class="font-bold text-zinc-200">${{r.filename}}</div>
          <div class="text-[11px] text-zinc-500">Drop bei ${{r.drop}}</div>
        </div>
        <div class="space-x-2">
          <button onclick="fetch('/api/open?p='+encodeURIComponent('${{r.filepath}}'))" class="px-3 py-1 bg-red-600 hover:bg-red-500 rounded text-white font-bold transition">In QuickTime</button>
          <button onclick="fetch('/api/reveal?p='+encodeURIComponent('${{r.filepath}}'))" class="px-3 py-1 bg-zinc-800 hover:bg-zinc-700 rounded text-zinc-300 transition">Im Finder</button>
        </div>
      </div>`).join('');
  }}
  if(d.progress===100||(d.progress===0&&d.logs.some(l=>l.includes('FEHLER')))){{document.getElementById('btn').disabled=false;}}else{{setTimeout(poll,700);}}
}}

// TAB 2 CRATE SCAN
async function startCrateScan(){{
  const text=document.getElementById('crateText').value;
  if(!text.trim())return alert('Bitte erst eine Tracklist einfügen!');
  const b=document.getElementById('crateBtn');
  b.disabled=true;
  b.innerText='⏳ Scanne SSD & USB-Laufwerke via Spotlight...';
  try{{
    const res=await(await fetch('/api/crate_scan',{{method:'POST',body:JSON.stringify({{text}})}})).json();
    document.getElementById('crateSummary').classList.remove('hidden');
    document.getElementById('crateMatchRate').innerText=`${{res.found_count}} von ${{res.total_queried}} gefunden (${{Math.round(res.found_count/res.total_queried*100)}}%)`;
    document.getElementById('crateItems').innerHTML=res.items.map(it=>`
      <div class="p-2.5 rounded ${{it.found?'bg-zinc-950 border border-zinc-800':'bg-red-950/20 border border-red-900/40'}} flex justify-between items-center">
        <div>
          <div class="font-bold ${{it.found?'text-zinc-200':'text-red-400'}}">${{it.found?'✅':'❌'}} ${{it.query}}</div>
          ${{it.found?`<div class="text-[11px] text-zinc-500 truncate max-w-md">${{it.path}}</div>`:`<div class="text-[11px] text-red-500">Datei nicht auf dem Mac gefunden</div>`}}
        </div>
        <div class="flex items-center space-x-2">
          <span class="px-2 py-0.5 rounded text-[10px] font-bold ${{it.found?'bg-emerald-950 text-emerald-400 border border-emerald-800':'bg-zinc-800 text-zinc-500'}}">${{it.format}}</span>
          ${{it.found?`<button onclick="copyToVault('${{encodeURIComponent(it.path)}}')" class="px-2 py-1 bg-zinc-800 hover:bg-red-600 rounded text-[11px] text-zinc-300 hover:text-white transition">In Teaser-Vault</button>`:''}}
        </div>
      </div>
    `).join('');
  }}catch(e){{
    alert('Fehler beim Scan: '+e);
  }}
  b.disabled=false;
  b.innerText='🔍 Tracks auf dem Mac aufspüren';
}}

async function exportM3U8(){{
  const name=document.getElementById('plName').value;
  const res=await(await fetch('/api/crate_export',{{method:'POST',body:JSON.stringify({{name}})}})).json();
  if(res.status==='ok'){{
    alert(`✓ Playlist gespeichert: ${{res.filename}}\\nIm Finder markiert – einfach in Denon Engine DJ ziehen!`);
  }} else {{
    alert('Fehler: '+res.message);
  }}
}}

async function copyToVault(pathEnc){{
  const res=await(await fetch('/api/copy_vault?path='+pathEnc)).json();
  alert(res.message);
}}
</script></body></html>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
        
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
                res = {"status": "ok", "message": f"✓ '{os.path.basename(f)}' in input_vault kopiert!"}
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
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        d = json.loads(body)
        
        if self.path == "/api/render":
            threading.Thread(
                target=run_job,
                args=(
                    d.get("p", "warehouse"),
                    d.get("v", 3),
                    d.get("hook", ""),
                    d.get("retention", True)
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
    print("\n[OK] Cockpit V5.3 aktiv unter: " + url)
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == "__main__":
    main()