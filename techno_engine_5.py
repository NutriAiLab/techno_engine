cat << 'EOF' > "$HOME/Desktop/TechnoEngine_V5/techno_engine_v5.py"
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, glob, json, time, shutil, subprocess, threading, webbrowser
import urllib.request, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + os.environ.get("PATH", "")
BASE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.join(BASE, "input_vault")
EXPORT = os.path.join(BASE, "export_teasers")
STYLES = os.path.join(BASE, "styles")
TEMP = os.path.join(BASE, ".cache_engine")

for d in [VAULT, EXPORT, STYLES, TEMP]:
    os.makedirs(d, exist_ok=True)

OLD = os.path.expanduser("~/Desktop/160_BPM_Teaser")
if os.path.exists(OLD):
    for f in glob.glob(os.path.join(OLD, "*.*")):
        dst = os.path.join(VAULT, os.path.basename(f))
        if not os.path.exists(dst):
            try:
                shutil.copy2(f, dst)
            except Exception:
                pass

STATUS = {"progress": 0, "logs": [], "results": []}

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

HTML = """<!DOCTYPE html><html class="dark"><head><meta charset="UTF-8"><title>Techno Engine V5.1</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-zinc-950 text-zinc-100 p-8 font-mono max-w-2xl mx-auto space-y-6">
  <div class="border-b border-zinc-800 pb-4 flex justify-between items-center">
    <div>
      <h1 class="text-xl font-black text-red-500">HARD-TECHNO ENGINE V5.1</h1>
      <p class="text-[10px] text-zinc-500 uppercase tracking-widest">MacBook Air Edition • Native Performance</p>
    </div>
    <div class="space-x-3 text-xs">
      <button onclick="fetch('/api/folder?t=vault')" class="px-3 py-1 bg-zinc-800 hover:bg-zinc-700 rounded transition">Input-Vault</button>
      <button onclick="fetch('/api/folder?t=export')" class="px-3 py-1 bg-zinc-800 hover:bg-zinc-700 rounded transition">Export-Ordner</button>
    </div>
  </div>

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
    <input type="checkbox" id="retention" checked class="w-5 h-5 accent-red-600 rounded cursor-pointer">
  </div>

  <button id="btn" onclick="start()" class="w-full py-4 bg-red-600 hover:bg-red-500 transition rounded font-black text-sm uppercase tracking-wider shadow-lg">Teaser jetzt rendern</button>

  <div class="bg-black p-4 rounded border border-zinc-800 space-y-2 text-xs">
    <div class="flex justify-between text-zinc-400 font-bold"><span>Status:</span><span id="ptxt" class="text-red-500">0%</span></div>
    <div class="bg-zinc-900 h-2 rounded overflow-hidden"><div id="pbar" class="bg-red-600 h-full w-0 transition-all duration-300"></div></div>
    <div id="logs" class="text-zinc-500 text-[11px] pt-2 max-h-32 overflow-y-auto space-y-0.5">Bereit.</div>
  </div>

  <div id="res" class="space-y-2"></div>
<script>
async function start(){
  document.getElementById('btn').disabled=true;
  await fetch('/api/render',{
    method:'POST',
    body:JSON.stringify({
      p: document.getElementById('p').value,
      v: parseInt(document.getElementById('v').value),
      hook: document.getElementById('hook').value,
      retention: document.getElementById('retention').checked
    })
  });
  poll();
}
async function poll(){
  const d=await(await fetch('/api/status')).json();
  document.getElementById('pbar').style.width=d.progress+'%';
  document.getElementById('ptxt').innerText=d.progress+'%';
  document.getElementById('logs').innerHTML=d.logs.map(l=>'<div>'+l+'</div>').join('');
  if(d.results&&d.results.length>0){
    document.getElementById('res').innerHTML=d.results.map(r=>`
      <div class="bg-zinc-900 p-3 rounded border border-zinc-800 flex justify-between items-center text-xs">
        <div>
          <div class="font-bold text-zinc-200">${r.filename}</div>
          <div class="text-[11px] text-zinc-500">Drop bei ${r.drop}</div>
        </div>
        <div class="space-x-2">
          <button onclick="fetch('/api/open?p='+encodeURIComponent('${r.filepath}'))" class="px-3 py-1 bg-red-600 hover:bg-red-500 rounded text-white font-bold transition">In QuickTime</button>
          <button onclick="fetch('/api/reveal?p='+encodeURIComponent('${r.filepath}'))" class="px-3 py-1 bg-zinc-800 hover:bg-zinc-700 rounded text-zinc-300 transition">Im Finder</button>
        </div>
      </div>`).join('');
  }
  if(d.progress===100||(d.progress===0&&d.logs.some(l=>l.includes('FEHLER')))){document.getElementById('btn').disabled=false;}else{setTimeout(poll,700);}
}
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
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/render":
            length = int(self.headers.get("Content-Length", 0))
            d = json.loads(self.rfile.read(length).decode("utf-8"))
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

def main():
    server = HTTPServer(("127.0.0.1", 8505), H)
    url = "http://127.0.0.1:8505"
    print("\n[OK] Cockpit V5.1 aktiv unter: " + url)
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == "__main__":
    main()
EOF
kill $(lsof -t -i:8505) 2>/dev/null || true
echo "FERTIG! V5.1 ist scharf geschaltet."
