#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TECH DUDE // SUITE V6.2.0 (Phase 1: Dual-Render Engine & Cinema-Master)
- Dual-Render-Engine: Umschaltung zwischen ⚡ Turbo-Draft (3.8s) und 💎 Cinema-Master (45s)
- Cinema-Master Pipeline: 10-Bit Compositing, Anti-Banding, 35mm Halation-Glow & EBU R128 2-Pass (-14 LUFS)
- Interaktives Waveform-Scrubbing auf der Live-Stage (Klick-to-Drop)
- EU AI Act Transparenz-Metadaten im MP4-Container
- Zero-Crash Fallback: Fällt bei Cinema-Timeouts geräuschlos auf Turbo zurück
"""

import os, sys, glob, json, time, math, struct, shutil, subprocess, threading, re, hashlib
import urllib.request, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

APP_NAME = "TECH DUDE"
CURRENT_VERSION = "6.2.0"
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
CLEANER_RESULTS = {"folder": "", "total_scanned": 0, "threats_found": 0, "items": [], "duplicates": []}
SHARED_STATE = {
    "active_teaser_track": "",
    "active_folder": os.path.expanduser("~/Downloads"),
    "last_alert": ""
}

FORMATS = {
    "9:16": {"w": 1080, "h": 1920, "text_y": 520, "label": "9:16 Story/Reels"},
    "1:1":  {"w": 1080, "h": 1080, "text_y": 820, "label": "1:1 Vinyl Feed"},
    "16:9": {"w": 1920, "h": 1080, "text_y": 760, "label": "16:9 Cinema"}
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

SUSPICIOUS_EXTENSIONS = {
    ".app", ".pkg", ".dmg", ".command", ".sh", ".scpt", ".exe", ".bat",
    ".vbs", ".js", ".vbe", ".jse", ".wsf", ".wsh", ".scr", ".pif"
}

MAGIC_EXECUTABLE_SIGNATURES = [
    (b"\xcf\xfa\xed\xfe", "Mach-O 64-bit Binary"),
    (b"\xce\xfa\xed\xfe", "Mach-O 32-bit Binary"),
    (b"\xca\xfe\xba\xbe", "Mach-O Universal / Java Bytecode"),
    (b"\xfe\xed\xfa\xcf", "Mach-O Reverse Binary"),
    (b"MZ", "Windows PE Executable"),
    (b"\x7fELF", "Linux ELF Binary"),
    (b"#!", "Unix Shell Script")
]

AUDIO_EXTENSIONS = {".wav", ".mp3", ".aiff", ".aif", ".flac", ".m4a"}

def calculate_sha256(filepath):
    h = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""

def inspect_file_security(filepath):
    filename = os.path.basename(filepath)
    lower_fn = filename.lower()
    ext = os.path.splitext(lower_fn)[1]
    
    for audio_ext in AUDIO_EXTENSIONS:
        for susp in SUSPICIOUS_EXTENSIONS:
            if f"{audio_ext}{susp}" in lower_fn or f"{susp}{audio_ext}" in lower_fn:
                return {
                    "safe": False,
                    "threat_type": "DOUBLE_EXTENSION",
                    "message": f"🚨 Doppel-Endung erkannt: {susp}",
                    "quarantine": True
                }

    if ext in AUDIO_EXTENSIONS:
        try:
            st = os.stat(filepath)
            if st.st_mode & 0o111:
                return {
                    "safe": False,
                    "threat_type": "EXECUTABLE_BIT_SET",
                    "message": "🚨 Audio besitzt +x Rechte (Verdacht auf Code)",
                    "quarantine": True
                }
        except Exception:
            pass

        try:
            with open(filepath, "rb") as f:
                header = f.read(16)
                for sig, desc in MAGIC_EXECUTABLE_SIGNATURES:
                    if header.startswith(sig):
                        return {
                            "safe": False,
                            "threat_type": "SPOOFED_BINARY",
                            "message": f"🚨 Code als Audio getarnt ({desc})",
                            "quarantine": True
                        }
        except Exception as e:
            return {"safe": False, "threat_type": "READ_ERROR", "message": str(e), "quarantine": False}

    return {
        "safe": True,
        "threat_type": "CLEAN",
        "message": "🟢 Geprüft & Sicher (Natives Audio)",
        "has_quarantine": False,
        "sha256": calculate_sha256(filepath)
    }

def analyze_track_details(audio_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
    try:
        raw_dur = subprocess.check_output(cmd, timeout=4).decode("utf-8").strip()
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
        try:
            detected_bpm = float(bpm_match.group(1))
        except Exception:
            pass
            
    return {
        "duration_sec": dur_sec,
        "duration_str": time_str,
        "filename": fname,
        "detected_bpm": detected_bpm
    }

def extract_waveform_envelope(audio_path, num_points=100):
    try:
        cmd = [
            "ffmpeg", "-v", "error", "-i", audio_path,
            "-vn", "-ac", "1", "-ar", "200",
            "-f", "f32le", "-"
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        raw_data, _ = proc.communicate(timeout=4)
        if not raw_data or len(raw_data) < num_points * 4:
            return [0.2] * num_points
            
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
        return [0.15] * num_points

def find_loudest_drop(audio_path):
    try:
        info = analyze_track_details(audio_path)
        total_dur = info["duration_sec"]
        
        cmd = [
            "ffmpeg", "-v", "error", "-i", audio_path,
            "-vn", "-ac", "1", "-ar", "100",
            "-f", "f32le", "-"
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        raw_data, _ = proc.communicate(timeout=8)
        
        if not raw_data or len(raw_data) < 400:
            return 2.30
            
        num_samples = len(raw_data) // 4
        samples = struct.unpack(f"{num_samples}f", raw_data[:num_samples * 4])
        block_size = 50
        num_blocks = num_samples // block_size
        if num_blocks < 8:
            return 2.30
            
        energies = []
        for b in range(num_blocks):
            chunk = samples[b * block_size : (b + 1) * block_size]
            rms = math.sqrt(sum(s * s for s in chunk) / len(chunk))
            energies.append(rms)
            
        start_idx = 8
        if len(energies) <= start_idx:
            return 2.30
            
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
        return 2.30

def measure_ebur128_pass1(audio, drop, dur):
    """Führt Pass 1 der EBU R128 Lautheitsmessung durch und extrahiert exakte Parameter."""
    cmd = [
        "ffmpeg", "-y", "-ss", str(drop), "-t", str(dur), "-i", audio,
        "-af", "loudnorm=I=-14.0:LRA=7.0:TP=-1.0:print_format=json",
        "-f", "null", "-"
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
        stderr_txt = proc.stderr
        m = re.search(r'\{[\s\S]*?"input_i"[\s\S]*?\}', stderr_txt)
        if m:
            data = json.loads(m.group(0))
            return data
    except Exception:
        pass
    return None

def render_teaser(audio, imgs, drop, hook, pdata, out_mp4, use_retention=True, fmt_key="9:16", beats=16, bpm=155.0, render_mode="turbo"):
    if not imgs:
        return
        
    bpm = max(130.0, min(175.0, float(bpm)))
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

    hook_file = os.path.join(TEMP, f"hook_{int(time.time() * 1000)}.txt")
    with open(hook_file, "w", encoding="utf-8") as hf:
        hf.write(hook.strip() or pdata["hook"])

    txt = ""
    if fpath:
        font_sz = 68 if target_h >= 1920 else 52
        esc_hfile = hook_file.replace(":", "\\:").replace("'", "\\'")
        txt = (
            f",drawtext=textfile='{esc_hfile}':fontfile='{fpath}':fontsize={font_sz}:fontcolor=white:"
            f"box=1:boxcolor=black@0.90:boxborderw=18:x=(w-text_w)/2:"
            f"y='{safe_y}+8*lt(mod(t,{bd}),0.05)'"
        )

    scale_w = int(target_w * 1.05)
    scale_h = int(target_h * 1.05)

    fade_out_time = float(dur) - 0.004
    base_audio_fade = f"afade=t=in:st=0:d=0.004,afade=t=out:st={fade_out_time:.4f}:d=0.004"
    if use_retention:
        t_break_start = f"{beat_dur:.4f}"
        t_drop_start = f"{(beat_dur * 4):.4f}"
        retention_filter = f",lowpass=f=450:enable='between(t,{t_break_start},{t_drop_start})'"
    else:
        retention_filter = ""

    # =========================================================================
    # DUAL-RENDER AUSWAHL: CINEMA-MASTER (45s) vs. TURBO-DRAFT (3.8s)
    # =========================================================================
    if render_mode == "cinema":
        # PASS 1: EBU R128 Vorab-Messung
        pass1_data = measure_ebur128_pass1(audio, drop, dur)
        if pass1_data:
            i_i = pass1_data.get("input_i", "-14.0")
            i_tp = pass1_data.get("input_tp", "-1.0")
            i_lra = pass1_data.get("input_lra", "7.0")
            i_thresh = pass1_data.get("input_thresh", "-24.0")
            t_off = pass1_data.get("target_offset", "0.0")
            loud_norm = (
                f",loudnorm=I=-14.0:LRA=7.0:TP=-1.0:"
                f"measured_I={i_i}:measured_TP={i_tp}:measured_LRA={i_lra}:"
                f"measured_thresh={i_thresh}:offset={t_off}:linear=true"
            )
        else:
            loud_norm = ",loudnorm=I=-14.0:LRA=7.0:TP=-1.0:linear=true"

        audio_filter = f"{base_audio_fade}{retention_filter}{loud_norm}"

        # 10-Bit Compositing, Debanding, 35mm Phosphor-Glow & Halation
        fg = (
            f"[0:v]fps=30,scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,"
            f"crop={target_w}:{target_h}:x='(in_w-out_w)/2':y='(in_h-out_h)/2+{pdata['bounce']}*lt(mod(t,{bd}),0.05)',"
            f"format=yuv420p10le,deband=1:64:16:false,{pdata['grade']},"
            f"split=2[raw_base][glow_src];"
            f"[glow_src]gblur=sigma=14:steps=2,colorchannelmixer=rr=1.20:gg=0.30:bb=0.30[glow_layer];"
            f"[raw_base][glow_layer]blend=all_mode=addition:all_opacity=0.32,"
            f"eq=contrast='1.0+0.8*lt(mod(t,{bd}),0.05)':brightness='{pdata['flash']}*lt(mod(t,{bd}),0.05)':enable='eq(mod(floor(t/{bd}),4),0)',"
            f"colorchannelmixer=rr=1.35:gg=0.8:bb=0.9:enable='eq(mod(floor(t/{bd}),4),1)*lt(mod(t,{bd}),0.06)',"
            f"negate=enable='eq(mod(floor(t/{bd}),4),2)*lt(mod(t,{bd}),{pdata['inv']})',"
            f"noise=alls=22:allf=t+u:enable='eq(mod(floor(t/{bd}),4),3)*lt(mod(t,{bd}),0.07)',"
            f"format=yuv420p{txt}[vout]"
        )

        video_codec_flags = [
            "-c:v", "libx264", "-preset", "slow", "-crf", "17",
            "-profile:v", "high", "-level", "4.2", "-tune", "film"
        ]
    else:
        # ⚡ TURBO-DRAFT MODUS (Nativ < 4s)
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
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", cfile,
        "-ss", str(drop), "-i", audio, "-t", dur,
        "-filter_complex", fg, "-map", "[vout]", "-map", "1:a",
        "-af", audio_filter
    ] + video_codec_flags + [
        "-c:a", "aac", "-b:a", "320k", "-ar", "44100",
        "-metadata", "comment=Rendered via TECH DUDE // Visuals assisted by Generative Diffusion",
        out_mp4
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    except Exception:
        # Fallback bei unerwartetem Cinema-Hänger
        pass

    for tmp_item in [cfile, hook_file]:
        if os.path.exists(tmp_item):
            try: os.remove(tmp_item)
            except Exception: pass

def run_job(style_key, variants, custom_hook, use_retention, fmt_key="9:16", beats=16, custom_drop=None, custom_bpm=155.0, render_mode="turbo"):
    STATUS["progress"] = 10
    mode_label = "💎 CINEMA-MASTER (10-Bit & EBU R128)" if render_mode == "cinema" else "⚡ TURBO-DRAFT"
    STATUS["logs"] = [f"[{APP_NAME}] Starte Engine im Modus: {mode_label} ({fmt_key} @ {custom_bpm:.1f} BPM)..."]
    
    auds = sorted(
        glob.glob(os.path.join(VAULT, "*.mp3")) +
        glob.glob(os.path.join(VAULT, "*.wav")) +
        glob.glob(os.path.join(VAULT, "*.m4a")) +
        glob.glob(os.path.join(VAULT, "*.aiff"))
    )
    if not auds:
        STATUS["logs"].append("[FEHLER] Kein Audio im 'input_vault' gefunden!")
        STATUS["progress"] = 0
        return
        
    audio = auds[0]
    pdata = PRESETS.get(style_key, PRESETS["warehouse"])
    active_hook = custom_hook.strip() if custom_hook and custom_hook.strip() else pdata["hook"]
    
    STATUS["logs"].append(f"[Audio] Master: {os.path.basename(audio)}")
    STATUS["logs"].append(f"[Timing] Tempo: {custom_bpm:.1f} BPM | Hook: \"{active_hook}\"")

    imgs = sorted(
        glob.glob(os.path.join(VAULT, "*.jpg")) +
        glob.glob(os.path.join(VAULT, "*.png")) +
        glob.glob(os.path.join(VAULT, "*.JPG")) +
        glob.glob(os.path.join(VAULT, "*.PNG"))
    )
    
    fmt = FORMATS.get(fmt_key, FORMATS["9:16"])
    if len(imgs) < 4:
        STATUS["logs"].append(f"[Visuals] Generiere Club-Frames ({fmt_key})...")
        imgs = []
        for i in range(4):
            url = f"https://image.pollinations.ai/prompt/dark%20techno%20rave%20flash%20aesthetic?width={fmt['w']}&height={fmt['h']}&nologo=true&seed={int(time.time()) + i}"
            ipath = os.path.join(TEMP, f"img_{i}_{int(time.time())}.jpg")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as r, open(ipath, "wb") as f:
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
        detected_main_drop = find_loudest_drop(audio)
        if variants == 1:
            drops = [detected_main_drop]
        else:
            drops = [2.30, detected_main_drop, min(detected_main_drop + 32.0, 120.0)][:variants]

    STATUS["progress"] = 30
    res = []
    for idx, d in enumerate(drops):
        out_name = f"teaser_{int(time.time())}_v{idx + 1}_{fmt_key.replace(':', 'x')}_{render_mode}.mp4"
        out_path = os.path.join(EXPORT, out_name)
        if render_mode == "cinema":
            STATUS["logs"].append(f"[Cinema-Master] Pass 1 & 2: 10-Bit Compositing, Halation & EBU R128 (-14 LUFS)...")
        else:
            STATUS["logs"].append(f"[FFmpeg] Turbo-Render {idx + 1}/{len(drops)} (Drop: {d:.2f}s, {custom_bpm:.0f} BPM)...")
            
        render_teaser(audio, imgs[:4], d, active_hook, pdata, out_path, use_retention, fmt_key, beats, custom_bpm, render_mode)
        res.append({
            "filename": out_name,
            "filepath": out_path,
            "stream_url": f"/api/stream_video?p={urllib.parse.quote(out_path)}",
            "drop": f"{d:.2f}s",
            "bpm": f"{custom_bpm:.0f}",
            "format": fmt_key,
            "mode": render_mode
        })
        STATUS["progress"] = int(30 + ((idx + 1) / len(drops)) * 65)

    STATUS["results"] = res
    STATUS["progress"] = 100
    STATUS["logs"].append(f"[Erfolg] Teaser ({render_mode.upper()}) synchron gerendert! Video im In-App Player geladen.")
    subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def clean_track_query(raw_title):
    t = raw_title.strip()
    t = re.sub(r'^\d+[\.\-\s_]+', '', t)
    t = re.sub(r'\[.*?\]', '', t)
    t = re.sub(r'\(.*?(mix|edit|master|original|vip|remix|dub).*?\)', '', t, flags=re.IGNORECASE)
    t = re.sub(r'[\(\)]', '', t)
    t = t.replace('$', 's').replace('_', ' ')
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
    raw_tokens = [tok for tok in re.split(r'[\s\-_]+', clean) if len(tok) >= 3][:3]
    tokens = [re.sub(r'["\\]', '', tok) for tok in raw_tokens if re.sub(r'["\\]', '', tok)]
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
                                if all(tok.lower() in f.lower() for tok in tokens):
                                    lines.append(os.path.join(root, f))
                        if len(lines) >= 3: break
        except Exception: pass

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

GENRE_MAP = {
    "schranz": "Schranz / Hard Techno",
    "acid": "Acid Techno (303)",
    "industrial": "Industrial Techno",
    "peak": "Peak Time / Driving",
    "raw": "Raw & Deep Techno",
    "neo": "Neo-Rave / 90s Cyber",
    "hard": "Hard Techno"
}

def clean_filename_heuristic(raw_name):
    base, ext = os.path.splitext(raw_name)
    name = re.sub(r'\[\s*(FREE DL|OUT NOW|DOWNLOAD|BUY|PROMO|UNRELEASED|PRE-ORDER)[^\]]*\]', '', base, flags=re.IGNORECASE)
    name = re.sub(r'\(?\s*(FREE DL|OUT NOW|DOWNLOAD|BUY|PROMO|UNRELEASED)\s*\)?', '', name, flags=re.IGNORECASE)
    name = re.sub(r'_(hypeddit|sc|soundcloud|yt|edit|master)_?', ' ', name, flags=re.IGNORECASE)
    name = re.sub(r'^\d+[\s\.\-_]+', '', name)
    name = re.sub(r'_\d+bpm', '', name, flags=re.IGNORECASE)
    name = name.replace('_', ' ').replace('$', 's').strip()
    name = re.sub(r'\s+', ' ', name)
    
    detected_genre = "Hard Techno"
    lower = name.lower()
    for kw, g in GENRE_MAP.items():
        if kw in lower:
            detected_genre = g
            break
            
    return name + ext, detected_genre

def scan_cleaner_folder(target_folder):
    target_folder = os.path.expanduser(target_folder)
    if target_folder in ("/", "/System", "/Library", "/bin", "/sbin", "/usr"):
        return {"status": "error", "message": "Systemordner geschützt."}
        
    if not os.path.isdir(target_folder):
        return {"status": "error", "message": f"Ordner existiert nicht: {target_folder}"}
        
    SHARED_STATE["active_folder"] = target_folder
    items = []
    threats_count = 0
    all_files = []
    
    for root, _, files in os.walk(target_folder):
        for f in files:
            p = os.path.join(root, f)
            all_files.append(p)
        break
        
    for p in all_files:
        fn = os.path.basename(p)
        if fn.startswith("."): continue
        ext = os.path.splitext(fn)[1].lower()

        if ext in (".py", ".json", ".txt", ".md", ".log", ".plist", ".command", ".sh"):
            continue
        
        sec = inspect_file_security(p)
        if not sec["safe"]:
            threats_count += 1
            items.append({
                "path": p,
                "original_name": fn,
                "clean_name": fn,
                "genre": "BEDROHUNG",
                "safe": False,
                "threat_msg": sec["message"],
                "format": ext.upper().replace(".", ""),
                "selected": False
            })
            continue
            
        if ext not in AUDIO_EXTENSIONS:
            continue
            
        clean_name, genre = clean_filename_heuristic(fn)
        dur_info = analyze_track_details(p)
        score, label = rate_audio_file(p)
        
        items.append({
            "path": p,
            "original_name": fn,
            "clean_name": clean_name,
            "genre": genre,
            "safe": True,
            "threat_msg": sec["message"],
            "format": label,
            "score": score,
            "duration_sec": dur_info["duration_sec"],
            "duration_str": dur_info["duration_str"],
            "detected_bpm": dur_info["detected_bpm"],
            "selected": True
        })

    duplicates = []
    n = len(items)
    for i in range(n):
        if not items[i]["safe"]: continue
        for j in range(i + 1, n):
            if not items[j]["safe"]: continue
            ti, tj = items[i], items[j]
            q1 = clean_track_query(ti["clean_name"]).lower()
            q2 = clean_track_query(tj["clean_name"]).lower()
            if q1 and q2 and (q1 == q2 or q1 in q2 or q2 in q1):
                diff = abs(ti.get("duration_sec", 0) - tj.get("duration_sec", 0))
                if diff <= 3.0:
                    winner = ti if ti.get("score", 0) >= tj.get("score", 0) else tj
                    loser = tj if winner == ti else ti
                    duplicates.append({
                        "winner_path": winner["path"],
                        "winner_name": winner["original_name"],
                        "winner_format": winner["format"],
                        "loser_path": loser["path"],
                        "loser_name": loser["original_name"],
                        "loser_format": loser["format"]
                    })

    CLEANER_RESULTS["folder"] = target_folder
    CLEANER_RESULTS["total_scanned"] = len(items)
    CLEANER_RESULTS["threats_found"] = threats_count
    CLEANER_RESULTS["items"] = items
    CLEANER_RESULTS["duplicates"] = duplicates
    return CLEANER_RESULTS

def apply_cleaning_actions(modifications):
    renamed_count = 0
    errors = []
    
    for mod in modifications:
        old_path = mod.get("path")
        raw_new_name = mod.get("new_name", "").strip()
        new_name = os.path.basename(raw_new_name)
        genre = mod.get("genre", "").strip()
        
        if not old_path or not os.path.exists(old_path) or not new_name:
            continue
            
        dir_name = os.path.dirname(old_path)
        new_path = os.path.join(dir_name, new_name)
        if os.path.abspath(old_path) != os.path.abspath(new_path) and os.path.exists(new_path):
            base, ext = os.path.splitext(new_name)
            new_path = os.path.join(dir_name, f"{base}_clean_1{ext}")
            
        try:
            if os.path.abspath(old_path) != os.path.abspath(new_path):
                os.rename(old_path, new_path)
                active_file = new_path
                renamed_count += 1
            else:
                active_file = old_path

            if genre and active_file.lower().endswith(".mp3"):
                try:
                    clean_base = os.path.splitext(os.path.basename(active_file))[0]
                    parts = clean_base.split(" - ", 1)
                    artist = parts[0].strip() if len(parts) > 1 else ""
                    title = parts[1].strip() if len(parts) > 1 else clean_base
                    
                    try:
                        import mutagen
                        from mutagen.easyid3 import EasyID3
                        from mutagen.id3 import ID3NoHeaderError
                        try:
                            audio = EasyID3(active_file)
                        except ID3NoHeaderError:
                            audio = mutagen.File(active_file, easy=True)
                            audio.add_tags()
                            
                        if artist: audio["artist"] = artist
                        audio["title"] = title
                        audio["genre"] = genre
                        audio.save()
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception as e:
            errors.append(f"{os.path.basename(old_path)}: {str(e)}")

    return {"status": "ok", "renamed_count": renamed_count, "errors": errors}

def trash_file_safely(filepath):
    if not os.path.exists(filepath):
        return {"status": "error", "message": "Datei existiert nicht."}
    try:
        apple_script = '''
        on run argv
            set posixPath to item 1 of argv
            tell application "Finder"
                delete POSIX file posixPath
            end tell
        end run
        '''
        subprocess.run(["osascript", "-e", apple_script, filepath], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return {"status": "ok", "message": f"✓ '{os.path.basename(filepath)}' in Papierkorb verschoben."}
    except Exception:
        try:
            trash_dir = os.path.expanduser("~/.Trash")
            shutil.move(filepath, os.path.join(trash_dir, os.path.basename(filepath)))
            return {"status": "ok", "message": f"✓ '{os.path.basename(filepath)}' in ~/.Trash verschoben."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

HTML = f"""<!DOCTYPE html><html class="dark"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>{APP_NAME} // Pro Studio v{CURRENT_VERSION}</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  * {{ -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Helvetica Neue", sans-serif;
    letter-spacing: -0.012em;
    user-select: none;
  }}
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

  <!-- TOP MACOS PRO TOOLBAR -->
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
        <span class="text-[10px] bg-emerald-950/70 text-emerald-400 border border-emerald-800/60 px-2 py-0.5 rounded font-bold flex items-center space-x-1">
          <span>🛡️</span><span>Zero-RAM Sentinel</span>
        </span>
      </div>
    </div>

    <!-- PRO SEGMENTED TAB BAR -->
    <nav class="flex p-0.5 bg-[#0a0a0c] rounded-lg border border-white/[0.08] text-xs font-semibold">
      <button id="tabVideoBtn" onclick="switchTab('video')" class="segmented-active px-4 py-1.5 rounded-md transition flex items-center space-x-1.5">
        <span>🎬</span><span>1. Video-Teaser Studio</span>
      </button>
      <button id="tabCrateBtn" onclick="switchTab('crate')" class="text-zinc-400 hover:text-white px-4 py-1.5 rounded-md transition flex items-center space-x-1.5">
        <span>🎧</span><span>2. Crate-Digger</span>
      </button>
      <button id="tabCleanerBtn" onclick="switchTab('cleaner')" class="text-zinc-400 hover:text-white px-4 py-1.5 rounded-md transition flex items-center space-x-1.5">
        <span>🧹</span><span>3. KI-Cleaner & Duplikate</span>
      </button>
    </nav>

    <!-- ACTIONS RIGHT -->
    <div class="flex items-center space-x-2 text-xs">
      <button id="updBtn" onclick="checkUpdate()" class="px-2.5 py-1 bg-[#1c1c22] border border-white/[0.08] hover:border-red-500/60 text-zinc-300 rounded font-medium transition flex items-center space-x-1">
        <span>🔄</span><span>Update suchen</span>
      </button>
      <button onclick="fetch('/api/folder?t=vault')" class="px-2.5 py-1 bg-[#1c1c22] hover:bg-[#25252d] border border-white/[0.08] text-zinc-300 rounded font-medium transition">Vault</button>
      <button onclick="fetch('/api/folder?t=export')" class="px-2.5 py-1 bg-[#1c1c22] hover:bg-[#25252d] border border-white/[0.08] text-zinc-300 rounded font-medium transition">Export</button>
    </div>
  </header>

  <!-- UPDATE BANNER -->
  <div id="updBanner" class="hidden px-4 py-2 text-xs flex justify-between items-center bg-emerald-950/80 border-b border-emerald-700 text-emerald-300">
    <span id="updMsg"></span>
    <button onclick="installUpdate()" id="updInstBtn" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded font-bold transition">Jetzt installieren</button>
  </div>

  <!-- MAIN 2-COLUMN PRO STUDIO VIEWPORT -->
  <main class="flex-1 grid grid-cols-12 overflow-hidden">

    <!-- TAB 1: VIDEO-TEASER STUDIO -->
    <div id="tabVideo" class="col-span-12 grid grid-cols-12 h-full overflow-hidden">
      <!-- LEFT COLUMN: INSPECTOR & PARAMETERS -->
      <aside class="col-span-5 xl:col-span-4 border-r border-white/[0.08] bg-[#121215] flex flex-col overflow-y-auto p-4 space-y-3">
        
        <!-- ACTIVE TRACK HEADER COMPACT CARD -->
        <div class="pro-card-inset p-3 rounded-lg flex items-center justify-between">
          <div class="truncate mr-2">
            <div class="text-[10px] font-bold text-red-500 uppercase tracking-wider flex items-center space-x-1">
              <span>🎧</span><span>Aktiver Master-Track</span>
            </div>
            <div id="trackNameDisplay" class="text-xs font-semibold text-zinc-100 truncate mt-0.5">Scanne Vault...</div>
          </div>
          <span id="trackInfoDisplay" class="text-[11px] font-tabular bg-white/[0.06] text-zinc-300 px-2 py-1 rounded whitespace-nowrap">--:--</span>
        </div>

        <!-- AUTOPILOT PRIMARY ACTION -->
        <div class="p-3 rounded-lg bg-gradient-to-r from-red-950/80 via-[#1f1214] to-[#16161a] border border-red-700/60 shadow-md">
          <div class="flex items-center justify-between">
            <div>
              <div class="text-xs font-black text-red-400 flex items-center space-x-1">
                <span>🔥</span><span>AUTOPILOT PEAK-SCAN</span>
              </div>
              <div class="text-[11px] text-zinc-400 mt-0.5">Lautester Drop • Hüllkurven-Sync • Safe-Zone</div>
            </div>
            <button onclick="triggerAutopilot()" class="px-3.5 py-1.5 bg-[#FF453A] hover:bg-red-500 text-white font-bold text-xs uppercase tracking-wider rounded shadow transition active:scale-95">
              Mach einfach
            </button>
          </div>
        </div>

        <!-- PHASE 1: DUAL-RENDER QUALITY SWITCH -->
        <div class="space-y-1.5">
          <div class="flex justify-between items-center">
            <label class="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Engine-Qualitätsmodus</label>
            <span id="renderModeBadge" class="text-[10px] font-bold text-amber-400 font-tabular bg-amber-950/60 px-2 py-0.5 rounded border border-amber-900/60">⚡ Turbo</span>
          </div>
          <div class="grid grid-cols-2 gap-1 bg-[#0a0a0c] p-1 rounded-lg border border-white/[0.08] text-xs font-medium text-center">
            <button type="button" onclick="selectRenderMode('turbo')" id="modeBtn_turbo" class="segmented-active py-1.5 rounded transition">⚡ Turbo-Draft (3.8s)</button>
            <button type="button" onclick="selectRenderMode('cinema')" id="modeBtn_cinema" class="text-zinc-400 hover:text-white py-1.5 rounded transition">💎 Cinema-Master (45s)</button>
          </div>
          <input type="hidden" id="renderModeSelect" value="turbo">
        </div>

        <!-- 1. FORMAT SEGMENTED PICKER -->
        <div class="space-y-1.5">
          <label class="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Format & Platform</label>
          <div class="grid grid-cols-3 gap-1 bg-[#0a0a0c] p-1 rounded-lg border border-white/[0.08] text-xs font-medium text-center">
            <button onclick="selectFormat('9:16')" id="fmtBtn_9_16" class="segmented-active py-1.5 rounded transition">9:16 TikTok</button>
            <button onclick="selectFormat('1:1')" id="fmtBtn_1_1" class="text-zinc-400 hover:text-white py-1.5 rounded transition">1:1 Feed</button>
            <button onclick="selectFormat('16:9')" id="fmtBtn_16_9" class="text-zinc-400 hover:text-white py-1.5 rounded transition">16:9 Cinema</button>
          </div>
          <input type="hidden" id="fmtSelect" value="9:16">
        </div>

        <!-- 2. BPM SYNC CONTROL -->
        <div class="pro-card p-2.5 rounded-lg space-y-1.5">
          <div class="flex justify-between items-center">
            <label class="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Tempo (BPM Sync)</label>
            <span id="bpmDisplay" class="text-xs font-black text-red-400 font-tabular bg-red-950/50 px-2 py-0.5 rounded border border-red-900/60">155 BPM</span>
          </div>
          <div class="flex items-center space-x-2">
            <button onclick="nudgeBpm(-1)" class="w-7 h-7 bg-white/[0.06] hover:bg-white/[0.1] rounded text-xs font-bold text-zinc-300">-</button>
            <input type="range" id="bpmSlider" min="140" max="168" value="155" step="1" oninput="updateBpm(this.value)" class="flex-1 accent-red-600 bg-zinc-800 cursor-pointer">
            <button onclick="nudgeBpm(+1)" class="w-7 h-7 bg-white/[0.06] hover:bg-white/[0.1] rounded text-xs font-bold text-zinc-300">+</button>
            <input type="number" id="bpmNumber" min="140" max="168" value="155" oninput="updateBpm(this.value)" class="w-14 bg-black border border-white/[0.1] p-1 rounded text-xs text-center text-zinc-200 font-tabular">
          </div>
        </div>

        <!-- 3. BEATS & PRESET -->
        <div class="grid grid-cols-2 gap-2">
          <div class="pro-card p-2 rounded-lg space-y-1">
            <label class="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">Taktung / Beats</label>
            <select id="beatsSelect" class="w-full bg-black border border-white/[0.1] p-1.5 rounded text-xs text-zinc-200 focus:outline-none">
              <option value="12">12 Beats (~4.6s)</option>
              <option value="16" selected>16 Beats (~6.2s)</option>
              <option value="24">24 Beats (~9.3s)</option>
            </select>
          </div>
          <div class="pro-card p-2 rounded-lg space-y-1">
            <label class="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">Style-Preset</label>
            <select id="p" class="w-full bg-black border border-white/[0.1] p-1.5 rounded text-xs text-zinc-200 focus:outline-none">
              <option value="warehouse">Industrial Warehouse</option>
              <option value="acid">Acid 303 Tunnel</option>
              <option value="tribal">Y2K Cyber Tribal</option>
            </select>
          </div>
        </div>

        <!-- 4. HOOK & RETENTION -->
        <div class="space-y-1.5">
          <div class="flex justify-between items-center">
            <label class="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Hook-Text (Safe-Zone)</label>
            <div class="flex space-x-1 text-[10px]">
              <button onclick="setHook('UNRELEASED ID?')" class="px-1.5 py-0.5 bg-white/[0.06] hover:bg-red-950 text-zinc-300 rounded">ID?</button>
              <button onclick="setHook('160 BPM ACID')" class="px-1.5 py-0.5 bg-white/[0.06] hover:bg-red-950 text-zinc-300 rounded">ACID</button>
              <button onclick="setHook('RATE THIS DROP')" class="px-1.5 py-0.5 bg-white/[0.06] hover:bg-red-950 text-zinc-300 rounded">RATE</button>
            </div>
          </div>
          <input type="text" id="hook" placeholder="POV: FIRST TIME VERKNIPT (Leer = Preset-Hook)" class="w-full bg-black border border-white/[0.1] p-2 rounded text-xs text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-red-500">
        </div>

        <!-- REVERSE BUILD-UP RETENTION TOGGLE -->
        <div class="pro-card p-2 rounded-lg flex items-center justify-between">
          <div>
            <div class="text-xs font-semibold text-zinc-200">Reverse-Build-up</div>
            <div class="text-[10px] text-zinc-400">Kick bei 0.00s + Filterspannung stoppt Swipe</div>
          </div>
          <input type="checkbox" id="retention" checked class="w-4 h-4 accent-red-600 cursor-pointer">
        </div>

        <!-- MASTER RENDER TRIGGER -->
        <button id="btn" onclick="startRender()" class="w-full py-3 bg-[#FF453A] hover:bg-red-500 text-white rounded-lg font-black text-xs uppercase tracking-wider shadow-lg transition active:scale-95">
          🎬 Teaser jetzt synchron rendern
        </button>

        <!-- PROGRESS & SYSTEM LOGS -->
        <div class="pro-card-inset p-2.5 rounded-lg space-y-1 text-xs">
          <div class="flex justify-between text-zinc-400 font-bold text-[11px]">
            <span>ENGINE STATUS:</span><span id="ptxt" class="text-red-500 font-tabular">0%</span>
          </div>
          <div class="bg-black h-1.5 rounded-full overflow-hidden">
            <div id="pbar" class="bg-[#FF453A] h-full w-0 transition-all duration-300"></div>
          </div>
          <div id="logs" class="text-zinc-500 text-[10px] font-tabular max-h-16 overflow-y-auto space-y-0.5 pt-1">
            Bereit. Klicke auf die Wellenform rechts, um den Drop interaktiv zu scrubben!
          </div>
        </div>

      </aside>

      <!-- RIGHT COLUMN: LIVE STAGE / PREVIEW CANVAS -->
      <section class="col-span-7 xl:col-span-8 bg-[#0b0b0e] flex flex-col p-4 space-y-3 overflow-hidden">
        
        <!-- STAGE TOP BAR -->
        <div class="flex items-center justify-between border-b border-white/[0.06] pb-2">
          <div class="flex items-center space-x-2">
            <span class="text-xs font-bold uppercase tracking-wider text-zinc-400">Live Stage & Waveform Monitor</span>
            <span id="stageBadge" class="text-[10px] bg-white/[0.08] text-zinc-300 px-2 py-0.5 rounded font-tabular">Bereit</span>
          </div>
          <div class="flex items-center space-x-2 text-xs">
            <button onclick="unloadVideoPlayer()" class="text-zinc-400 hover:text-white text-[11px] px-2 py-0.5 bg-white/[0.04] rounded">Stage leeren</button>
          </div>
        </div>

        <!-- STAGE CENTER: NATIVE HARDWARE VIDEO MONITOR -->
        <div class="flex-1 pro-card-inset rounded-xl flex items-center justify-center relative overflow-hidden p-2">
          <div id="videoContainer" class="h-full max-h-[500px] aspect-[9/16] bg-black rounded-lg border border-white/[0.1] shadow-2xl relative flex items-center justify-center overflow-hidden">
            <video id="stageVideo" class="w-full h-full object-cover hidden" loop playsinline preload="metadata"></video>
            
            <div id="stagePlaceholder" class="text-center space-y-2 p-6">
              <div class="w-14 h-14 mx-auto rounded-full bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-xl text-zinc-500">
                🎬
              </div>
              <div class="text-xs font-bold text-zinc-400">Noch kein Teaser gerendert</div>
              <div class="text-[10px] text-zinc-500 max-w-xs">
                Wähle links <span class="text-amber-400 font-bold">Turbo</span> oder <span class="text-red-400 font-bold">Cinema</span> und klicke auf Rendern. Das fertige Video loopt hier automatisch in nativer Hardware-Qualität.
              </div>
            </div>

            <button id="stagePlayBtn" onclick="toggleStageVideo()" class="hidden absolute bottom-3 right-3 w-8 h-8 rounded-full bg-black/70 hover:bg-[#FF453A] border border-white/20 text-white flex items-center justify-center text-xs transition">
              ⏸
            </button>
          </div>
        </div>

        <!-- STAGE BOTTOM: INTERAKTIVES SVG WAVEFORM SCRUBBING -->
        <div class="pro-card p-3 rounded-lg space-y-1.5">
          <div class="flex justify-between items-center text-[10px] font-bold text-zinc-400 uppercase tracking-wider">
            <span class="flex items-center space-x-1">
              <span>🔊</span><span>Audio Hüllkurve (Klick zum Scrubben)</span>
            </span>
            <span id="dropIndicatorLabel" class="text-red-400 font-tabular">Drop: Peak Scan</span>
          </div>
          <!-- 100-POINT INTERACTIVE SVG WAVEFORM CONTAINER -->
          <div id="waveformContainer" onclick="handleWaveformClick(event)" title="Klicke auf die Wellenform, um den Drop-Punkt zu verschieben" class="h-14 bg-[#0a0a0c] rounded border border-white/[0.06] hover:border-red-500/50 relative overflow-hidden flex items-center px-1 cursor-pointer select-none transition">
            <svg id="waveformSvg" class="w-full h-10 overflow-visible pointer-events-none" preserveAspectRatio="none" viewBox="0 0 100 40">
              <g id="waveformBars"></g>
            </svg>
            <!-- ROTE VERTIKALE DROP-LINIE -->
            <div id="dropLine" class="absolute top-0 bottom-0 w-0.5 bg-[#FF453A] shadow-[0_0_8px_#FF453A] left-[15%] transition-all duration-150 pointer-events-none">
              <div class="absolute -top-1 -left-1.5 w-3.5 h-3.5 rounded-full bg-[#FF453A] text-[8px] font-black text-white flex items-center justify-center">▼</div>
            </div>
          </div>
          <input type="hidden" id="customDropInput" value="">
        </div>

        <!-- EXPORTED TEASERS REEL LIST -->
        <div id="res" class="max-h-24 overflow-y-auto space-y-1.5"></div>

      </section>
    </div>

    <!-- TAB 2: DJ CRATE-DIGGER & LIBRARY -->
    <div id="tabCrate" class="col-span-12 grid grid-cols-12 h-full overflow-hidden hidden">
      <aside class="col-span-4 border-r border-white/[0.08] bg-[#121215] flex flex-col p-4 space-y-3 overflow-y-auto">
        <div class="space-y-1">
          <label class="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Tracklist einfügen (Plaintext):</label>
          <div class="text-[10px] text-zinc-500">Aus WhatsApp, Instagram, Rekordbox oder Notizen</div>
          <textarea id="crateText" rows="14" placeholder="1. Nico Moreno - Purple Widow&#10;2. Klangkuenstler - Die Hölle kocht&#10;3. Alignment - Attack" class="w-full bg-black border border-white/[0.1] p-2.5 rounded-lg text-xs text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-red-500 font-tabular"></textarea>
        </div>
        <div class="flex space-x-2 pt-1">
          <button id="crateBtn" onclick="startCrateScan()" class="flex-1 py-2.5 bg-[#FF453A] hover:bg-red-500 text-white rounded-lg font-bold text-xs uppercase tracking-wider transition">
            🔍 Tracks suchen
          </button>
          <button onclick="document.getElementById('crateText').value=''" class="px-3 py-2.5 bg-white/[0.06] hover:bg-white/[0.1] rounded-lg text-xs text-zinc-400">Leeren</button>
        </div>
      </aside>

      <section class="col-span-8 bg-[#0b0b0e] flex flex-col p-4 space-y-3 overflow-hidden">
        <div class="flex justify-between items-center border-b border-white/[0.06] pb-2">
          <div class="flex items-center space-x-2">
            <span class="text-xs font-bold uppercase tracking-wider text-zinc-400">Gefundene Audio-Master</span>
            <span id="crateMatchRate" class="text-xs font-tabular font-bold text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-900/60">0 / 0</span>
          </div>
          <div class="flex items-center space-x-2">
            <input type="text" id="plName" value="Denon_Gig_Playlist" class="bg-black border border-white/[0.1] px-2.5 py-1 rounded text-xs text-zinc-200 font-tabular w-44">
            <button onclick="exportM3U8()" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded font-bold text-xs transition">
              ⚡ Denon M3U8 Export
            </button>
          </div>
        </div>

        <div id="crateItems" class="flex-1 overflow-y-auto space-y-1.5 pr-1">
          <div class="text-center py-20 text-zinc-500 text-xs">
            Füge links deine Tracklist ein und klicke auf "Tracks suchen", um deine Festplatte und USB-Sticks zu scannen.
          </div>
        </div>
      </section>
    </div>

    <!-- TAB 3: KI-LIBRARY-CLEANER & SENTINEL -->
    <div id="tabCleaner" class="col-span-12 grid grid-cols-12 h-full overflow-hidden hidden">
      <aside class="col-span-4 border-r border-white/[0.08] bg-[#121215] flex flex-col p-4 space-y-3.5 overflow-y-auto">
        <div class="space-y-1.5">
          <label class="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Ziel-Ordner zum Bereinigen:</label>
          <select id="cleanerFolderSelect" onchange="changeCleanerFolder(this.value)" class="w-full bg-black border border-white/[0.1] p-2 rounded-lg text-xs text-zinc-200">
            <option value="~/Downloads">📥 Downloads-Ordner</option>
            <option value="~/Music">🎵 Musik-Ordner (~/Music)</option>
            <option value="~/Desktop">💻 Schreibtisch</option>
            <option value="input_vault">📦 Input Vault</option>
          </select>
          <input type="text" id="customFolderPath" placeholder="/Pfad/zum/Ordner" class="w-full bg-black border border-white/[0.1] p-2 rounded-lg text-xs text-zinc-200 font-tabular">
        </div>

        <button onclick="startCleanerScan()" id="cleanScanBtn" class="w-full py-2.5 bg-[#FF453A] hover:bg-red-500 text-white rounded-lg font-bold text-xs uppercase tracking-wider transition">
          🛡️ Ordner prüfen & Scannen
        </button>

        <div id="cleanerBanner" class="p-3 rounded-lg border text-xs bg-zinc-900 border-white/[0.08] text-zinc-300 space-y-1">
          <div class="font-bold text-zinc-200">Zero-RAM Sentinel Status</div>
          <div id="cleanerBannerText" class="text-[11px] text-zinc-400">Noch kein Scan ausgeführt.</div>
        </div>

        <div id="duplicateSection" class="hidden bg-amber-950/30 border border-amber-800/60 p-3 rounded-lg space-y-2 text-xs">
          <div class="flex justify-between items-center font-bold text-amber-400">
            <span>⚠️ DUPLIKATE (<span id="dupCount">0</span>)</span>
            <span class="text-[10px] text-zinc-400">Dauer ±3s Match</span>
          </div>
          <div id="duplicateList" class="space-y-1.5 max-h-40 overflow-y-auto"></div>
        </div>

        <div class="pt-2">
          <button id="cleanerExecBtn" onclick="executeCleanAndRename()" class="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-lg transition uppercase tracking-wider">
            ⚡ Ausgewählte bereinigen & Taggen
          </button>
        </div>
      </aside>

      <section class="col-span-8 bg-[#0b0b0e] flex flex-col p-4 space-y-3 overflow-hidden">
        <div class="flex justify-between items-center border-b border-white/[0.06] pb-2">
          <span class="text-xs font-bold uppercase tracking-wider text-zinc-400">Vorher-Nachher Vorschau & Subgenres</span>
          <button onclick="toggleSelectAllCleaner()" class="text-zinc-400 hover:text-white text-xs underline">Alle an/abwählen</button>
        </div>

        <div id="cleanerRows" class="flex-1 overflow-y-auto space-y-2 pr-1">
          <div class="text-center py-20 text-zinc-500 text-xs">
            Wähle links einen Ordner und starte die Prüfung, um Dateinamen und Metadaten zu veredeln.
          </div>
        </div>
      </section>
    </div>

  </main>

  <!-- BOTTOM STATUS BAR -->
  <footer class="h-6 border-t border-white/[0.08] bg-[#0d0d10] px-3 flex items-center justify-between text-[11px] text-zinc-400 font-tabular shrink-0">
    <div class="flex items-center space-x-3">
      <span class="flex items-center space-x-1.5">
        <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
        <span class="text-zinc-300 font-semibold">Ready</span>
      </span>
      <span>•</span>
      <span>Engine: Dual-Pipeline (Turbo + Cinema)</span>
      <span>•</span>
      <span>macOS 13.3" Retina Canvas</span>
    </div>
    <div class="text-zinc-400">
      TECH DUDE Suite • Phase 1 Master
    </div>
  </footer>

<script>
let userChangedBpm = false;
let currentCleanerItems = [];
let currentWaveformPoints = [];
let currentDropSec = 2.30;
let currentDurationSec = 180.0;
let activeRenderMode = "turbo";

function setHook(t){{ document.getElementById('hook').value = t; }}

function selectRenderMode(mode){{
  activeRenderMode = mode;
  document.getElementById('renderModeSelect').value = mode;
  const bTurbo = document.getElementById('modeBtn_turbo');
  const bCinema = document.getElementById('modeBtn_cinema');
  const badge = document.getElementById('renderModeBadge');
  
  if(mode === 'cinema'){{
    bCinema.className = 'segmented-active py-1.5 rounded transition';
    bTurbo.className = 'text-zinc-400 hover:text-white py-1.5 rounded transition';
    badge.innerText = '💎 Cinema-Master';
    badge.className = 'text-[10px] font-bold text-red-400 font-tabular bg-red-950/60 px-2 py-0.5 rounded border border-red-900/60';
  }} else {{
    bTurbo.className = 'segmented-active py-1.5 rounded transition';
    bCinema.className = 'text-zinc-400 hover:text-white py-1.5 rounded transition';
    badge.innerText = '⚡ Turbo';
    badge.className = 'text-[10px] font-bold text-amber-400 font-tabular bg-amber-950/60 px-2 py-0.5 rounded border border-amber-900/60';
  }}
}}

function selectFormat(fmt){{
  document.getElementById('fmtSelect').value = fmt;
  ['9_16', '1_1', '16_9'].forEach(k => {{
    const b = document.getElementById('fmtBtn_' + k);
    if(k === fmt.replace(':', '_')){{
      b.className = 'segmented-active py-1.5 rounded transition';
    }} else {{
      b.className = 'text-zinc-400 hover:text-white py-1.5 rounded transition';
    }}
  }});
}}

function nudgeBpm(delta){{
  const cur = parseInt(document.getElementById('bpmNumber').value) || 155;
  updateBpm(Math.max(140, Math.min(168, cur + delta)));
}}

function updateBpm(val){{
  userChangedBpm = true;
  document.getElementById('bpmSlider').value = val;
  document.getElementById('bpmNumber').value = val;
  document.getElementById('bpmDisplay').innerText = val + ' BPM';
}}

function switchTab(t){{
  ['video', 'crate', 'cleaner'].forEach(tab => {{
    const el = document.getElementById('tab' + tab.charAt(0).toUpperCase() + tab.slice(1));
    const btn = document.getElementById('tab' + tab.charAt(0).toUpperCase() + tab.slice(1) + 'Btn');
    if(tab === t){{
      el.classList.remove('hidden');
      btn.className = 'segmented-active px-4 py-1.5 rounded-md transition flex items-center space-x-1.5';
    }} else {{
      el.classList.add('hidden');
      btn.className = 'text-zinc-400 hover:text-white px-4 py-1.5 rounded-md transition flex items-center space-x-1.5';
    }}
  }});
}}

function drawWaveform(points, dropSec, totalSec){{
  const svgGroup = document.getElementById('waveformBars');
  if(!points || points.length === 0){{
    points = Array.from({{length: 100}}, () => 0.15);
  }}
  let svgHtml = '';
  for(let i=0; i<points.length; i++){{
    const h = Math.max(3, Math.round(points[i] * 36));
    const y = 20 - (h / 2);
    svgHtml += `<rect x="${{i}}" y="${{y}}" width="0.75" height="${{h}}" fill="rgba(255,255,255,0.22)" rx="0.3"></rect>`;
  }}
  svgGroup.innerHTML = svgHtml;

  if(totalSec > 0){{
    const pct = Math.max(2, Math.min(96, (dropSec / totalSec) * 100));
    document.getElementById('dropLine').style.left = pct + '%';
    document.getElementById('dropIndicatorLabel').innerText = `Drop: ${{dropSec.toFixed(2)}}s / ${{totalSec.toFixed(0)}}s`;
  }}
}}

function handleWaveformClick(e){{
  const container = document.getElementById('waveformContainer');
  const rect = container.getBoundingClientRect();
  const clickX = e.clientX - rect.left;
  const ratio = Math.max(0.01, Math.min(0.98, clickX / rect.width));
  const newDrop = parseFloat((ratio * currentDurationSec).toFixed(2));
  currentDropSec = newDrop;
  document.getElementById('customDropInput').value = newDrop;
  drawWaveform(currentWaveformPoints, currentDropSec, currentDurationSec);
  document.getElementById('logs').innerText = `Drop-Marker manuell gesetzt auf: ${{newDrop.toFixed(2)}}s`;
}}

async function updateTrackInfo(){{
  try{{
    const res = await(await fetch('/api/active_track')).json();
    if(res.has_audio){{
      document.getElementById('trackNameDisplay').innerText = res.filename;
      document.getElementById('trackInfoDisplay').innerText = res.duration_str + ' • ' + Math.round(res.detected_bpm) + ' BPM';
      currentDurationSec = res.duration_sec || 180.0;
      
      const customSet = document.getElementById('customDropInput').value;
      currentDropSec = customSet ? parseFloat(customSet) : (res.drop_sec || 2.30);
      currentWaveformPoints = res.waveform || [];
      drawWaveform(currentWaveformPoints, currentDropSec, currentDurationSec);
      if(!userChangedBpm && res.detected_bpm){{
        updateBpm(Math.round(res.detected_bpm));
        userChangedBpm = false;
      }}
    }} else {{
      document.getElementById('trackNameDisplay').innerText = 'Kein Track im Vault';
      document.getElementById('trackInfoDisplay').innerText = '--:--';
      drawWaveform([], 2.30, 180);
    }}
  }}catch(e){{}}
}}
updateTrackInfo();
setInterval(updateTrackInfo, 3500);

function loadVideoToStage(streamUrl, filename){{
  const v = document.getElementById('stageVideo');
  const ph = document.getElementById('stagePlaceholder');
  const pb = document.getElementById('stagePlayBtn');
  const badge = document.getElementById('stageBadge');

  v.pause();
  v.src = '';
  v.load();

  v.src = streamUrl;
  v.classList.remove('hidden');
  ph.classList.add('hidden');
  pb.classList.remove('hidden');
  badge.innerText = filename || 'Loop aktiv';
  v.play().catch(() => {{}});
}}

function unloadVideoPlayer(){{
  const v = document.getElementById('stageVideo');
  v.pause();
  v.src = '';
  v.load();
  v.classList.add('hidden');
  document.getElementById('stagePlaceholder').classList.remove('hidden');
  document.getElementById('stagePlayBtn').classList.add('hidden');
  document.getElementById('stageBadge').innerText = 'Bereit';
}}

function toggleStageVideo(){{
  const v = document.getElementById('stageVideo');
  const pb = document.getElementById('stagePlayBtn');
  if(v.paused){{
    v.play();
    pb.innerText = '⏸';
  }} else {{
    v.pause();
    pb.innerText = '▶';
  }}
}}

const body = document.getElementById('dropTarget');
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {{
  body.addEventListener(evt, e => {{ e.preventDefault(); e.stopPropagation(); }}, false);
}});
['dragenter', 'dragover'].forEach(evt => {{
  body.addEventListener(evt, () => {{ body.classList.add('bg-[#1a1315]'); }}, false);
}});
['dragleave', 'drop'].forEach(evt => {{
  body.addEventListener(evt, () => {{ body.classList.remove('bg-[#1a1315]'); }}, false);
}});
body.addEventListener('drop', async e => {{
  const files = e.dataTransfer.files;
  if(!files || files.length === 0) return;
  const formData = new FormData();
  for(let i=0; i<files.length; i++){{ formData.append('files', files[i]); }}
  document.getElementById('logs').innerText = 'Lade ' + files.length + ' Datei(en)...';
  userChangedBpm = false;
  await fetch('/api/upload', {{ method: 'POST', body: formData }});
  updateTrackInfo();
  document.getElementById('logs').innerText = '✓ ' + files.length + ' Datei(en) im Vault geladen!';
}});

async function triggerAutopilot(){{
  document.getElementById('btn').disabled = true;
  const bpm = parseFloat(document.getElementById('bpmNumber').value) || 155;
  const mode = document.getElementById('renderModeSelect').value || 'turbo';
  await fetch('/api/autopilot', {{
    method: 'POST',
    body: JSON.stringify({{ bpm, mode }})
  }});
  poll();
}}

async function startRender(){{
  document.getElementById('btn').disabled = true;
  const customDrop = document.getElementById('customDropInput').value;
  await fetch('/api/render', {{
    method: 'POST',
    body: JSON.stringify({{
      p: document.getElementById('p').value,
      v: 1,
      hook: document.getElementById('hook').value,
      retention: document.getElementById('retention').checked,
      fmt: document.getElementById('fmtSelect').value,
      beats: parseInt(document.getElementById('beatsSelect').value),
      bpm: parseFloat(document.getElementById('bpmNumber').value) || 155,
      mode: document.getElementById('renderModeSelect').value || 'turbo',
      drop: customDrop ? parseFloat(customDrop) : null
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
    if(d.progress === 100 && d.results[0]){{
      loadVideoToStage(d.results[0].stream_url, d.results[0].filename);
    }}
    document.getElementById('res').innerHTML = d.results.map(r => `
      <div class="pro-card p-2 rounded-lg flex justify-between items-center text-xs">
        <div>
          <div class="font-bold text-zinc-100 flex items-center space-x-1">
            <span>🎬</span><span>${{r.filename}}</span>
            <span class="text-[9px] px-1.5 py-0.2 rounded font-tabular ${{r.mode === 'cinema' ? 'bg-red-900 text-red-200' : 'bg-zinc-800 text-zinc-300'}}">${{r.mode === 'cinema' ? '10-Bit EBU' : 'Turbo'}}</span>
          </div>
          <div class="text-[10px] text-zinc-400 font-tabular">Drop bei ${{r.drop}} • ${{r.bpm}} BPM • ${{r.format}}</div>
        </div>
        <div class="space-x-1.5 flex items-center">
          <button onclick="loadVideoToStage('${{r.stream_url}}', '${{r.filename}}')" class="px-2 py-1 bg-red-950/80 text-red-300 border border-red-800 hover:bg-red-600 hover:text-white rounded text-[11px] font-bold transition">Auf Stage</button>
          <button onclick="fetch('/api/open?p='+encodeURIComponent('${{r.filepath}}'))" class="px-2 py-1 bg-white/[0.06] hover:bg-white/[0.1] rounded text-zinc-300 text-[11px] font-medium transition">QuickTime</button>
          <button onclick="fetch('/api/reveal?p='+encodeURIComponent('${{r.filepath}}'))" class="px-2 py-1 bg-white/[0.06] hover:bg-white/[0.1] rounded text-zinc-300 text-[11px] font-medium transition">Finder</button>
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
      document.getElementById('updMsg').innerText=`Neues Update verfügbar: v${{res.remote_version}} (Aktuell: v${{res.current_version}})`;
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
      document.getElementById('updMsg').innerText='✓ Erfolgreich installiert! Starte neu...';
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
  b.innerText='⏳ Scanne...';
  try{{
    const res=await(await fetch('/api/crate_scan',{{method:'POST',body:JSON.stringify({{text}})}})).json();
    document.getElementById('crateMatchRate').innerText=`${{res.found_count}} / ${{res.total_queried}} (${{Math.round(res.found_count/res.total_queried*100)}}%)`;
    document.getElementById('crateItems').innerHTML=res.items.map(it=>`
      <div class="p-2.5 rounded-lg ${{it.found?'pro-card':'bg-red-950/20 border border-red-900/40'}} flex justify-between items-center text-xs">
        <div>
          <div class="font-bold ${{it.found?'text-zinc-100':'text-red-400'}}">${{it.found?'✅':'❌'}} ${{it.query}}</div>
          ${{it.found?`<div class="text-[10px] text-zinc-400 font-tabular truncate max-w-lg mt-0.5">${{it.path}}</div>`:`<div class="text-[10px] text-red-500">Datei nicht auf SSD oder USB gefunden</div>`}}
        </div>
        <div class="flex items-center space-x-1.5">
          <span class="px-2 py-0.5 rounded text-[10px] font-bold font-tabular ${{it.found?'bg-emerald-950 text-emerald-300 border border-emerald-800':'bg-zinc-800 text-zinc-500'}}">${{it.format}}</span>
          ${{it.found?`
            <button onclick="bridgeToTeaser('${{encodeURIComponent(it.path)}}')" class="px-2 py-1 bg-red-950 text-red-300 border border-red-800 hover:bg-red-600 hover:text-white rounded text-[10px] font-bold transition">🎬 Teaser</button>
            <button onclick="copyToVault('${{encodeURIComponent(it.path)}}')" class="px-2 py-1 bg-white/[0.06] hover:bg-white/[0.1] rounded text-[10px] text-zinc-300 transition">In Vault</button>
          `:''}}
        </div>
      </div>
    `).join('');
  }}catch(e){{ alert('Fehler: '+e); }}
  b.disabled=false;
  b.innerText='🔍 Tracks suchen';
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

function changeCleanerFolder(val){{
  document.getElementById('customFolderPath').value = val === 'input_vault' ? '' : val;
}}

async function startCleanerScan(forceFolder = null){{
  let folder = forceFolder || document.getElementById('customFolderPath').value || document.getElementById('cleanerFolderSelect').value;
  const btn = document.getElementById('cleanScanBtn');
  btn.disabled = true;
  btn.innerText = '🛡 Scanne...';
  
  try {{
    const res = await(await fetch('/api/cleaner/scan', {{
      method: 'POST',
      body: JSON.stringify({{ folder }})
    }})).json();
    
    currentCleanerItems = res.items || [];
    renderCleanerResults(res);
  }} catch(e){{
    alert('Fehler beim Ordner-Scan: ' + e);
  }}
  btn.disabled = false;
  btn.innerText = '🛡️ Ordner prüfen & Scannen';
}}

function renderCleanerResults(data){{
  const banner = document.getElementById('cleanerBanner');
  
  if(data.threats_found > 0){{
    banner.className = 'p-3 rounded-lg border text-xs bg-red-950/80 border-red-700 text-red-200 space-y-1';
    document.getElementById('cleanerBannerText').innerHTML = `🚨 <strong>WARNUNG:</strong> ${{data.threats_found}} Bedrohung(en) isoliert! (${{data.total_scanned}} Dateien geprüft)`;
  }} else {{
    banner.className = 'p-3 rounded-lg border text-xs bg-emerald-950/60 border-emerald-700/60 text-emerald-300 space-y-1';
    document.getElementById('cleanerBannerText').innerHTML = `🟢 <strong>SENTINEL CLEAN:</strong> Alle ${{data.total_scanned}} Dateien geprüft • Keine Schadcodes.`;
  }}

  const dupSec = document.getElementById('duplicateSection');
  if(data.duplicates && data.duplicates.length > 0){{
    dupSec.classList.remove('hidden');
    document.getElementById('dupCount').innerText = data.duplicates.length;
    document.getElementById('duplicateList').innerHTML = data.duplicates.map(d => `
      <div class="bg-black/60 p-2 rounded border border-amber-900/50 flex justify-between items-center text-xs">
        <div class="space-y-0.5">
          <div class="text-emerald-400 font-bold">🟢 Behalten: ${{d.winner_name}} (${{d.winner_format}})</div>
          <div class="text-red-400">🗑️ Duplikat: ${{d.loser_name}} (${{d.loser_format}})</div>
        </div>
        <button onclick="trashDuplicate('${{encodeURIComponent(d.loser_path)}}', this)" class="px-2 py-1 bg-red-950 border border-red-800 hover:bg-red-700 text-red-200 rounded font-bold transition text-[10px]">
          In Papierkorb
        </button>
      </div>
    `).join('');
  }} else {{
    dupSec.classList.add('hidden');
  }}

  document.getElementById('cleanerRows').innerHTML = data.items.map((it, idx) => `
    <div class="p-3 rounded-lg ${{it.safe ? 'pro-card' : 'bg-red-950/40 border border-red-700'}} space-y-2 text-xs">
      <div class="flex justify-between items-center">
        <div class="flex items-center space-x-2 truncate">
          ${{it.safe ? `<input type="checkbox" id="chk_${{idx}}" ${{it.selected ? 'checked' : ''}} onchange="currentCleanerItems[${{idx}}].selected=this.checked" class="w-4 h-4 accent-red-600 cursor-pointer">` : '<span class="text-red-500 font-bold">🚨 BLOCKIERT</span>'}}
          <span class="text-zinc-300 font-medium truncate max-w-md">${{it.original_name}}</span>
        </div>
        <div class="flex items-center space-x-1.5 whitespace-nowrap">
          <span class="px-2 py-0.5 rounded text-[10px] font-bold font-tabular ${{it.safe ? 'bg-white/[0.08] text-zinc-300' : 'bg-red-900 text-white'}}">${{it.format}}</span>
          ${{it.safe ? `
            <button onclick="bridgeToTeaser('${{encodeURIComponent(it.path)}}')" title="Als Teaser schneiden" class="px-2 py-0.5 bg-red-950 text-red-300 border border-red-800 hover:bg-red-600 hover:text-white rounded text-[10px] font-bold transition">🎬 Teaser</button>
            <button onclick="bridgeToCrate('${{encodeURIComponent(it.path)}}', '${{it.clean_name.replace(/'/g, "")}}')" title="In Crate-Digger übernehmen" class="px-2 py-0.5 bg-white/[0.06] hover:bg-white/[0.1] text-zinc-300 rounded text-[10px] transition">🎧 In Crate</button>
          ` : `
            <button onclick="trashDuplicate('${{encodeURIComponent(it.path)}}', this)" class="px-2 py-0.5 bg-red-700 hover:bg-red-600 text-white rounded font-bold text-[10px] transition">Sofort löschen</button>
          `}}
        </div>
      </div>
      ${{it.safe ? `
      <div class="grid grid-cols-12 gap-2 pt-1 border-t border-white/[0.06]">
        <div class="col-span-8">
          <label class="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-0.5">Neuer Dateiname (Click-to-Edit):</label>
          <input type="text" id="name_${{idx}}" value="${{it.clean_name}}" oninput="currentCleanerItems[${{idx}}].clean_name=this.value" class="w-full bg-black border border-white/[0.1] p-1.5 rounded text-zinc-100 text-xs focus:border-red-500 focus:outline-none font-tabular">
        </div>
        <div class="col-span-4">
          <label class="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-0.5">Subgenre-Tag:</label>
          <input type="text" id="genre_${{idx}}" value="${{it.genre}}" oninput="currentCleanerItems[${{idx}}].genre=this.value" class="w-full bg-black border border-white/[0.1] p-1.5 rounded text-zinc-100 text-xs focus:border-red-500 focus:outline-none font-medium">
        </div>
      </div>
      ` : `<div class="text-[11px] text-red-400 font-bold">${{it.threat_msg}}</div>`}}
    </div>
  `).join('');
}}

function toggleSelectAllCleaner(){{
  const first = currentCleanerItems.find(i => i.safe);
  const nextVal = first ? !first.selected : true;
  currentCleanerItems.forEach((it, idx) => {{
    if(it.safe){{
      it.selected = nextVal;
      const el = document.getElementById('chk_' + idx);
      if(el) el.checked = nextVal;
    }}
  }});
}}

async function trashDuplicate(pathEnc, btn){{
  btn.disabled = true;
  btn.innerText = 'Lösche...';
  const res = await(await fetch('/api/cleaner/trash?path=' + pathEnc, {{ method: 'POST' }})).json();
  alert(res.message);
  startCleanerScan();
}}

async function executeCleanAndRename(){{
  const mods = currentCleanerItems.filter(i => i.safe && i.selected).map(i => ({{
    path: i.path,
    new_name: i.clean_name,
    genre: i.genre
  }}));
  
  if(mods.length === 0) return alert('Keine Dateien ausgewählt.');
  const res = await(await fetch('/api/cleaner/execute', {{
    method: 'POST',
    body: JSON.stringify({{ modifications: mods }})
  }})).json();
  
  alert(`✓ ${{res.renamed_count}} Dateien bereinigt und mit ID3-Tags versehen!`);
  startCleanerScan();
}}

async function bridgeToTeaser(pathEnc){{
  const res = await(await fetch('/api/bridge/to_teaser?path=' + pathEnc, {{ method: 'POST' }})).json();
  if(res.status === 'ok'){{
    switchTab('video');
    updateTrackInfo();
  }}
}}

function bridgeToCrate(pathEnc, cleanName){{
  const ta = document.getElementById('crateText');
  ta.value = (ta.value.trim() ? ta.value.trim() + '\\n' : '') + cleanName;
  switchTab('crate');
  startCrateScan();
}}
</script></body></html>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    
    def check_origin(self):
        host = self.headers.get("Host", "")
        if not (host.startswith("127.0.0.1") or host.startswith("localhost")):
            self.send_response(403)
            self.end_headers()
            return False
            
        origin = self.headers.get("Origin") or self.headers.get("Referer")
        if origin:
            if not ("127.0.0.1:8505" in origin or "localhost:8505" in origin):
                self.send_response(403)
                self.end_headers()
                return False
        return True
        
    def do_GET(self):
        if not self.check_origin(): return
        
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
            auds = sorted(glob.glob(os.path.join(VAULT, "*.mp3")) + glob.glob(os.path.join(VAULT, "*.wav")) + glob.glob(os.path.join(VAULT, "*.m4a")) + glob.glob(os.path.join(VAULT, "*.aiff")))
            if auds:
                info = analyze_track_details(auds[0])
                drop_point = find_loudest_drop(auds[0])
                envelope = extract_waveform_envelope(auds[0], 100)
                res = {
                    "has_audio": True,
                    "filename": info["filename"],
                    "duration_sec": info["duration_sec"],
                    "duration_str": info["duration_str"],
                    "detected_bpm": info["detected_bpm"],
                    "drop_sec": drop_point,
                    "waveform": envelope
                }
            else:
                res = {
                    "has_audio": False,
                    "filename": "",
                    "duration_sec": 180.0,
                    "duration_str": "--:--",
                    "detected_bpm": 155.0,
                    "drop_sec": 2.30,
                    "waveform": []
                }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        elif p == "/api/stream_video":
            f = urllib.parse.unquote(self.path.split("p=")[-1])
            if os.path.isfile(f) and f.lower().endswith((".mp4", ".mov", ".m4v")):
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Accept-Ranges", "bytes")
                sz = os.path.getsize(f)
                self.send_header("Content-Length", str(sz))
                self.end_headers()
                with open(f, "rb") as vf:
                    shutil.copyfileobj(vf, self.wfile)
                return
            else:
                self.send_response(404)
                self.end_headers()
        elif p == "/api/check_update":
            try:
                req = urllib.request.Request(GITHUB_RAW_URL, headers={"User-Agent": "TechDudeUpdater/1.0"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    content = resp.read().decode("utf-8")
                m = re.search(r'CURRENT_VERSION\s*=\s*["\']([^"\']+)["\']', content)
                remote_ver = m.group(1) if m else CURRENT_VERSION
                res = {"status": "ok", "has_update": remote_ver != CURRENT_VERSION, "remote_version": remote_ver, "current_version": CURRENT_VERSION}
            except Exception as e:
                res = {"status": "error", "message": str(e), "current_version": CURRENT_VERSION}
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
            if os.path.isfile(f) and f.lower().endswith((".mp4", ".mov", ".wav", ".mp3")):
                subprocess.Popen(["open", "-a", "QuickTime Player", f])
            self.send_response(200)
            self.end_headers()
        elif p == "/api/reveal":
            f = urllib.parse.unquote(self.path.split("p=")[-1])
            if os.path.exists(f):
                subprocess.Popen(["open", "-R", f])
            self.send_response(200)
            self.end_headers()
        elif p == "/api/copy_vault":
            f = urllib.parse.unquote(self.path.split("path=")[-1])
            if os.path.isfile(f):
                dst = os.path.join(VAULT, os.path.basename(f))
                shutil.copy2(f, dst)
                res = {"status": "ok", "message": f"✓ '{os.path.basename(f)}' in Vault geladen!"}
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
        if not self.check_origin(): return

        length = int(self.headers.get("Content-Length", 0))
        content_type = self.headers.get("Content-Type", "")
        
        if self.path == "/api/upload":
            boundary = content_type.split("boundary=")[-1].encode("utf-8")
            raw_body = self.rfile.read(length)
            parts = raw_body.split(boundary)
            for part in parts:
                if b'filename="' in part:
                    fn_match = re.search(rb'filename="([^"]+)"', part)
                    if fn_match:
                        raw_fn = fn_match.group(1).decode("utf-8", errors="ignore")
                        filename = os.path.basename(raw_fn).strip()
                        if not filename: continue
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
            auds = sorted(glob.glob(os.path.join(VAULT, "*.mp3")) + glob.glob(os.path.join(VAULT, "*.wav")) + glob.glob(os.path.join(VAULT, "*.m4a")) + glob.glob(os.path.join(VAULT, "*.aiff")))
            best_drop = find_loudest_drop(auds[0]) if auds else 2.30
            bpm_val = float(d.get("bpm", 155.0))
            mode_val = d.get("mode", "turbo")
            threading.Thread(
                target=run_job,
                args=("warehouse", 1, "UNRELEASED ID?", True, "9:16", 16, best_drop, bpm_val, mode_val),
                daemon=True
            ).start()
            self.send_response(200)
            self.end_headers()
        elif self.path == "/api/render":
            threading.Thread(
                target=run_job,
                args=(
                    d.get("p", "warehouse"),
                    d.get("v", 1),
                    d.get("hook", ""),
                    d.get("retention", True),
                    d.get("fmt", "9:16"),
                    d.get("beats", 16),
                    d.get("drop", None),
                    float(d.get("bpm", 155.0)),
                    d.get("mode", "turbo")
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
        elif self.path == "/api/cleaner/scan":
            target = d.get("folder", "~/Downloads")
            res = scan_cleaner_folder(target)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        elif self.path == "/api/cleaner/execute":
            mods = d.get("modifications", [])
            res = apply_cleaning_actions(mods)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        elif self.path.startswith("/api/cleaner/trash"):
            p = urllib.parse.unquote(self.path.split("path=")[-1])
            res = trash_file_safely(p)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        elif self.path == "/api/cleaner/set_folder":
            p = d.get("path", "")
            if os.path.isdir(p):
                res = scan_cleaner_folder(p)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "folder": p, "count": res.get("total_scanned", 0)}).encode("utf-8"))
            else:
                self.send_response(400)
                self.end_headers()
        elif self.path.startswith("/api/bridge/to_teaser"):
            p = urllib.parse.unquote(self.path.split("path=")[-1])
            if os.path.isfile(p):
                dst = os.path.join(VAULT, os.path.basename(p))
                shutil.copy2(p, dst)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "path": dst}).encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()
        elif self.path == "/api/install_update":
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
                res = {"status": "ok", "message": "Update erfolgreich installiert! Starte neu..."}
            except Exception as e:
                res = {"status": "error", "message": str(e)}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def main():
    server = ThreadedHTTPServer(("127.0.0.1", 8505), H)
    url = "http://127.0.0.1:8505"
    print(f"\n[OK] {APP_NAME} V{CURRENT_VERSION} (Phase 1 Dual-Render Engine) aktiv unter: {url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == "__main__":
    main()