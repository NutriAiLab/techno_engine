#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TECH DUDE // SUITE V6.5.0 (Master Release)
- Reaktiviert: 1-Klick GitHub Live-Updater mit autonomem Server-Neustart
- Gesichert: Gemini API-Key überlebt Updates in ~/.techdude_config.json und lädt automatisch
- Gefixt: Interaktives Track-Dropdown (blauer Bereich) zum schnellen Wechseln von Songs
- Gefixt: Cinema-Master EBU R128 + Deband ohne Crash
- Erweitert: Säule 3 mit nativer Ordner-Auswahl (AppleScript) & 3 Modi (Viren, Duplikate, ID3-Edit)
- Erweitert: 8 Hard-Techno Style Presets
"""

import os, sys, glob, json, time, math, struct, shutil, subprocess, threading, re, hashlib
import urllib.request, urllib.parse, urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

APP_NAME = "TECH DUDE"
CURRENT_VERSION = "6.5.0"
GITHUB_RAW_URL = "https://raw.githubusercontent.com/NutriAiLab/techno_engine/main/techno_engine_v5.py"

# Homebrew- und System-Pfade für FFmpeg / FFprobe priorisieren
os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + os.environ.get("PATH", "")
BASE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.join(BASE, "input_vault")
EXPORT = os.path.join(BASE, "export_teasers")
STYLES = os.path.join(BASE, "styles")
TEMP = os.path.join(BASE, ".cache_engine")
CONFIG_FILE = os.path.expanduser("~/.techdude_config.json")

for d in [VAULT, EXPORT, STYLES, TEMP]:
    os.makedirs(d, exist_ok=True)

STATUS = {"progress": 0, "logs": [], "results": []}
CRATE_RESULTS = {"total_queried": 0, "found_count": 0, "missing_count": 0, "items": [], "playlist_path": ""}
CLEANER_RESULTS = {"folder": "", "total_scanned": 0, "threats_found": 0, "items": [], "duplicates": []}
SHARED_STATE = {
    "active_folder": os.path.expanduser("~/Downloads"),
    "last_alert": "",
    "active_track_file": ""
}

# In-Memory Cache verhindert wiederholte FFmpeg-Aufrufe und schützt die CPU
TRACK_CACHE = {
    "path": "",
    "mtime": 0,
    "data": None,
    "processing": False
}

BUNKER_CACHE = {
    "hooks": {
        "warehouse": ["UNRELEASED ID?", "BERLIN BASEMENT PRESSURE", "160 BPM INDUSTRIAL FORCE", "DROPPED AT 04:30 AM", "RATE THIS DROP 1-10", "TESTING THE CLUB PA", "INDUSTRIAL WEAPON", "KEEP LOCKED OR DROP?", "RAW CONCRETE SOUND"],
        "acid": ["ACID THERAPY 160BPM", "303 INVASION", "ACID PRESSURE PEAK", "HYPNOTIC 303 MADNESS", "TB-303 AT MAXIMUM DRIVE", "PURE ANALOG RESISTANCE", "RAW ACID TOOL", "ACID VORTEX"],
        "tribal": ["POV: FIRST TIME VERKNIPT", "NEO-RAVE ENERGY 162 BPM", "DUTCH RAVE ESCALATION", "FAST & HEAVY TRIBAL", "CYBER RAVE VIBE", "TELETECH READY ID", "RAW PERCUSSION WEAPON", "GROOVE MEETS VIOLENCE"],
        "schranz": ["165 BPM SCHRANZ PRESSURE", "FRANKFURT SOUND REBORN", "MAXIMUM DISTORTION KICK", "PURE INDUSTRIAL SCHRANZ", "BASSFACE GUARANTEE", "NO RETREAT 165BPM"],
        "hardgroove": ["PURE GROOVE WEAPON", "TIGHT ROLLING 909", "SPANISH HARDGROOVE TOOL", "NON-STOP PRESSURE", "RAW LATIN PERCUSSION"],
        "berlin": ["BERLIN DARKROOM WEAPON", "RAW CONCRETE SOUND", "BASEMENT ACID FORCE", "SWEAT ON CONCRETE", "NO LIGHT ONLY SOUND"],
        "neorave": ["NEO RAVE SPEED 164BPM", "CYBER TRANCE ENERGY", "HIGH OCTANE RAVE", "FAST & FURIOUS DROP", "EUPHORIC ACID ESCALATION"],
        "industrial": ["INDUSTRIAL HAMMER", "METALLIC PERCUSSION", "HEAVY FACTORY KICK", "DISTORTION PROTOCOL", "RAW DRIVING VIOLENCE"],
        "general": ["UNRELEASED ID?", "DROP OR KEEP LOCKED?", "TESTING CLUB SOUNDSYSTEM", "PURE BASEMENT SOUND", "FIRST TIME PLAYED LIVE", "HARD TECHNO WEAPON"]
    },
    "visual_prompts": [
        "raw industrial basement rave, 35mm flash photography, motion blur, harsh shadows, dark concrete walls, strobe light beams, 160bpm techno crowd",
        "berlin underground techno club, red strobe lighting, silhouettes dancing, smoke machine haze, concrete pillars, analog film grain, high contrast",
        "cyber rave aesthetic, laser grid tunnels, dark aesthetic, industrial warehouse, green laser cuts through fog, 90s analog photo style",
        "strobe flash moment, monochrome hard techno crowd, sweaty dancing silhouettes, warehouse interior, 35mm lens blur, authentic underground"
    ]
}

def load_user_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception: pass
    return {}

def save_user_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        return True
    except Exception: return False

def get_gemini_api_key():
    return load_user_config().get("gemini_api_key", "").strip()

def call_gemini_api(prompt_text, system_instruction=None, timeout=2.8):
    key = get_gemini_api_key()
    if not key: return None
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
    parts = [{"text": prompt_text}]
    payload = {"contents": [{"parts": parts}], "generationConfig": {"temperature": 0.65, "maxOutputTokens": 400}}
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_res = json.loads(resp.read().decode("utf-8"))
            candidates = raw_res.get("candidates", [])
            if candidates:
                parts_out = candidates[0].get("content", {}).get("parts", [])
                if parts_out: return parts_out[0].get("text", "").strip()
    except Exception:
        # Robuster Fallback auf Gemini 1.5 Flash
        try:
            url_15 = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
            req2 = urllib.request.Request(url_15, data=data_bytes, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req2, timeout=timeout) as resp2:
                raw_res2 = json.loads(resp2.read().decode("utf-8"))
                candidates = raw_res2.get("candidates", [])
                if candidates:
                    parts_out = candidates[0].get("content", {}).get("parts", [])
                    if parts_out: return parts_out[0].get("text", "").strip()
        except Exception: pass
    return None

def generate_viral_hooks(track_name="", bpm=155.0, style_key="warehouse"):
    sys_inst = "Du bist ein Hard-Techno Creative Director. Gib exakt 3 extrem kurze, virale Hooks für TikTok/Reels Teaser zurück. Underground-Slang, GROSSBUCHSTABEN, 4-6 Wörter. Ausschließlich valides JSON-Array aus 3 Strings, z.B. [\"HOOK 1\", \"HOOK 2\", \"HOOK 3\"]."
    prompt = f"Track: '{track_name}', Tempo: {bpm:.0f} BPM, Stil: {style_key}. Generiere 3 virale Hooks."
    ai_raw = call_gemini_api(prompt, system_instruction=sys_inst)
    if ai_raw:
        try:
            m = re.search(r'\[\s*"[\s\S]*?"\s*\]', ai_raw)
            if m:
                hooks = json.loads(m.group(0))
                if isinstance(hooks, list) and len(hooks) >= 1:
                    clean_hooks = [str(h).strip().upper() for h in hooks[:3] if str(h).strip()]
                    if clean_hooks: return clean_hooks, "cloud"
        except Exception: pass
    import random
    bunker_pool = BUNKER_CACHE["hooks"].get(style_key, BUNKER_CACHE["hooks"]["general"])
    return random.sample(bunker_pool, min(3, len(bunker_pool))), "bunker"

def parse_messy_tracklist_with_ai(raw_text):
    if not raw_text.strip(): return [], "bunker"
    sys_inst = "Du bist ein DJ-Bibliothekar. Extrahiere alle Musiktracks sauber aus dem Text. Entferne Emojis, Nummern und Tags wie [FREE DL]. Strikt als 'Artist - Title'. Gib ausschließlich ein JSON-Array aus Strings zurück."
    ai_res = call_gemini_api(raw_text, system_instruction=sys_inst)
    if ai_res:
        try:
            m = re.search(r'\[\s*"[\s\S]*?"\s*\]', ai_res)
            if m:
                parsed = json.loads(m.group(0))
                if isinstance(parsed, list) and len(parsed) > 0:
                    return [str(p).strip() for p in parsed if str(p).strip()], "cloud"
        except Exception: pass
    cleaned = [clean_track_query(l) for l in raw_text.splitlines() if clean_track_query(l)]
    return cleaned, "bunker"

FORMATS = {
    "9:16": {"w": 1080, "h": 1920, "text_y": 520, "label": "9:16 Story/Reels"},
    "1:1":  {"w": 1080, "h": 1080, "text_y": 820, "label": "1:1 Vinyl Feed"},
    "16:9": {"w": 1920, "h": 1080, "text_y": 760, "label": "16:9 Cinema"}
}

PRESETS = {
    "warehouse": {"name": "Industrial Warehouse", "grade": "eq=contrast=1.35:saturation=0.20", "bounce": 24, "flash": "0.45", "inv": 0.030, "hook": "UNRELEASED ID?"},
    "acid": {"name": "Acid 303 Tunnel", "grade": "colorchannelmixer=rr=0.4:gg=1.3:bb=0.6", "bounce": 28, "flash": "0.35", "inv": 0.040, "hook": "ACID THERAPY 160BPM"},
    "tribal": {"name": "Y2K Cyber Tribal", "grade": "eq=contrast=1.40:saturation=1.15", "bounce": 26, "flash": "0.50", "inv": 0.032, "hook": "POV: FIRST TIME VERKNIPT"},
    "schranz": {"name": "Schranz Distortion", "grade": "colorchannelmixer=rr=1.4:gg=0.2:bb=0.2,eq=contrast=1.5:saturation=1.2", "bounce": 32, "flash": "0.60", "inv": 0.050, "hook": "165 BPM PRESSURE"},
    "hardgroove": {"name": "Hardgroove Minimal", "grade": "colorchannelmixer=rr=0.3:gg=0.3:bb=0.3,eq=contrast=1.2", "bounce": 14, "flash": "0.20", "inv": 0.0, "hook": "PURE GROOVE"},
    "berlin": {"name": "Berlin Darkroom", "grade": "colorchannelmixer=rr=0.2:gg=0.4:bb=0.6,eq=contrast=1.6:brightness=-0.05", "bounce": 18, "flash": "0.30", "inv": 0.020, "hook": "BASEMENT VIBES"},
    "neorave": {"name": "Neo-Rave Speed", "grade": "colorchannelmixer=rr=1.3:gg=0.8:bb=1.4,eq=contrast=1.4:saturation=1.3", "bounce": 30, "flash": "0.55", "inv": 0.045, "hook": "NEO-RAVE 164 BPM"},
    "industrial": {"name": "Raw Concrete Industrial", "grade": "eq=contrast=1.50:saturation=0.0:brightness=-0.02", "bounce": 26, "flash": "0.65", "inv": 0.060, "hook": "RAW CONCRETE WEAPON"}
}

SUSPICIOUS_EXTENSIONS = {".app", ".pkg", ".dmg", ".command", ".sh", ".scpt", ".exe", ".bat", ".vbs", ".js", ".scr"}
MAGIC_EXECUTABLE_SIGNATURES = [
    (b"\xcf\xfa\xed\xfe", "Mach-O 64-bit Binary"),
    (b"\xce\xfa\xed\xfe", "Mach-O 32-bit Binary"),
    (b"\xca\xfe\xba\xbe", "Mach-O Universal"),
    (b"MZ", "Windows PE Executable"),
    (b"\x7fELF", "Linux ELF Binary"),
    (b"#!", "Unix Shell Script")
]
AUDIO_EXTENSIONS = {".wav", ".mp3", ".aiff", ".aif", ".flac", ".m4a"}

def calculate_sha256(filepath):
    h = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(65536): h.update(chunk)
        return h.hexdigest()
    except Exception: return ""

def inspect_file_security(filepath):
    filename = os.path.basename(filepath)
    lower_fn = filename.lower()
    ext = os.path.splitext(lower_fn)[1]
    
    for audio_ext in AUDIO_EXTENSIONS:
        for susp in SUSPICIOUS_EXTENSIONS:
            if f"{audio_ext}{susp}" in lower_fn or f"{susp}{audio_ext}" in lower_fn:
                return {"safe": False, "threat_type": "DOUBLE_EXTENSION", "message": f"🚨 Doppel-Endung erkannt: {susp}", "quarantine": True}

    if ext in AUDIO_EXTENSIONS:
        try:
            st = os.stat(filepath)
            if st.st_mode & 0o111:
                return {"safe": False, "threat_type": "EXECUTABLE_BIT_SET", "message": "🚨 Audio besitzt ausführbare Rechte (+x)", "quarantine": True}
        except Exception: pass
        try:
            with open(filepath, "rb") as f:
                header = f.read(16)
                for sig, desc in MAGIC_EXECUTABLE_SIGNATURES:
                    if header.startswith(sig):
                        return {"safe": False, "threat_type": "SPOOFED_BINARY", "message": f"🚨 Schadcode getarnt als Audio ({desc})", "quarantine": True}
        except Exception as e: return {"safe": False, "threat_type": "READ_ERROR", "message": str(e), "quarantine": False}

    return {"safe": True, "threat_type": "CLEAN", "message": "🟢 Geprüft & Sicher (Natives Audio)", "has_quarantine": False, "sha256": calculate_sha256(filepath)}

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
    
    fname = os.path.basename(audio_path)
    detected_bpm = 155.0
    bpm_match = re.search(r'(\b1[3-7]\d)\s*(?:bpm|\b)', fname, re.IGNORECASE)
    if bpm_match:
        try: detected_bpm = float(bpm_match.group(1))
        except Exception: pass
            
    return {"duration_sec": dur_sec, "duration_str": time_str, "filename": fname, "detected_bpm": detected_bpm}

def extract_waveform_envelope(audio_path, num_points=100):
    cmd = ["ffmpeg", "-v", "error", "-i", audio_path, "-vn", "-ac", "1", "-ar", "200", "-f", "f32le", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        raw_data, _ = proc.communicate(timeout=6)
        if not raw_data or len(raw_data) < num_points * 4: return [0.2] * num_points
        num_floats = len(raw_data) // 4
        samples = struct.unpack(f"{num_floats}f", raw_data[:num_floats * 4])
        step = max(1, num_floats // num_points)
        peaks = []
        for i in range(num_points):
            chunk = samples[i * step : (i + 1) * step]
            if chunk:
                rms = math.sqrt(sum(s * s for s in chunk) / len(chunk))
                peaks.append(rms)
            else:
                peaks.append(0.05)
        max_val = max(peaks) if peaks and max(peaks) > 0 else 1.0
        return [round(min(1.0, (p / max_val) * 1.15), 3) for p in peaks]
    except Exception:
        proc.kill()
        proc.wait()
        return [0.15] * num_points

def find_loudest_drop(audio_path):
    info = analyze_track_details(audio_path)
    total_dur = info["duration_sec"]
    cmd = ["ffmpeg", "-v", "error", "-i", audio_path, "-vn", "-ac", "1", "-ar", "100", "-f", "f32le", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        raw_data, _ = proc.communicate(timeout=8)
        if not raw_data or len(raw_data) < 400: return 2.30
        num_samples = len(raw_data) // 4
        samples = struct.unpack(f"{num_samples}f", raw_data[:num_samples * 4])
        block_size = 50
        num_blocks = num_samples // block_size
        if num_blocks < 8: return 2.30
        energies = []
        for b in range(num_blocks):
            chunk = samples[b * block_size : (b + 1) * block_size]
            rms = math.sqrt(sum(s * s for s in chunk) / len(chunk))
            energies.append(rms)
        start_idx = 8
        if len(energies) <= start_idx: return 2.30
        end_idx = max(start_idx + 1, int(len(energies) * 0.88))
        best_time = 2.30
        max_jump = -1.0
        for i in range(start_idx, end_idx):
            prev_avg = sum(energies[max(0, i - 4) : i]) / 4.0
            curr_energy = energies[i]
            jump = curr_energy - prev_avg
            if jump > max_jump and curr_energy > 0.12:
                max_jump = jump
                best_time = round(i * 0.5, 2)
        if max_jump <= 0.04:
            max_e = max(energies) if energies else 1.0
            for i in range(start_idx, end_idx):
                if energies[i] >= max_e * 0.75:
                    best_time = round(i * 0.5, 2)
                    break
        return max(1.50, min(best_time, total_dur - 8.0))
    except Exception:
        proc.kill()
        proc.wait()
        return 2.30

def measure_ebur128_pass1(audio, drop, dur):
    cmd = ["ffmpeg", "-y", "-ss", str(drop), "-t", str(dur), "-i", audio, "-af", "loudnorm=I=-14.0:LRA=7.0:TP=-1.0:print_format=json", "-f", "null", "-"]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
        stderr_txt = proc.stderr
        m = re.search(r'\{[\s\S]*?"input_i"[\s\S]*?\}', stderr_txt)
        if m: return json.loads(m.group(0))
    except Exception: pass
    return None

def render_teaser(audio, imgs, drop, hook, pdata, out_mp4, use_retention=True, fmt_key="9:16", beats=16, bpm=155.0, render_mode="turbo"):
    if not imgs: return
    bpm = max(130.0, min(175.0, float(bpm)))
    beat_dur = 60.0 / bpm
    bd = f"{beat_dur:.4f}"
    loops = max(1, beats // 4)
    dur = f"{(loops * 4 * beat_dur):.4f}"
    
    fmt = FORMATS.get(fmt_key, FORMATS["9:16"])
    target_w, target_h, safe_y = fmt["w"], fmt["h"], fmt["text_y"]

    cfile = os.path.join(TEMP, f"c_{int(time.time() * 1000)}.txt")
    with open(cfile, "w", encoding="utf-8") as f:
        for _ in range(loops):
            for im in imgs:
                f.write(f"file '{im}'\nduration {bd}\n")
        f.write(f"file '{imgs[-1]}'\n")

    fpath = None
    for fp in ["/System/Library/Fonts/Supplemental/Impact.ttf", "/System/Library/Fonts/Supplemental/Arial Black.ttf", "/Library/Fonts/Arial.ttf"]:
        if os.path.exists(fp):
            fpath = fp; break

    hook_file = os.path.join(TEMP, f"hook_{int(time.time() * 1000)}.txt")
    with open(hook_file, "w", encoding="utf-8") as hf: hf.write(hook.strip() or pdata["hook"])

    txt = ""
    if fpath:
        font_sz = 68 if target_h >= 1920 else 52
        esc_hfile = hook_file.replace(":", "\\:").replace("'", "\\'")
        txt = f",drawtext=textfile='{esc_hfile}':fontfile='{fpath}':fontsize={font_sz}:fontcolor=white:box=1:boxcolor=black@0.90:boxborderw=18:x=(w-text_w)/2:y='{safe_y}+8*lt(mod(t,{bd}),0.05)'"

    scale_w, scale_h = int(target_w * 1.05), int(target_h * 1.05)
    fade_out_time = float(dur) - 0.004
    base_audio_fade = f"afade=t=in:st=0:d=0.004,afade=t=out:st={fade_out_time:.4f}:d=0.004"
    retention_filter = f",lowpass=f=450:enable='between(t,{beat_dur:.4f},{(beat_dur * 4):.4f})'" if use_retention else ""

    if render_mode == "cinema":
        pass1_data = measure_ebur128_pass1(audio, drop, dur)
        if pass1_data:
            loud_norm = f",loudnorm=I=-14.0:LRA=7.0:TP=-1.0:measured_I={pass1_data.get('input_i', '-14.0')}:measured_TP={pass1_data.get('input_tp', '-1.0')}:measured_LRA={pass1_data.get('input_lra', '7.0')}:linear=true"
        else:
            loud_norm = ",loudnorm=I=-14.0:LRA=7.0:TP=-1.0:linear=true"

        audio_filter = f"{base_audio_fade}{retention_filter}{loud_norm}"
        # Robustes Debanding und Phosphor Halation ohne ungültige Flags
        fg = (
            f"[0:v]fps=30,scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,"
            f"crop={target_w}:{target_h}:x='(in_w-out_w)/2':y='(in_h-out_h)/2+{pdata['bounce']}*lt(mod(t,{bd}),0.05)',"
            f"format=yuv420p,deband=1:64:16:0,{pdata['grade']},"
            f"split=2[raw_base][glow_src];"
            f"[glow_src]gblur=sigma=12:steps=2,colorchannelmixer=rr=1.15:gg=0.25:bb=0.25[glow_layer];"
            f"[raw_base][glow_layer]blend=all_mode=addition:all_opacity=0.30,"
            f"eq=contrast='1.0+0.8*lt(mod(t,{bd}),0.05)':brightness='{pdata['flash']}*lt(mod(t,{bd}),0.05)':enable='eq(mod(floor(t/{bd}),4),0)',"
            f"colorchannelmixer=rr=1.35:gg=0.8:bb=0.9:enable='eq(mod(floor(t/{bd}),4),1)*lt(mod(t,{bd}),0.06)',"
            f"negate=enable='eq(mod(floor(t/{bd}),4),2)*lt(mod(t,{bd}),{pdata['inv']})',"
            f"noise=alls=20:allf=t+u:enable='eq(mod(floor(t/{bd}),4),3)*lt(mod(t,{bd}),0.07)'{txt}[vout]"
        )
        video_codec_flags = ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p"]
    else:
        audio_filter = f"{base_audio_fade}{retention_filter}"
        fg = (
            f"[0:v]fps=30,scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,"
            f"crop={target_w}:{target_h}:x='(in_w-out_w)/2':y='(in_h-out_h)/2+{pdata['bounce']}*lt(mod(t,{bd}),0.05)',"
            f"format=yuv420p,{pdata['grade']},"
            f"eq=contrast='1.0+0.8*lt(mod(t,{bd}),0.05)':brightness='{pdata['flash']}*lt(mod(t,{bd}),0.05)':enable='eq(mod(floor(t/{bd}),4),0)',"
            f"colorchannelmixer=rr=1.35:gg=0.8:bb=0.9:enable='eq(mod(floor(t/{bd}),4),1)*lt(mod(t,{bd}),0.06)',"
            f"negate=enable='eq(mod(floor(t/{bd}),4),2)*lt(mod(t,{bd}),{pdata['inv']})',"
            f"noise=alls=30:allf=t+u:enable='eq(mod(floor(t/{bd}),4),3)*lt(mod(t,{bd}),0.07)'{txt}[vout]"
        )
        video_codec_flags = ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", cfile, "-ss", str(drop), "-i", audio, "-t", dur,
        "-filter_complex", fg, "-map", "[vout]", "-map", "1:a", "-af", audio_filter
    ] + video_codec_flags + ["-c:a", "aac", "-b:a", "320k", "-ar", "44100", "-metadata", "comment=Rendered via TECH DUDE", out_mp4]

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=240)
        if proc.returncode != 0:
            err_lines = proc.stderr.strip().split('\n')
            relevant_err = " | ".join(err_lines[-3:]) if err_lines else "FFmpeg Unbekannter Fehler"
            STATUS["logs"].append(f"❌ [FFmpeg Crash] {relevant_err}")
            STATUS["progress"] = 0
    except subprocess.TimeoutExpired:
        STATUS["logs"].append("❌ [FFmpeg Fehler] Timeout überschritten.")
        STATUS["progress"] = 0
    except Exception as e:
        STATUS["logs"].append(f"❌ [System Fehler] {str(e)}")
        STATUS["progress"] = 0

def run_job(style_key, variants, custom_hook, use_retention, fmt_key="9:16", beats=16, custom_drop=None, custom_bpm=155.0, render_mode="turbo"):
    STATUS["progress"] = 10
    mode_label = "💎 CINEMA-MASTER (EBU R128)" if render_mode == "cinema" else "⚡ TURBO-DRAFT"
    STATUS["logs"] = [f"[{APP_NAME}] Starte Render im Modus: {mode_label} ({fmt_key} @ {custom_bpm:.1f} BPM)..."]
    
    auds = sorted(glob.glob(os.path.join(VAULT, "*.mp3")) + glob.glob(os.path.join(VAULT, "*.wav")) + glob.glob(os.path.join(VAULT, "*.m4a")) + glob.glob(os.path.join(VAULT, "*.aiff")))
    if not auds:
        STATUS["logs"].append("❌ [FEHLER] Kein Audio im 'input_vault' gefunden!")
        STATUS["progress"] = 0
        return
        
    audio = SHARED_STATE.get("active_track_file", "")
    if not audio or audio not in auds:
        audio = auds[0]
        
    pdata = PRESETS.get(style_key, PRESETS["warehouse"])
    active_hook = custom_hook.strip() if custom_hook and custom_hook.strip() else pdata["hook"]
    
    STATUS["logs"].append(f"[Audio] Master: {os.path.basename(audio)}")
    STATUS["logs"].append(f"[Timing] Tempo: {custom_bpm:.1f} BPM | Hook: \"{active_hook}\"")

    imgs = sorted(glob.glob(os.path.join(VAULT, "*.jpg")) + glob.glob(os.path.join(VAULT, "*.png")) + glob.glob(os.path.join(VAULT, "*.JPG")) + glob.glob(os.path.join(VAULT, "*.PNG")))
    fmt = FORMATS.get(fmt_key, FORMATS["9:16"])
    
    if len(imgs) < 4:
        STATUS["logs"].append(f"[Visuals] Generiere Club-Frames ({fmt_key})...")
        imgs = []
        for i in range(4):
            prompt_idx = i % len(BUNKER_CACHE["visual_prompts"])
            cur_prompt = urllib.parse.quote(BUNKER_CACHE["visual_prompts"][prompt_idx])
            url = f"https://image.pollinations.ai/prompt/{cur_prompt}?width={fmt['w']}&height={fmt['h']}&nologo=true&seed={int(time.time()) + i}"
            ipath = os.path.join(TEMP, f"img_{i}_{int(time.time())}.jpg")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=6) as r, open(ipath, "wb") as f: f.write(r.read())
                imgs.append(ipath)
            except Exception: pass

    if len(imgs) < 4:
        for i in range(4):
            fb = os.path.join(TEMP, f"fb_{i}.jpg")
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black:s={fmt['w']}x{fmt['h']}:d=1", "-frames:v", "1", fb], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            imgs.append(fb)

    if custom_drop is not None and float(custom_drop) > 0:
        drops = [float(custom_drop)]
    else:
        detected_main_drop = find_loudest_drop(audio)
        drops = [detected_main_drop] if variants == 1 else [2.30, detected_main_drop, min(detected_main_drop + 32.0, 120.0)][:variants]

    STATUS["progress"] = 30
    res = []
    for idx, d in enumerate(drops):
        out_name = f"teaser_{int(time.time())}_v{idx + 1}_{fmt_key.replace(':', 'x')}_{render_mode}.mp4"
        out_path = os.path.join(EXPORT, out_name)
        if render_mode == "cinema": STATUS["logs"].append(f"[Cinema-Master] Compositing, Halation & EBU R128 (-14 LUFS)...")
        else: STATUS["logs"].append(f"[FFmpeg] Turbo-Render {idx + 1}/{len(drops)} (Drop: {d:.2f}s)...")
            
        render_teaser(audio, imgs[:4], d, active_hook, pdata, out_path, use_retention, fmt_key, beats, custom_bpm, render_mode)
        res.append({"filename": out_name, "filepath": out_path, "stream_url": f"/api/stream_video?p={urllib.parse.quote(out_path)}", "drop": f"{d:.2f}s", "bpm": f"{custom_bpm:.0f}", "format": fmt_key, "mode": render_mode})
        STATUS["progress"] = int(30 + ((idx + 1) / len(drops)) * 65)

    STATUS["results"] = res
    STATUS["progress"] = 100
    STATUS["logs"].append(f"[Erfolg] Teaser ({render_mode.upper()}) synchron gerendert!")
    subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def clean_track_query(raw_title):
    t = raw_title.strip()
    t = re.sub(r'^\d+[\.\-\s_]+', '', t)
    t = re.sub(r'\[.*?\]', '', t)
    t = re.sub(r'\(.*?(mix|edit|master|original|vip|remix|dub).*?\)', '', t, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', t.replace('$', 's').replace('_', ' ').replace('(', '').replace(')', '')).strip()

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
    tokens = [re.sub(r'["\\]', '', tok) for tok in re.split(r'[\s\-_]+', clean) if len(tok) >= 3][:3]
    if not tokens: tokens = [re.sub(r'["\\]', '', clean)]
    predicates = " && ".join([f'kMDItemFSName == "*{tok}*"c' for tok in tokens])
    audio_type = '(kMDItemContentTypeTree == "public.audio" || kMDItemFSName == "*.wav"c || kMDItemFSName == "*.mp3"c)'
    full_query = f'{audio_type} && ({predicates})'
    try:
        raw = subprocess.check_output(["mdfind", full_query], timeout=4).decode("utf-8").strip()
        lines = [l.strip() for l in raw.split("\n") if l.strip() and os.path.isfile(l.strip())]
    except Exception: lines = []
    
    if not lines and os.path.exists("/Volumes"):
        try:
            for vol in os.listdir("/Volumes"):
                vpath = os.path.join("/Volumes", vol)
                if os.path.isdir(vpath) and vol not in ("Macintosh HD", "Recovery"):
                    for root, _, files in os.walk(vpath):
                        for f in files:
                            if any(f.lower().endswith(e) for e in (".wav", ".mp3", ".aiff", ".flac", ".m4a")):
                                if all(tok.lower() in f.lower() for tok in tokens): lines.append(os.path.join(root, f))
                        if len(lines) >= 3: break
        except Exception: pass

    if not lines: return None
    rated = [(rate_audio_file(f)[0], rate_audio_file(f)[1], f) for f in lines]
    rated.sort(key=lambda x: x[0], reverse=True)
    best = rated[0]
    return {"path": best[2], "filename": os.path.basename(best[2]), "format": best[1]}

def parse_and_scan_crate(raw_text):
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    items, found_count, missing_count = [], 0, 0
    for raw in lines:
        res = find_track_on_mac(raw)
        if res:
            found_count += 1
            items.append({"query": raw, "found": True, "path": res["path"], "filename": res["filename"], "format": res["format"]})
        else:
            missing_count += 1
            items.append({"query": raw, "found": False, "path": "", "filename": "", "format": "FEHLT"})
    CRATE_RESULTS.update({"total_queried": len(lines), "found_count": found_count, "missing_count": missing_count, "items": items})
    return CRATE_RESULTS

def export_denon_m3u8(playlist_name="Denon_Gig_Playlist"):
    found_items = [it for it in CRATE_RESULTS["items"] if it["found"] and it["path"]]
    if not found_items: return {"status": "error", "message": "Keine Tracks gefunden."}
    clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', playlist_name.strip()) or "Denon_Playlist"
    out_file = os.path.join(EXPORT, f"{clean_name}_{int(time.time())}.m3u8")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for it in found_items: f.write(f"#EXTINF:-1,{it['query']}\n{it['path']}\n")
    subprocess.Popen(["open", "-R", out_file])
    return {"status": "ok", "path": out_file, "filename": os.path.basename(out_file)}

def clean_filename_heuristic(raw_name):
    base, ext = os.path.splitext(raw_name)
    name = re.sub(r'\[\s*(FREE DL|OUT NOW|DOWNLOAD|BUY|PROMO|UNRELEASED|PRE-ORDER)[^\]]*\]', '', base, flags=re.IGNORECASE)
    name = re.sub(r'\(?\s*(FREE DL|OUT NOW|DOWNLOAD|BUY|PROMO|UNRELEASED)\s*\)?', '', name, flags=re.IGNORECASE)
    name = re.sub(r'_(hypeddit|sc|soundcloud|yt|edit|master)_?', ' ', name, flags=re.IGNORECASE)
    name = re.sub(r'^\d+[\s\.\-_]+', '', name)
    name = re.sub(r'_\d+bpm', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+', ' ', name.replace('_', ' ').replace('$', 's').strip())
    detected_genre = "Hard Techno"
    for kw, g in {
        "schranz": "Schranz / Hard Techno",
        "acid": "Acid Techno (303)",
        "industrial": "Industrial Techno",
        "hardgroove": "Hardgroove",
        "neorave": "Neo-Rave",
        "peak": "Peak Time / Driving",
        "raw": "Raw & Deep Techno"
    }.items():
        if kw in name.lower():
            detected_genre = g; break
    return name + ext, detected_genre

def scan_cleaner_folder(target_folder):
    target_folder = os.path.expanduser(target_folder)
    if target_folder in ("/", "/System", "/Library", "/bin", "/sbin", "/usr"): return {"status": "error", "message": "Systemordner geschützt."}
    if not os.path.isdir(target_folder): return {"status": "error", "message": f"Ordner existiert nicht: {target_folder}"}
        
    SHARED_STATE["active_folder"] = target_folder
    items, threats_count, all_files = [], 0, []
    
    for root, _, files in os.walk(target_folder):
        for f in files: all_files.append(os.path.join(root, f))
        break
        
    for p in all_files:
        fn = os.path.basename(p)
        if fn.startswith("."): continue
        ext = os.path.splitext(fn)[1].lower()
        if ext in (".py", ".json", ".txt", ".md", ".log", ".plist", ".command", ".sh"): continue
        
        sec = inspect_file_security(p)
        if not sec["safe"]:
            threats_count += 1
            items.append({"path": p, "original_name": fn, "clean_name": fn, "genre": "BEDROHUNG", "safe": False, "threat_msg": sec["message"], "format": ext.upper().replace(".", ""), "selected": False})
            continue
            
        if ext not in AUDIO_EXTENSIONS: continue
            
        clean_name, genre = clean_filename_heuristic(fn)
        dur_info = analyze_track_details(p)
        score, label = rate_audio_file(p)
        items.append({"path": p, "original_name": fn, "clean_name": clean_name, "genre": genre, "safe": True, "threat_msg": sec["message"], "format": label, "score": score, "duration_sec": dur_info["duration_sec"], "duration_str": dur_info["duration_str"], "detected_bpm": dur_info["detected_bpm"], "selected": True})

    duplicates = []
    n = len(items)
    for i in range(n):
        if not items[i]["safe"]: continue
        for j in range(i + 1, n):
            if not items[j]["safe"]: continue
            ti, tj = items[i], items[j]
            q1, q2 = clean_track_query(ti["clean_name"]).lower(), clean_track_query(tj["clean_name"]).lower()
            if q1 and q2 and (q1 == q2 or q1 in q2 or q2 in q1):
                if abs(ti.get("duration_sec", 0) - tj.get("duration_sec", 0)) <= 3.0:
                    winner, loser = (ti, tj) if ti.get("score", 0) >= tj.get("score", 0) else (tj, ti)
                    duplicates.append({"winner_path": winner["path"], "winner_name": winner["original_name"], "winner_format": winner["format"], "loser_path": loser["path"], "loser_name": loser["original_name"], "loser_format": loser["format"]})

    CLEANER_RESULTS.update({"folder": target_folder, "total_scanned": len(items), "threats_found": threats_count, "items": items, "duplicates": duplicates})
    return CLEANER_RESULTS

def apply_cleaning_actions(modifications):
    renamed_count, errors = 0, []
    for mod in modifications:
        old_path, raw_new_name, genre = mod.get("path"), mod.get("new_name", "").strip(), mod.get("genre", "").strip()
        if not old_path or not os.path.exists(old_path) or not os.path.basename(raw_new_name): continue
        dir_name = os.path.dirname(old_path)
        new_path = os.path.join(dir_name, os.path.basename(raw_new_name))
        
        if os.path.abspath(old_path) != os.path.abspath(new_path) and os.path.exists(new_path):
            base, ext = os.path.splitext(new_path)
            new_path = os.path.join(dir_name, f"{base}_clean_1{ext}")
            
        try:
            if os.path.abspath(old_path) != os.path.abspath(new_path):
                os.rename(old_path, new_path)
                active_file = new_path
                renamed_count += 1
            else: active_file = old_path

            if genre and active_file.lower().endswith(".mp3"):
                try:
                    import mutagen
                    from mutagen.easyid3 import EasyID3
                    from mutagen.id3 import ID3NoHeaderError
                    try: audio = EasyID3(active_file)
                    except ID3NoHeaderError:
                        audio = mutagen.File(active_file, easy=True)
                        audio.add_tags()
                    clean_base = os.path.splitext(os.path.basename(active_file))[0]
                    parts = clean_base.split(" - ", 1)
                    if len(parts) > 1: audio["artist"] = parts[0].strip()
                    audio["title"] = parts[1].strip() if len(parts) > 1 else clean_base
                    audio["genre"] = genre
                    audio.save()
                except Exception: pass
        except Exception as e: errors.append(f"{os.path.basename(old_path)}: {str(e)}")
    return {"status": "ok", "renamed_count": renamed_count, "errors": errors}

def trash_file_safely(filepath):
    if not os.path.exists(filepath): return {"status": "error", "message": "Datei existiert nicht."}
    try:
        apple_script = f'''on run argv\n tell application "Finder"\n delete POSIX file (item 1 of argv)\n end tell\nend run'''
        subprocess.run(["osascript", "-e", apple_script, filepath], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return {"status": "ok", "message": f"✓ '{os.path.basename(filepath)}' in Papierkorb verschoben."}
    except Exception:
        try:
            shutil.move(filepath, os.path.join(os.path.expanduser("~/.Trash"), os.path.basename(filepath)))
            return {"status": "ok", "message": f"✓ '{os.path.basename(filepath)}' in ~/.Trash verschoben."}
        except Exception as e: return {"status": "error", "message": str(e)}

HTML = f"""<!DOCTYPE html><html class="dark"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>{APP_NAME} // Pro Studio v{CURRENT_VERSION}</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  * {{ -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif; letter-spacing: -0.012em; user-select: none; }}
  .font-tabular {{ font-family: "SF Mono", Menlo, Monaco, monospace; font-feature-settings: "tnum" 1; }}
  ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
  ::-webkit-scrollbar-track {{ background: rgba(0,0,0,0.15); }}
  ::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.15); border-radius: 3px; }}
  ::-webkit-scrollbar-thumb:hover {{ background: rgba(255,255,255,0.25); }}
  .segmented-active {{ background: #FF453A; color: #ffffff; box-shadow: 0 1px 3px rgba(0,0,0,0.4); }}
  .pro-card {{ background: #161619; border: 1px solid rgba(255,255,255,0.07); }}
  .pro-card-inset {{ background: #0e0e11; border: 1px solid rgba(255,255,255,0.05); }}
</style>
</head>
<body id="dropTarget" class="w-screen h-screen overflow-hidden bg-[#0d0d10] text-zinc-200 flex flex-col transition-colors duration-150">

  <div id="toast" class="fixed bottom-4 right-4 z-50 px-4 py-2.5 rounded-lg text-xs font-bold shadow-2xl transition-all duration-300 transform translate-y-8 opacity-0 pointer-events-none"></div>

  <header class="h-12 border-b border-white/[0.08] bg-[#141418] px-4 flex items-center justify-between shrink-0">
    <div class="flex items-center space-x-3">
      <div class="flex items-center space-x-1.5 mr-2">
        <div class="w-3 h-3 rounded-full bg-[#FF5F56] border border-[#E0443E]"></div>
        <div class="w-3 h-3 rounded-full bg-[#FFBD2E] border border-[#DEA123]"></div>
        <div class="w-3 h-3 rounded-full bg-[#27C93F] border border-[#1AAB29]"></div>
      </div>
      <div class="flex items-center space-x-2">
        <span class="text-sm font-black tracking-wider text-red-500 font-tabular">{APP_NAME}</span>
        <span class="text-[10px] bg-red-950/80 text-red-400 border border-red-800/80 px-2 py-0.5 rounded font-bold">v{CURRENT_VERSION}</span>
        <button id="aiBadgeBtn" onclick="toggleConfigModal()" class="text-[10px] bg-zinc-900 hover:bg-zinc-800 text-zinc-400 border border-white/[0.1] px-2.5 py-0.5 rounded font-bold flex items-center space-x-1 transition cursor-pointer">
          <span id="aiBadgeIcon">🧠</span><span id="aiBadgeText">Brain: Lädt...</span>
        </button>
      </div>
    </div>
    <nav class="flex p-0.5 bg-[#0a0a0c] rounded-lg border border-white/[0.08] text-xs font-semibold">
      <button id="tabVideoBtn" onclick="switchTab('video')" class="segmented-active px-4 py-1.5 rounded-md transition flex items-center space-x-1.5"><span>🎬</span><span>1. Video-Teaser</span></button>
      <button id="tabCrateBtn" onclick="switchTab('crate')" class="text-zinc-400 hover:text-white px-4 py-1.5 rounded-md transition flex items-center space-x-1.5"><span>🎧</span><span>2. Crate-Digger</span></button>
      <button id="tabCleanerBtn" onclick="switchTab('cleaner')" class="text-zinc-400 hover:text-white px-4 py-1.5 rounded-md transition flex items-center space-x-1.5"><span>🧹</span><span>3. KI-Cleaner</span></button>
    </nav>
    <div class="flex items-center space-x-2 text-xs">
      <button id="updBtn" onclick="checkUpdate()" class="px-2.5 py-1 bg-[#1c1c22] border border-white/[0.08] hover:border-red-500/60 text-zinc-300 rounded font-medium transition flex items-center space-x-1"><span>🔄</span><span id="updBtnText">Update suchen</span></button>
      <button onclick="fetch('/api/folder?t=vault')" class="px-2.5 py-1 bg-[#1c1c22] hover:bg-[#25252d] border border-white/[0.08] text-zinc-300 rounded font-medium transition">Vault</button>
      <button onclick="fetch('/api/folder?t=export')" class="px-2.5 py-1 bg-[#1c1c22] hover:bg-[#25252d] border border-white/[0.08] text-zinc-300 rounded font-medium transition">Export</button>
    </div>
  </header>

  <div id="updBanner" class="hidden px-4 py-2 text-xs flex justify-between items-center bg-emerald-950/90 border-b border-emerald-700 text-emerald-200">
    <span id="updMsg" class="font-semibold"></span>
    <button onclick="installUpdate()" id="updInstBtn" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded font-bold transition shadow">Jetzt installieren</button>
  </div>

  <div id="configModal" class="hidden fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="pro-card w-full max-w-md p-5 rounded-xl border border-indigo-500/40 shadow-2xl space-y-4">
      <div class="flex justify-between items-center border-b border-white/[0.08] pb-3">
        <h3 class="text-sm font-bold text-zinc-100 flex items-center space-x-2"><span>🧠</span><span>Google Gemini Cloud-Brain Setup</span></h3>
        <button onclick="toggleConfigModal()" class="text-zinc-400 hover:text-white text-sm">✕</button>
      </div>
      <div class="space-y-2 text-xs">
        <label class="text-[11px] font-bold text-zinc-300 uppercase tracking-wider block">Google AI Studio API-Key:</label>
        <input type="password" id="geminiKeyInput" placeholder="AIzaSy..." class="w-full bg-black border border-white/[0.15] p-2.5 rounded-lg text-zinc-100 font-tabular text-xs focus:border-indigo-500 focus:outline-none">
        <p class="text-[10px] text-zinc-400">Gesichert in ~/.techdude_config.json. Überlebt alle Code-Updates auf dem Mac.</p>
      </div>
      <button onclick="saveApiKey()" class="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs rounded-lg transition uppercase tracking-wider">Key speichern & testen</button>
    </div>
  </div>

  <main class="flex-1 grid grid-cols-12 overflow-hidden">
    <div id="tabVideo" class="col-span-12 grid grid-cols-12 h-full overflow-hidden">
      <aside class="col-span-5 xl:col-span-4 border-r border-white/[0.08] bg-[#121215] flex flex-col overflow-y-auto p-4 space-y-3">
        
        <!-- INTERAKTIVES TRACK-DROPDOWN -->
        <div class="pro-card-inset p-3 rounded-lg flex items-center justify-between border border-red-500/30">
          <div class="truncate mr-2 w-full">
            <div class="text-[10px] font-bold text-red-500 uppercase tracking-wider mb-1 flex items-center space-x-1">
              <span>🎧</span><span>Aktiver Master-Track</span>
            </div>
            <select id="trackSelect" onchange="changeActiveTrack(this.value)" class="w-full bg-black border border-white/[0.15] p-2 rounded text-xs text-zinc-100 focus:outline-none focus:border-red-500 font-bold truncate cursor-pointer">
                <option value="">Scanne Vault...</option>
            </select>
          </div>
          <div class="flex flex-col items-end justify-center ml-2 shrink-0">
            <span id="trackInfoDisplay" class="text-[11px] font-tabular bg-white/[0.06] text-zinc-300 px-2 py-1 rounded whitespace-nowrap mb-1">--:--</span>
            <span id="trackBpmDisplay" class="text-[10px] font-bold text-zinc-500">-- BPM</span>
          </div>
        </div>

        <div class="p-3 rounded-lg bg-gradient-to-r from-red-950/80 via-[#1f1214] to-[#16161a] border border-red-700/60 shadow-md flex items-center justify-between">
          <div><div class="text-xs font-black text-red-400">🔥 AUTOPILOT PEAK-SCAN</div><div class="text-[11px] text-zinc-400 mt-0.5">Lautester Drop • Auto-Sync</div></div>
          <button onclick="triggerAutopilot()" id="btnAuto" class="px-3.5 py-1.5 bg-[#FF453A] hover:bg-red-500 text-white font-bold text-xs uppercase tracking-wider rounded shadow transition active:scale-95">Mach einfach</button>
        </div>

        <div class="space-y-1.5">
          <div class="flex justify-between items-center"><label class="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Engine-Qualitätsmodus</label><span id="renderModeBadge" class="text-[10px] font-bold text-amber-400 font-tabular bg-amber-950/60 px-2 py-0.5 rounded border border-amber-900/60">⚡ Turbo</span></div>
          <div class="grid grid-cols-2 gap-1 bg-[#0a0a0c] p-1 rounded-lg border border-white/[0.08] text-xs font-medium text-center">
            <button type="button" onclick="selectRenderMode('turbo')" id="modeBtn_turbo" class="segmented-active py-1.5 rounded transition">⚡ Turbo-Draft (3.8s)</button>
            <button type="button" onclick="selectRenderMode('cinema')" id="modeBtn_cinema" class="text-zinc-400 hover:text-white py-1.5 rounded transition">💎 Cinema-Master</button>
          </div>
          <input type="hidden" id="renderModeSelect" value="turbo">
        </div>

        <div class="space-y-1.5">
          <label class="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Format & Platform</label>
          <div class="grid grid-cols-3 gap-1 bg-[#0a0a0c] p-1 rounded-lg border border-white/[0.08] text-xs font-medium text-center">
            <button onclick="selectFormat('9:16')" id="fmtBtn_9_16" class="segmented-active py-1.5 rounded transition">9:16 TikTok</button>
            <button onclick="selectFormat('1:1')" id="fmtBtn_1_1" class="text-zinc-400 hover:text-white py-1.5 rounded transition">1:1 Feed</button>
            <button onclick="selectFormat('16:9')" id="fmtBtn_16_9" class="text-zinc-400 hover:text-white py-1.5 rounded transition">16:9 Cinema</button>
          </div>
          <input type="hidden" id="fmtSelect" value="9:16">
        </div>

        <div class="pro-card p-2.5 rounded-lg space-y-1.5">
          <div class="flex justify-between items-center"><label class="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Tempo (BPM Sync)</label><span id="bpmDisplay" class="text-xs font-black text-red-400 font-tabular bg-red-950/50 px-2 py-0.5 rounded border border-red-900/60">155 BPM</span></div>
          <div class="flex items-center space-x-2">
            <button onclick="nudgeBpm(-1)" class="w-7 h-7 bg-white/[0.06] hover:bg-white/[0.1] rounded text-xs font-bold text-zinc-300">-</button>
            <input type="range" id="bpmSlider" min="140" max="168" value="155" step="1" oninput="updateBpm(this.value)" class="flex-1 accent-red-600 bg-zinc-800 cursor-pointer">
            <button onclick="nudgeBpm(+1)" class="w-7 h-7 bg-white/[0.06] hover:bg-white/[0.1] rounded text-xs font-bold text-zinc-300">+</button>
            <input type="number" id="bpmNumber" min="140" max="168" value="155" oninput="updateBpm(this.value)" class="w-14 bg-black border border-white/[0.1] p-1 rounded text-xs text-center text-zinc-200 font-tabular">
          </div>
        </div>

        <div class="grid grid-cols-2 gap-2">
          <div class="pro-card p-2 rounded-lg space-y-1">
            <label class="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">Taktung / Beats</label>
            <select id="beatsSelect" class="w-full bg-black border border-white/[0.1] p-1.5 rounded text-xs text-zinc-200 focus:outline-none"><option value="12">12 Beats</option><option value="16" selected>16 Beats</option><option value="24">24 Beats</option></select>
          </div>
          <div class="pro-card p-2 rounded-lg space-y-1">
            <label class="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">Style-Preset (8 Stile)</label>
            <select id="p" class="w-full bg-black border border-white/[0.1] p-1.5 rounded text-xs text-zinc-200 focus:outline-none">
              <option value="warehouse">Industrial Warehouse</option>
              <option value="acid">Acid 303 Tunnel</option>
              <option value="tribal">Y2K Cyber Tribal</option>
              <option value="schranz">Schranz Distortion</option>
              <option value="hardgroove">Hardgroove Minimal</option>
              <option value="berlin">Berlin Darkroom</option>
              <option value="neorave">Neo-Rave Speed</option>
              <option value="industrial">Raw Concrete Industrial</option>
            </select>
          </div>
        </div>

        <div class="space-y-1.5">
          <div class="flex justify-between items-center"><label class="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Hook-Text</label>
            <button onclick="fetchAiViralHooks()" id="aiHookScoutBtn" class="text-[10px] font-bold bg-indigo-950/80 hover:bg-indigo-900 text-indigo-300 border border-indigo-700/60 px-2 py-0.5 rounded transition">🧠 KI-Scout</button>
          </div>
          <div id="aiHookPills" class="flex flex-wrap gap-1 text-[10px]">
            <button onclick="setHook('UNRELEASED ID?')" class="px-1.5 py-0.5 bg-white/[0.06] hover:bg-red-950 text-zinc-300 rounded">ID?</button>
            <button onclick="setHook('160 BPM ACID PRESSURE')" class="px-1.5 py-0.5 bg-white/[0.06] hover:bg-red-950 text-zinc-300 rounded">ACID</button>
            <button onclick="setHook('165 BPM SCHRANZ DROP')" class="px-1.5 py-0.5 bg-white/[0.06] hover:bg-red-950 text-zinc-300 rounded">SCHRANZ</button>
          </div>
          <input type="text" id="hook" placeholder="POV: FIRST TIME VERKNIPT" class="w-full bg-black border border-white/[0.1] p-2 rounded text-xs text-zinc-100 focus:outline-none focus:border-red-500 font-medium">
        </div>

        <div class="pro-card p-2 rounded-lg flex items-center justify-between">
          <div><div class="text-xs font-semibold text-zinc-200">Reverse-Build-up</div><div class="text-[10px] text-zinc-400">Kick bei 0.00s + Filterspannung</div></div>
          <input type="checkbox" id="retention" checked class="w-4 h-4 accent-red-600 cursor-pointer">
        </div>

        <button id="btn" onclick="startRender()" class="w-full py-3 bg-[#FF453A] hover:bg-red-500 text-white rounded-lg font-black text-xs uppercase tracking-wider shadow-lg transition active:scale-95">🎬 Teaser jetzt synchron rendern</button>

        <div class="pro-card-inset p-2.5 rounded-lg space-y-1 text-xs">
          <div class="flex justify-between text-zinc-400 font-bold text-[11px]"><span>ENGINE STATUS:</span><span id="ptxt" class="text-red-500 font-tabular">0%</span></div>
          <div class="bg-black h-1.5 rounded-full overflow-hidden"><div id="pbar" class="bg-[#FF453A] h-full w-0 transition-all duration-300"></div></div>
          <div id="logs" class="text-zinc-500 text-[10px] font-tabular max-h-16 overflow-y-auto space-y-0.5 pt-1">Bereit.</div>
        </div>
      </aside>

      <section class="col-span-7 xl:col-span-8 bg-[#0b0b0e] flex flex-col p-4 space-y-3 overflow-hidden">
        <div class="flex items-center justify-between border-b border-white/[0.06] pb-2">
          <div class="flex items-center space-x-2"><span class="text-xs font-bold uppercase tracking-wider text-zinc-400">Live Stage & Monitor</span><span id="stageBadge" class="text-[10px] bg-white/[0.08] text-zinc-300 px-2 py-0.5 rounded font-tabular">Bereit</span></div>
          <button onclick="unloadVideoPlayer()" class="text-zinc-400 hover:text-white text-[11px] px-2 py-0.5 bg-white/[0.04] rounded">Stage leeren</button>
        </div>

        <div class="flex-1 pro-card-inset rounded-xl flex items-center justify-center relative overflow-hidden p-2">
          <div id="videoContainer" class="h-full max-h-[500px] aspect-[9/16] bg-black rounded-lg border border-white/[0.1] shadow-2xl relative flex items-center justify-center overflow-hidden">
            <video id="stageVideo" class="w-full h-full object-cover hidden" loop playsinline preload="auto"></video>
            <div id="stagePlaceholder" class="text-center space-y-2 p-6">
              <div class="w-14 h-14 mx-auto rounded-full bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-xl text-zinc-500">🎬</div>
              <div class="text-xs font-bold text-zinc-400">Noch kein Teaser gerendert</div>
            </div>
            <button id="stagePlayBtn" onclick="toggleStageVideo()" class="hidden absolute bottom-3 right-3 w-8 h-8 rounded-full bg-black/70 hover:bg-[#FF453A] border border-white/20 text-white flex items-center justify-center text-xs transition">⏸</button>
          </div>
        </div>

        <div class="pro-card p-3 rounded-lg space-y-1.5">
          <div class="flex justify-between items-center text-[10px] font-bold text-zinc-400 uppercase tracking-wider">
            <span class="flex items-center space-x-1"><span>🔊</span><span>Audio Hüllkurve (Klick zum Scrubben)</span></span>
            <span id="dropIndicatorLabel" class="text-red-400 font-tabular">Drop: Peak Scan</span>
          </div>
          <div id="waveformContainer" onclick="handleWaveformClick(event)" title="Klicke auf die Wellenform, um den Drop-Punkt zu verschieben" class="h-14 bg-[#0a0a0c] rounded border border-white/[0.06] hover:border-red-500/50 relative overflow-hidden flex items-center px-1 cursor-pointer select-none transition">
            <svg id="waveformSvg" class="w-full h-10 overflow-visible pointer-events-none" preserveAspectRatio="none" viewBox="0 0 100 40"><g id="waveformBars"></g></svg>
            <div id="dropLine" class="absolute top-0 bottom-0 w-0.5 bg-[#FF453A] shadow-[0_0_8px_#FF453A] left-[15%] transition-all duration-150 pointer-events-none"><div class="absolute -top-1 -left-1.5 w-3.5 h-3.5 rounded-full bg-[#FF453A] text-[8px] font-black text-white flex items-center justify-center">▼</div></div>
          </div>
          <input type="hidden" id="customDropInput" value="">
        </div>
        <div id="res" class="max-h-24 overflow-y-auto space-y-1.5"></div>
      </section>
    </div>

    <div id="tabCrate" class="col-span-12 grid grid-cols-12 h-full overflow-hidden hidden">
      <aside class="col-span-4 border-r border-white/[0.08] bg-[#121215] flex flex-col p-4 space-y-3 overflow-y-auto">
        <div class="space-y-1">
          <div class="flex justify-between items-center"><label class="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Tracklist (Notizen):</label>
            <button onclick="aiParseCrateNotes()" id="aiParseNotesBtn" class="text-[10px] font-bold bg-indigo-950/80 hover:bg-indigo-900 text-indigo-300 border border-indigo-700/60 px-2 py-0.5 rounded transition flex items-center space-x-1"><span>🧠</span><span>KI-Entwirrer</span></button>
          </div>
          <textarea id="crateText" rows="14" placeholder="1. Nico Moreno - Purple Widow" class="w-full bg-black border border-white/[0.1] p-2.5 rounded-lg text-xs text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-red-500 font-tabular"></textarea>
        </div>
        <div class="flex space-x-2 pt-1">
          <button id="crateBtn" onclick="startCrateScan()" class="flex-1 py-2.5 bg-[#FF453A] hover:bg-red-500 text-white rounded-lg font-bold text-xs uppercase tracking-wider transition">🔍 Tracks suchen</button>
        </div>
      </aside>
      <section class="col-span-8 bg-[#0b0b0e] flex flex-col p-4 space-y-3 overflow-hidden">
        <div class="flex justify-between items-center border-b border-white/[0.06] pb-2">
          <div class="flex items-center space-x-2"><span class="text-xs font-bold uppercase tracking-wider text-zinc-400">Gefundene Audio-Master</span><span id="crateMatchRate" class="text-xs font-tabular font-bold text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-900/60">0 / 0</span></div>
          <div class="flex items-center space-x-2"><input type="text" id="plName" value="Denon_Gig_Playlist" class="bg-black border border-white/[0.1] px-2.5 py-1 rounded text-xs text-zinc-200 font-tabular w-44"><button onclick="exportM3U8()" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded font-bold text-xs transition">⚡ Denon M3U8 Export</button></div>
        </div>
        <div id="crateItems" class="flex-1 overflow-y-auto space-y-1.5 pr-1"></div>
      </section>
    </div>

    <div id="tabCleaner" class="col-span-12 grid grid-cols-12 h-full overflow-hidden hidden">
      <aside class="col-span-4 border-r border-white/[0.08] bg-[#121215] flex flex-col p-4 space-y-3.5 overflow-y-auto">
        
        <div class="space-y-1.5">
          <label class="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Ziel-Ordner zum Bereinigen:</label>
          <div class="flex items-center space-x-2">
            <select id="cleanerFolderSelect" onchange="changeCleanerFolder(this.value)" class="w-1/3 bg-black border border-white/[0.1] p-2 rounded-lg text-xs text-zinc-200 focus:outline-none">
              <option value="~/Downloads">📥 Downloads</option>
              <option value="~/Music">🎵 Music</option>
              <option value="input_vault">📦 Vault</option>
            </select>
            <input type="text" id="customFolderPath" placeholder="/Pfad/zum/Ordner" class="flex-1 bg-black border border-white/[0.1] p-2 rounded-lg text-xs text-zinc-200 font-tabular focus:outline-none">
            <button onclick="pickFolder()" class="px-3 py-2 bg-white/[0.06] hover:bg-white/[0.1] border border-white/[0.1] rounded-lg text-xs" title="Ordner auf dem Mac durchsuchen">📂</button>
          </div>
        </div>

        <div class="flex p-0.5 bg-[#0a0a0c] rounded-lg border border-white/[0.08] text-[10px] font-bold mt-1">
          <button id="clnMode_malware" onclick="setCleanerMode('malware')" class="segmented-active px-1 py-1.5 rounded w-1/3 transition">🛡️ Viren</button>
          <button id="clnMode_dupes" onclick="setCleanerMode('dupes')" class="text-zinc-400 hover:text-white px-1 py-1.5 rounded w-1/3 transition">👯 Duplikate</button>
          <button id="clnMode_edit" onclick="setCleanerMode('edit')" class="text-zinc-400 hover:text-white px-1 py-1.5 rounded w-1/3 transition">🏷️ Tracks Editieren</button>
        </div>

        <button onclick="startCleanerScan()" id="cleanScanBtn" class="w-full py-2.5 bg-[#FF453A] hover:bg-red-500 text-white rounded-lg font-bold text-xs uppercase tracking-wider transition">Ordner Scannen & Prüfen</button>
        
        <div id="cleanerBanner" class="p-3 rounded-lg border text-xs bg-zinc-900 border-white/[0.08] text-zinc-300 space-y-1"><div class="font-bold text-zinc-200">Zero-RAM Sentinel Status</div><div id="cleanerBannerText" class="text-[11px] text-zinc-400">Noch kein Scan ausgeführt.</div></div>
        <div id="duplicateSection" class="hidden bg-amber-950/30 border border-amber-800/60 p-3 rounded-lg space-y-2 text-xs"><div class="flex justify-between items-center font-bold text-amber-400"><span>⚠️ DUPLIKATE (<span id="dupCount">0</span>)</span></div><div id="duplicateList" class="space-y-1.5 max-h-40 overflow-y-auto"></div></div>
        
        <div class="pt-2">
          <button id="cleanerExecBtn" onclick="executeCleanAndRename()" class="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-lg transition uppercase tracking-wider hidden">⚡ Ausgewählte Taggen</button>
        </div>
      </aside>
      <section class="col-span-8 bg-[#0b0b0e] flex flex-col p-4 space-y-3 overflow-hidden">
        <div class="flex justify-between items-center border-b border-white/[0.06] pb-2"><span class="text-xs font-bold uppercase tracking-wider text-zinc-400">Scanner Vorschau-Matrix</span><button onclick="toggleSelectAllCleaner()" class="text-zinc-400 hover:text-white text-[11px] underline">Alle an/abwählen</button></div>
        <div id="cleanerRows" class="flex-1 overflow-y-auto space-y-2 pr-1"></div>
      </section>
    </div>
  </main>

<script>
let userChangedBpm = false, currentCleanerItems = [], currentWaveformPoints = [], currentDropSec = 2.30, currentDurationSec = 180.0, activeRenderMode = "turbo", currentCleanerMode = "malware";

function showToast(msg, type='info') {
  const t = document.getElementById('toast');
  t.innerText = msg;
  t.className = `fixed bottom-4 right-4 z-50 px-4 py-2.5 rounded-lg text-xs font-bold shadow-2xl transition-all duration-300 transform translate-y-0 opacity-100 ${{type === 'error' ? 'bg-red-600 text-white' : type === 'success' ? 'bg-emerald-600 text-white' : 'bg-zinc-800 text-zinc-100 border border-white/10'}}`;
  setTimeout(() => {
    t.className = 'fixed bottom-4 right-4 z-50 px-4 py-2.5 rounded-lg text-xs font-bold shadow-2xl transition-all duration-300 transform translate-y-8 opacity-0 pointer-events-none';
  }, 3500);
}

async function fetchApiKeyStatus() {
    try {
        const res = await(await fetch('/api/config')).json();
        const badge = document.getElementById('aiBadgeBtn');
        if (res.has_key) {
            badge.className = 'text-[10px] bg-indigo-950/90 hover:bg-indigo-900 text-indigo-200 border border-indigo-700/60 px-2.5 py-0.5 rounded font-bold flex items-center space-x-1 transition cursor-pointer';
            document.getElementById('aiBadgeText').innerText = 'Brain: Online';
        } else {
            badge.className = 'text-[10px] bg-zinc-900 hover:bg-zinc-800 text-zinc-400 border border-white/[0.1] px-2.5 py-0.5 rounded font-bold flex items-center space-x-1 transition cursor-pointer';
            document.getElementById('aiBadgeText').innerText = 'Brain: Offline (Bunker)';
        }
    } catch (e) {}
}
window.addEventListener('DOMContentLoaded', () => { fetchApiKeyStatus(); });

function setHook(t){ document.getElementById('hook').value = t; }
function selectRenderMode(mode){
  activeRenderMode = mode; document.getElementById('renderModeSelect').value = mode;
  const bTurbo = document.getElementById('modeBtn_turbo'), bCinema = document.getElementById('modeBtn_cinema'), badge = document.getElementById('renderModeBadge');
  if(mode === 'cinema'){
    bCinema.className = 'segmented-active py-1.5 rounded transition'; bTurbo.className = 'text-zinc-400 hover:text-white py-1.5 rounded transition';
    badge.innerText = '💎 Cinema-Master'; badge.className = 'text-[10px] font-bold text-red-400 font-tabular bg-red-950/60 px-2 py-0.5 rounded border border-red-900/60';
  } else {
    bTurbo.className = 'segmented-active py-1.5 rounded transition'; bCinema.className = 'text-zinc-400 hover:text-white py-1.5 rounded transition';
    badge.innerText = '⚡ Turbo'; badge.className = 'text-[10px] font-bold text-amber-400 font-tabular bg-amber-950/60 px-2 py-0.5 rounded border border-amber-900/60';
  }
}

function selectFormat(fmt){
  document.getElementById('fmtSelect').value = fmt;
  ['9_16', '1_1', '16_9'].forEach(k => {
    document.getElementById('fmtBtn_' + k).className = (k === fmt.replace(':', '_')) ? 'segmented-active py-1.5 rounded transition' : 'text-zinc-400 hover:text-white py-1.5 rounded transition';
  });
}

function nudgeBpm(delta){ updateBpm(Math.max(140, Math.min(168, (parseInt(document.getElementById('bpmNumber').value) || 155) + delta))); }
function updateBpm(val){ userChangedBpm = true; document.getElementById('bpmSlider').value = val; document.getElementById('bpmNumber').value = val; document.getElementById('bpmDisplay').innerText = val + ' BPM'; }

function switchTab(t){
  ['video', 'crate', 'cleaner'].forEach(tab => {
    document.getElementById('tab' + tab.charAt(0).toUpperCase() + tab.slice(1)).classList.toggle('hidden', tab !== t);
    document.getElementById('tab' + tab.charAt(0).toUpperCase() + tab.slice(1) + 'Btn').className = (tab === t) ? 'segmented-active px-4 py-1.5 rounded-md transition flex items-center space-x-1.5' : 'text-zinc-400 hover:text-white px-4 py-1.5 rounded-md transition flex items-center space-x-1.5';
  });
}

function drawWaveform(points, dropSec, totalSec){
  const svgGroup = document.getElementById('waveformBars');
  if(!points || points.length === 0) points = Array.from({{length: 100}}, () => 0.15);
  svgGroup.innerHTML = points.map((p, i) => `<rect x="${{i}}" y="${{20 - (Math.max(3, Math.round(p * 36)) / 2)}}" width="0.75" height="${{Math.max(3, Math.round(p * 36))}}" fill="rgba(255,255,255,0.22)" rx="0.3"></rect>`).join('');
  if(totalSec > 0){
    document.getElementById('dropLine').style.left = Math.max(2, Math.min(96, (dropSec / totalSec) * 100)) + '%';
    document.getElementById('dropIndicatorLabel').innerText = `Drop: ${{dropSec.toFixed(2)}}s / ${{totalSec.toFixed(0)}}s`;
  }
}

function handleWaveformClick(e){
  const rect = document.getElementById('waveformContainer').getBoundingClientRect();
  const newDrop = parseFloat((Math.max(0.01, Math.min(0.98, (e.clientX - rect.left) / rect.width)) * currentDurationSec).toFixed(2));
  currentDropSec = newDrop; document.getElementById('customDropInput').value = newDrop;
  drawWaveform(currentWaveformPoints, currentDropSec, currentDurationSec);
  document.getElementById('logs').innerText = `Drop-Marker manuell gesetzt auf: ${{newDrop.toFixed(2)}}s`;
}

async function changeActiveTrack(val){
    await fetch('/api/set_active_track', {{method: 'POST', body: JSON.stringify({{filename: val}})}});
    updateTrackInfo();
}

async function updateTrackInfo(){
  try{{
    const res = await(await fetch('/api/active_track')).json();
    if(res.processing) return;
    
    const sel = document.getElementById('trackSelect');
    if(res.has_audio){
      if(sel.options.length !== res.vault_files.length || (sel.options.length > 0 && sel.options[0].value !== res.vault_files[0])) {{
          sel.innerHTML = res.vault_files.map(f => `<option value="${{f}}" ${{f === res.filename ? 'selected' : ''}}>${{f}}</option>`).join('');
      }} else {{
          sel.value = res.filename;
      }}
      document.getElementById('trackInfoDisplay').innerText = res.duration_str;
      document.getElementById('trackBpmDisplay').innerText = Math.round(res.detected_bpm) + ' BPM';
      
      currentDurationSec = res.duration_sec || 180.0;
      currentDropSec = document.getElementById('customDropInput').value ? parseFloat(document.getElementById('customDropInput').value) : (res.drop_sec || 2.30);
      currentWaveformPoints = res.waveform || [];
      drawWaveform(currentWaveformPoints, currentDropSec, currentDurationSec);
      if(!userChangedBpm && res.detected_bpm) updateBpm(Math.round(res.detected_bpm)); userChangedBpm = false;
    }} else {{ 
      sel.innerHTML = '<option value="">Kein Track im Vault</option>';
      document.getElementById('trackInfoDisplay').innerText = '--:--'; 
      document.getElementById('trackBpmDisplay').innerText = '-- BPM';
      drawWaveform([], 2.30, 180); 
    }}
  }}catch(e){{}}
}
updateTrackInfo(); setInterval(updateTrackInfo, 3500);

function toggleConfigModal(){ document.getElementById('configModal').classList.toggle('hidden'); }
async function saveApiKey(){
  const res = await(await fetch('/api/config', {{ method: 'POST', body: JSON.stringify({{ gemini_api_key: document.getElementById('geminiKeyInput').value.trim() }}) }})).json();
  showToast(res.message, res.status === 'ok' ? 'success' : 'error');
  toggleConfigModal(); fetchApiKeyStatus();
}

async function fetchAiViralHooks(){
  const btn = document.getElementById('aiHookScoutBtn'); btn.disabled = true; btn.innerHTML = '<span>⏳</span><span>Scoute...</span>';
  try {{
    const trackName = document.getElementById('trackSelect').value || 'Unknown Track';
    const res = await(await fetch('/api/gemini/generate_hooks', {{ method: 'POST', body: JSON.stringify({{ track: trackName, bpm: parseFloat(document.getElementById('bpmNumber').value) || 155, style: document.getElementById('p').value || 'warehouse' }}) }})).json();
    if(res.hooks && res.hooks.length > 0){{
      document.getElementById('aiHookPills').innerHTML = res.hooks.map(h => `<button onclick="setHook('${{h.replace(/'/g, "\\'")}}')" class="px-2 py-0.5 bg-indigo-950/90 hover:bg-red-950 text-indigo-200 border border-indigo-700/60 rounded text-[10px] font-bold">${{h}}</button>`).join('');
      setHook(res.hooks[0]);
    }}
  }} catch(e){{ showToast('Fehler beim KI-Scouting: ' + e, 'error'); }}
  btn.disabled = false; btn.innerHTML = '<span>🧠</span><span>KI-Scout</span>';
}

async function aiParseCrateNotes(){
  const ta = document.getElementById('crateText'), raw = ta.value.trim();
  if(!raw) return showToast('Bitte Text in die Tracklist einfügen!', 'error');
  const btn = document.getElementById('aiParseNotesBtn'); btn.disabled = true; btn.innerHTML = '<span>⏳</span><span>Entwirre...</span>';
  try {{
    const res = await(await fetch('/api/gemini/parse_notes', {{ method: 'POST', body: JSON.stringify({{ raw_text: raw }}) }})).json();
    if(res.parsed && res.parsed.length > 0) ta.value = res.parsed.join('\n');
  }} catch(e){{}}
  btn.disabled = false; btn.innerHTML = '<span>🧠</span><span>KI-Entwirrer</span>';
}

function loadVideoToStage(streamUrl, filename){
  const v = document.getElementById('stageVideo');
  v.pause(); v.src = streamUrl; v.load();
  v.classList.remove('hidden'); document.getElementById('stagePlaceholder').classList.add('hidden');
  document.getElementById('stagePlayBtn').classList.remove('hidden'); document.getElementById('stageBadge').innerText = filename || 'Loop aktiv';
  v.play().catch(() => {{}});
}

function unloadVideoPlayer(){
  const v = document.getElementById('stageVideo'); v.pause(); v.src = ''; v.classList.add('hidden');
  document.getElementById('stagePlaceholder').classList.remove('hidden'); document.getElementById('stagePlayBtn').classList.add('hidden'); document.getElementById('stageBadge').innerText = 'Bereit';
}

function toggleStageVideo(){
  const v = document.getElementById('stageVideo'), pb = document.getElementById('stagePlayBtn');
  if(v.paused){{ v.play(); pb.innerText = '⏸'; }} else {{ v.pause(); pb.innerText = '▶'; }}
}

const body = document.getElementById('dropTarget');
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => body.addEventListener(evt, e => {{ e.preventDefault(); e.stopPropagation(); }}, false));
body.addEventListener('dragover', () => body.classList.add('bg-[#1a1315]'), false);
body.addEventListener('dragleave', () => body.classList.remove('bg-[#1a1315]'), false);
body.addEventListener('drop', async e => {{
  body.classList.remove('bg-[#1a1315]');
  const files = e.dataTransfer.files; if(!files.length) return;
  const formData = new FormData(); for(let i=0; i<files.length; i++) formData.append('files', files[i]);
  await fetch('/api/upload', {{ method: 'POST', body: formData }}); updateTrackInfo();
}});

async function triggerAutopilot(){
  document.getElementById('btn').disabled = document.getElementById('btnAuto').disabled = true;
  await fetch('/api/autopilot', {{ method: 'POST', body: JSON.stringify({{ bpm: parseFloat(document.getElementById('bpmNumber').value) || 155, mode: document.getElementById('renderModeSelect').value || 'turbo' }}) }}); poll();
}

async function startRender(){
  document.getElementById('btn').disabled = document.getElementById('btnAuto').disabled = true;
  await fetch('/api/render', {{ method: 'POST', body: JSON.stringify({{ p: document.getElementById('p').value, v: 1, hook: document.getElementById('hook').value, retention: document.getElementById('retention').checked, fmt: document.getElementById('fmtSelect').value, beats: parseInt(document.getElementById('beatsSelect').value), bpm: parseFloat(document.getElementById('bpmNumber').value) || 155, mode: document.getElementById('renderModeSelect').value || 'turbo', drop: document.getElementById('customDropInput').value ? parseFloat(document.getElementById('customDropInput').value) : null }}) }}); poll();
}

async function poll(){
  const d = await(await fetch('/api/status')).json();
  document.getElementById('pbar').style.width = d.progress + '%'; document.getElementById('ptxt').innerText = d.progress + '%';
  document.getElementById('logs').innerHTML = d.logs.map(l => '<div>' + l + '</div>').join('');
  if(d.results && d.results.length > 0){{
    if(d.progress === 100 && d.results[0]) loadVideoToStage(d.results[0].stream_url, d.results[0].filename);
    document.getElementById('res').innerHTML = d.results.map(r => `
      <div class="pro-card p-2 rounded-lg flex justify-between items-center text-xs">
        <div><div class="font-bold text-zinc-100 flex items-center space-x-1"><span>🎬</span><span>${{r.filename}}</span></div></div>
        <div class="space-x-1.5 flex items-center">
          <button onclick="loadVideoToStage('${{r.stream_url}}', '${{r.filename}}')" class="px-2 py-1 bg-red-950/80 text-red-300 border border-red-800 hover:bg-red-600 hover:text-white rounded text-[11px] font-bold transition">Auf Stage</button>
          <button onclick="fetch('/api/reveal?p='+encodeURIComponent('${{r.filepath}}'))" class="px-2 py-1 bg-white/[0.06] hover:bg-white/[0.1] rounded text-zinc-300 text-[11px] transition">Finder</button>
        </div>
      </div>`).join('');
  }}
  if(d.progress === 100 || (d.progress === 0 && d.logs.some(l => l.includes('FEHLER') || l.includes('Crash')))){{ document.getElementById('btn').disabled = document.getElementById('btnAuto').disabled = false; }} else setTimeout(poll, 700);
}

async function startCrateScan(){
  const text=document.getElementById('crateText').value; if(!text.trim()) return;
  const b=document.getElementById('crateBtn'); b.disabled=true; b.innerText='⏳ Scanne...';
  try{{
    const res=await(await fetch('/api/crate_scan',{{method:'POST',body:JSON.stringify({{text}})}})).json();
    document.getElementById('crateMatchRate').innerText=`${{res.found_count}} / ${{res.total_queried}}`;
    document.getElementById('crateItems').innerHTML=res.items.map(it=>`
      <div class="p-2.5 rounded-lg ${{it.found?'pro-card':'bg-red-950/20'}} flex justify-between items-center text-xs">
        <div><div class="font-bold ${{it.found?'text-zinc-100':'text-red-400'}}">${{it.found?'✅':'❌'}} ${{it.query}}</div><div class="text-[10px] text-zinc-400 truncate max-w-lg mt-0.5">${{it.path || 'Fehlt'}}</div></div>
        <div class="flex items-center space-x-1.5">
          <span class="px-2 py-0.5 rounded text-[10px] font-bold font-tabular ${{it.found?'bg-emerald-950 text-emerald-300 border border-emerald-800':'bg-zinc-800 text-zinc-500'}}">${{it.format}}</span>
          ${{it.found?`<button onclick="fetch('/api/copy_vault?path=${{encodeURIComponent(it.path)}}');showToast('✓ In Vault kopiert!','success');updateTrackInfo();" class="px-2 py-1 bg-white/[0.06] hover:bg-white/[0.1] rounded text-[10px] text-zinc-300 transition">In Vault</button>`:''}}
        </div>
      </div>`).join('');
  }}catch(e){{}} b.disabled=false; b.innerText='🔍 Tracks suchen';
}

async function exportM3U8(){
  const res=await(await fetch('/api/crate_export',{{method:'POST',body:JSON.stringify({{name: document.getElementById('plName').value}})}})).json();
  if(res.status==='ok') showToast(`✓ Gespeichert: ${{res.filename}}`, 'success');
}

function changeCleanerFolder(val){ document.getElementById('customFolderPath').value = val === 'input_vault' ? '' : val; }

function setCleanerMode(mode) {{
    currentCleanerMode = mode;
    ['malware', 'dupes', 'edit'].forEach(m => {{
        document.getElementById('clnMode_' + m).className = (m === mode) ? 'segmented-active px-1 py-1.5 rounded w-1/3 transition' : 'text-zinc-400 hover:text-white px-1 py-1.5 rounded w-1/3 transition';
    }});
    renderCleanerView();
}}

async function pickFolder() {{
    try {{
        const res = await(await fetch('/api/pick_folder')).json();
        if(res.path) {{ document.getElementById('customFolderPath').value = res.path; }}
    }} catch(e) {{}}
}}

async function startCleanerScan(){{
  const folder = document.getElementById('customFolderPath').value || document.getElementById('cleanerFolderSelect').value;
  const btn = document.getElementById('cleanScanBtn'); btn.disabled = true; btn.innerText = '🛡 Scanne...';
  try {{
    const res = await(await fetch('/api/cleaner/scan', {{ method: 'POST', body: JSON.stringify({{ folder }}) }})).json();
    currentCleanerItems = res.items || [];
    document.getElementById('cleanerBanner').className = res.threats_found > 0 ? 'p-3 rounded-lg border text-xs bg-red-950/80 border-red-700 text-red-200 space-y-1 mt-2' : 'p-3 rounded-lg border text-xs bg-emerald-950/60 border-emerald-700/60 text-emerald-300 space-y-1 mt-2';
    document.getElementById('cleanerBannerText').innerHTML = res.threats_found > 0 ? `🚨 <strong>WARNUNG:</strong> ${{res.threats_found}} Bedrohung(en) isoliert!` : `🟢 <strong>SENTINEL CLEAN:</strong> Alle ${{res.total_scanned}} Dateien geprüft.`;
    
    document.getElementById('dupCount').innerText = res.duplicates ? res.duplicates.length : 0;
    renderCleanerView();
  }} catch(e){{}} btn.disabled = false; btn.innerText = 'Ordner Scannen & Prüfen';
}}

function renderCleanerView() {{
    if(!currentCleanerItems || currentCleanerItems.length === 0) return;
    
    document.getElementById('duplicateSection').classList.toggle('hidden', currentCleanerMode !== 'dupes');
    document.getElementById('cleanerExecBtn').classList.toggle('hidden', currentCleanerMode !== 'edit');
    
    let html = '';
    if(currentCleanerMode === 'malware') {{
        html = currentCleanerItems.map((it, idx) => `
          <div class="p-3 rounded-lg ${{it.safe ? 'pro-card' : 'bg-red-950/40 border border-red-700'}} space-y-2 text-xs">
            <div class="flex justify-between items-center">
              <div class="flex items-center space-x-2 truncate">
                ${{it.safe ? '🟢' : '🚨'}} <span class="text-zinc-300 font-medium truncate max-w-md">${{it.original_name}}</span>
              </div>
              <span class="px-2 py-0.5 rounded text-[10px] font-bold font-tabular bg-white/[0.08] text-zinc-300">${{it.format}}</span>
            </div>
            ${{!it.safe ? `<div class="text-[11px] text-red-400 font-bold">${{it.threat_msg}}</div>` : ''}}
          </div>`).join('');
    }} else if (currentCleanerMode === 'edit') {{
        html = currentCleanerItems.filter(i => i.safe).map((it, idx) => `
          <div class="p-3 rounded-lg pro-card space-y-2 text-xs">
            <div class="flex justify-between items-center">
              <div class="flex items-center space-x-2 truncate">
                <input type="checkbox" id="chk_${{idx}}" ${{it.selected ? 'checked' : ''}} onchange="currentCleanerItems[${{idx}}].selected=this.checked" class="w-4 h-4 accent-red-600">
                <span class="text-zinc-300 font-medium truncate max-w-md">${{it.original_name}}</span>
              </div>
              <button onclick="fetch('/api/bridge/to_teaser?path=${{encodeURIComponent(it.path)}}',{{method:'POST'}});switchTab('video');" class="px-2 py-0.5 bg-red-950 text-red-300 border border-red-800 rounded text-[10px] font-bold transition hover:bg-red-600 hover:text-white">🎬 Zu Tab 1 (Teaser)</button>
            </div>
            <div class="grid grid-cols-12 gap-2 pt-1 border-t border-white/[0.06]">
               <div class="col-span-8"><input type="text" value="${{it.clean_name}}" oninput="currentCleanerItems[${{idx}}].clean_name=this.value" class="w-full bg-black border border-white/[0.1] p-1.5 rounded text-zinc-100 text-xs font-tabular focus:border-red-500 focus:outline-none"></div>
               <div class="col-span-4"><input type="text" value="${{it.genre}}" oninput="currentCleanerItems[${{idx}}].genre=this.value" class="w-full bg-black border border-white/[0.1] p-1.5 rounded text-zinc-100 text-xs font-medium focus:border-red-500 focus:outline-none"></div>
            </div>
          </div>`).join('');
    }} else if (currentCleanerMode === 'dupes') {{
         html = `<div class="text-center text-zinc-400 text-[11px] p-6 font-bold uppercase tracking-wider">Erkannte Duplikate werden in der linken Spalte gelistet.</div>`;
    }}
    document.getElementById('cleanerRows').innerHTML = html;
}}

function toggleSelectAllCleaner(){{ const v = currentCleanerItems.find(i=>i.safe) ? !currentCleanerItems.find(i=>i.safe).selected : true; currentCleanerItems.forEach((it, idx) => {{ if(it.safe){{ it.selected = v; const el = document.getElementById('chk_' + idx); if(el) el.checked = v; }} }}); }}
async function trashDuplicate(pathEnc, btn){{ btn.disabled = true; const res = await(await fetch('/api/cleaner/trash?path=' + pathEnc, {{ method: 'POST' }})).json(); showToast(res.message, res.status==='ok'?'success':'error'); startCleanerScan(); }}
async function executeCleanAndRename(){{
  const mods = currentCleanerItems.filter(i => i.safe && i.selected).map(i => ({{ path: i.path, new_name: i.clean_name, genre: i.genre }})); if(mods.length === 0) return;
  const res = await(await fetch('/api/cleaner/execute', {{ method: 'POST', body: JSON.stringify({{ modifications: mods }}) }})).json(); showToast(`✓ ${{res.renamed_count}} Dateien bereinigt!`, 'success'); startCleanerScan();
}}

// ==============================================================================
// 1-KLICK LIVE UPDATER LOGIK (REPARIERT)
// ==============================================================================
async function checkUpdate(){{
  const btn = document.getElementById('updBtn'), btnTxt = document.getElementById('updBtnText');
  btn.disabled = true; btnTxt.innerText = 'Prüfe...';
  try {{
    const res = await(await fetch('/api/check_update')).json();
    if(res.status === 'ok') {{
      if(res.update_available) {{
        document.getElementById('updBanner').classList.remove('hidden');
        document.getElementById('updMsg').innerText = `🚀 Neues Update verfügbar: v${{res.remote_version}} (Installiert: v${{res.current_version}})`;
        showToast(`Update verfügbar: v${{res.remote_version}}`, 'info');
      }} else {{
        showToast(`✓ Auf neuestem Stand (v${{res.current_version}})`, 'success');
        btnTxt.innerText = `✓ v${{res.current_version}}`;
        setTimeout(() => {{ btnTxt.innerText = 'Update suchen'; }}, 3000);
      }}
    }} else {{
      showToast('Update-Prüfung fehlgeschlagen: ' + (res.message || 'Offline'), 'error');
      btnTxt.innerText = 'Update suchen';
    }}
  }} catch(e) {{
    showToast('Verbindungsfehler beim Update-Check', 'error');
    btnTxt.innerText = 'Update suchen';
  }}
  btn.disabled = false;
}}

async function installUpdate(){{
  const btn = document.getElementById('updInstBtn');
  btn.disabled = true; btn.innerText = '⏳ Lade herunter...';
  try {{
    const res = await(await fetch('/api/install_update', {{ method: 'POST' }})).json();
    if(res.status === 'ok') {{
      showToast(res.message, 'success');
      btn.innerText = '✓ Installiert!';
      setTimeout(() => {{ window.location.reload(); }}, 2500);
    }} else {{
      showToast('Installationsfehler: ' + res.message, 'error');
      btn.disabled = false; btn.innerText = 'Jetzt installieren';
    }}
  }} catch(e) {{
    showToast('Fehler bei Update-Installation', 'error');
    btn.disabled = false; btn.innerText = 'Jetzt installieren';
  }}
}}
</script></body></html>"""

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    
    def check_origin(self):
        host = self.headers.get("Host", "")
        if not (host.startswith("127.0.0.1") or host.startswith("localhost")):
            self.send_response(403); self.end_headers(); return False
        return True
        
    def do_GET(self):
        if not self.check_origin(): return
        p = self.path.split("?")[0]
        if p in ("/", "/index.html"):
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(HTML.encode("utf-8"))
        elif p == "/api/status":
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(STATUS).encode("utf-8"))
        elif p == "/api/config":
            k = get_gemini_api_key()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps({"has_key": bool(k), "masked_key": f"{k[:6]}...{k[-4:]}" if len(k)>10 else "***"}).encode("utf-8"))
        elif p == "/api/check_update":
            try:
                req = urllib.request.Request(GITHUB_RAW_URL, headers={"User-Agent": "TECH-DUDE-CLIENT"})
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    remote_code = resp.read().decode("utf-8")
                    m = re.search(r'CURRENT_VERSION\s*=\s*["\']([^"\']+)["\']', remote_code)
                    if m:
                        remote_ver = m.group(1).strip()
                        update_avail = remote_ver != CURRENT_VERSION
                        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                        self.wfile.write(json.dumps({"status": "ok", "current_version": CURRENT_VERSION, "remote_version": remote_ver, "update_available": update_avail}).encode("utf-8"))
                        return
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "current_version": CURRENT_VERSION, "remote_version": CURRENT_VERSION, "update_available": False}).encode("utf-8"))
            except Exception as e:
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e), "current_version": CURRENT_VERSION}).encode("utf-8"))
        elif p == "/api/active_track":
            auds = sorted(glob.glob(os.path.join(VAULT, "*.mp3")) + glob.glob(os.path.join(VAULT, "*.wav")) + glob.glob(os.path.join(VAULT, "*.m4a")) + glob.glob(os.path.join(VAULT, "*.aiff")))
            if auds:
                curr_path = SHARED_STATE.get("active_track_file", "")
                if not curr_path or curr_path not in auds:
                    curr_path = auds[0]
                    SHARED_STATE["active_track_file"] = curr_path
                    
                vault_files = [os.path.basename(a) for a in auds]
                
                try: curr_mtime = os.path.getmtime(curr_path)
                except Exception: curr_mtime = 0
                
                if TRACK_CACHE["path"] == curr_path and TRACK_CACHE["mtime"] == curr_mtime and TRACK_CACHE["data"]:
                    res = TRACK_CACHE["data"]
                    res["vault_files"] = vault_files
                elif TRACK_CACHE["processing"]:
                    res = {"has_audio": True, "processing": True, "filename": "Analysiere...", "vault_files": vault_files, "waveform": []}
                else:
                    TRACK_CACHE["processing"] = True
                    info = analyze_track_details(curr_path)
                    res = {"has_audio": True, "processing": False, "filename": info["filename"], "vault_files": vault_files, "duration_sec": info["duration_sec"], "duration_str": info["duration_str"], "detected_bpm": info["detected_bpm"], "drop_sec": find_loudest_drop(curr_path), "waveform": extract_waveform_envelope(curr_path, 100)}
                    TRACK_CACHE.update({"path": curr_path, "mtime": curr_mtime, "data": res, "processing": False})
            else:
                TRACK_CACHE.update({"path": "", "data": None, "processing": False})
                res = {"has_audio": False, "processing": False, "filename": "", "vault_files": [], "duration_sec": 180.0, "duration_str": "--:--", "detected_bpm": 155.0, "drop_sec": 2.30, "waveform": []}
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(res).encode("utf-8"))
        elif p == "/api/pick_folder":
            try:
                apple_script = '''tell application "Finder"
                    activate
                    set myFolder to choose folder with prompt "Wähle einen Ordner zum Scannen:"
                    POSIX path of myFolder
                end tell'''
                res = subprocess.check_output(['osascript', '-e', apple_script]).decode('utf-8').strip()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps({"path": res}).encode("utf-8"))
            except Exception:
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps({"path": ""}).encode("utf-8"))
        elif p == "/api/folder":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            target = VAULT if q.get("t", [""])[0] == "vault" else EXPORT
            subprocess.Popen(["open", target])
            self.send_response(200); self.end_headers()
        elif p == "/api/reveal":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            fp = q.get("p", [""])[0]
            if fp and os.path.exists(fp): subprocess.Popen(["open", "-R", fp])
            self.send_response(200); self.end_headers()
        elif p == "/api/copy_vault":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            fp = q.get("path", [""])[0]
            if fp and os.path.exists(fp):
                dst = os.path.join(VAULT, os.path.basename(fp))
                shutil.copy2(fp, dst)
                SHARED_STATE["active_track_file"] = dst
                TRACK_CACHE["path"] = ""
            self.send_response(200); self.end_headers()
        elif p.startswith("/api/stream_video"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            video_path = q.get("p", [""])[0]
            if not video_path or not os.path.exists(video_path):
                self.send_response(404); self.end_headers(); return

            file_size = os.path.getsize(video_path)
            range_header = self.headers.get("Range", None)
            
            if range_header:
                range_match = re.search(r'bytes=(\d+)-(\d*)', range_header)
                if range_match:
                    start = int(range_match.group(1))
                    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
                    end = min(end, file_size - 1)
                    length = end - start + 1
                    
                    self.send_response(206)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Content-Length", str(length))
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    
                    with open(video_path, "rb") as f:
                        f.seek(start)
                        self.wfile.write(f.read(length))
                    return

            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            with open(video_path, "rb") as f: shutil.copyfileobj(f, self.wfile)
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if not self.check_origin(): return
        p = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        
        if p == "/api/upload":
            content_type = self.headers.get("Content-Type", "")
            if "boundary=" in content_type:
                boundary = content_type.split("boundary=")[1].strip()
                raw_bytes = self.rfile.read(length)
                boundary_bytes = ("--" + boundary).encode("utf-8")
                parts = raw_bytes.split(boundary_bytes)
                for part in parts:
                    if b'filename="' in part:
                        headers_raw, file_body = part.split(b"\r\n\r\n", 1)
                        m = re.search(rb'filename="([^"]+)"', headers_raw)
                        if m:
                            filename = m.group(1).decode("utf-8")
                            if file_body.endswith(b"\r\n"): file_body = file_body[:-2]
                            dest = os.path.join(VAULT, filename)
                            with open(dest, "wb") as f: f.write(file_body)
                            SHARED_STATE["active_track_file"] = dest
                            TRACK_CACHE["path"] = ""
            self.send_response(200); self.end_headers()
            return

        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        data = json.loads(body) if body else {}

        if p == "/api/config":
            cfg = load_user_config()
            new_key = data.get("gemini_api_key", "").strip()
            cfg["gemini_api_key"] = new_key
            save_user_config(cfg)
            test_resp = call_gemini_api("Antworte mit 'OK'", timeout=2.5) if new_key else None
            msg = "✓ Gemini Cloud-Brain Online!" if test_resp else ("Key gespeichert (Bunker-Fallback aktiv)" if new_key else "Key entfernt")
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "message": msg, "cloud_active": bool(test_resp)}).encode("utf-8"))
        elif p == "/api/install_update":
            try:
                req = urllib.request.Request(GITHUB_RAW_URL, headers={"User-Agent": "TECH-DUDE-UPDATER"})
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    new_code = resp.read().decode("utf-8")
                if "CURRENT_VERSION" in new_code and "APP_NAME" in new_code:
                    current_file = os.path.abspath(__file__)
                    with open(current_file, "w", encoding="utf-8") as f:
                        f.write(new_code)
                    
                    # Automatischer Server-Neustart in 1 Sekunde
                    def restart_daemon():
                        time.sleep(1.2)
                        os.execv(sys.executable, [sys.executable, current_file])
                    threading.Thread(target=restart_daemon, daemon=True).start()

                    self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok", "message": "✓ Update erfolgreich! Server startet neu..."}).encode("utf-8"))
                    return
                else:
                    self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                    self.wfile.write(json.dumps({"status": "error", "message": "Fehlerhafte Update-Datei auf GitHub."}).encode("utf-8"))
            except Exception as e:
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": f"Update fehlgeschlagen: {str(e)}"}).encode("utf-8"))
        elif p == "/api/set_active_track":
            fname = data.get("filename", "")
            target = os.path.join(VAULT, fname)
            if os.path.exists(target):
                SHARED_STATE["active_track_file"] = target
                TRACK_CACHE["path"] = ""
            self.send_response(200); self.end_headers()
        elif p == "/api/gemini/generate_hooks":
            hooks, mode = generate_viral_hooks(data.get("track", ""), data.get("bpm", 155), data.get("style", "warehouse"))
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps({"hooks": hooks, "source": mode}).encode("utf-8"))
        elif p == "/api/gemini/parse_notes":
            parsed, mode = parse_messy_tracklist_with_ai(data.get("raw_text", ""))
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps({"parsed": parsed, "source": mode}).encode("utf-8"))
        elif p == "/api/autopilot":
            bpm = float(data.get("bpm", 155.0))
            mode = data.get("mode", "turbo")
            threading.Thread(target=run_job, args=("warehouse", 1, "", True, "9:16", 16, None, bpm, mode)).start()
            self.send_response(200); self.end_headers()
        elif p == "/api/render":
            p_val = data.get("p", "warehouse")
            v_val = int(data.get("v", 1))
            h_val = data.get("hook", "")
            ret_val = bool(data.get("retention", True))
            fmt_val = data.get("fmt", "9:16")
            beats_val = int(data.get("beats", 16))
            bpm_val = float(data.get("bpm", 155.0))
            mode_val = data.get("mode", "turbo")
            drop_val = float(data.get("drop")) if data.get("drop") is not None else None
            threading.Thread(target=run_job, args=(p_val, v_val, h_val, ret_val, fmt_val, beats_val, drop_val, bpm_val, mode_val)).start()
            self.send_response(200); self.end_headers()
        elif p == "/api/crate_scan":
            res = parse_and_scan_crate(data.get("text", ""))
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(res).encode("utf-8"))
        elif p == "/api/crate_export":
            res = export_denon_m3u8(data.get("name", "Denon_Gig_Playlist"))
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(res).encode("utf-8"))
        elif p == "/api/cleaner/scan":
            f_target = data.get("folder", SHARED_STATE["active_folder"])
            res = scan_cleaner_folder(f_target)
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(res).encode("utf-8"))
        elif p == "/api/cleaner/execute":
            res = apply_cleaning_actions(data.get("modifications", []))
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(res).encode("utf-8"))
        elif p.startswith("/api/cleaner/trash"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            fp = q.get("path", [""])[0]
            res = trash_file_safely(fp)
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(res).encode("utf-8"))
        elif p == "/api/bridge/to_teaser":
            fp = data.get("path", "")
            if fp and os.path.exists(fp):
                dst = os.path.join(VAULT, os.path.basename(fp))
                if os.path.abspath(fp) != os.path.abspath(dst): shutil.copy2(fp, dst)
                SHARED_STATE["active_track_file"] = dst
                TRACK_CACHE["path"] = ""
            self.send_response(200); self.end_headers()
        else:
            self.send_response(404); self.end_headers()

def main():
    port = 8505
    server = ThreadedHTTPServer(("127.0.0.1", port), H)
    print(f"[{APP_NAME}] Master Server V{CURRENT_VERSION} läuft auf http://127.0.0.1:{port}")
    try: server.serve_forever()
    except KeyboardInterrupt: server.server_close()

if __name__ == "__main__":
    main()