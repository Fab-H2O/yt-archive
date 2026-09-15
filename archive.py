import os
import re
import sys
import time
import signal
import shutil
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
DENO = os.path.join(ROOT, "deno.exe")
YTDLP = os.path.join(ROOT, "yt-dlp.exe")
YTARCHIVE = os.path.join(ROOT, "ytarchive.exe")
FFMPEG_DIR = os.path.join(ROOT, "ffmpeg")

QUALITY_HEIGHT = {
    "audio_only": None, "audio": None,
    "144p": 144, "240p": 240, "360p": 360, "480p": 480, "720p": 720,
    "720p60": 720, "1080p": 1080, "1080p60": 1080, "1440p": 1440,
    "1440p60": 1440, "2160p": 2160, "2160p60": 2160,
}
QUALITY_60 = {"720p60", "1080p60", "1440p60", "2160p60"}

USAGE = """usage: archive.py [OPTIONS] [url] [quality]

Runs the bundled yt-dlp + deno + ffmpeg pipeline so YouTube livestream
archival works with current YouTube (deno solves the nsig challenges
automatically; no manual --potoken needed).

[url]     youtube livestream/channel URL (prompted if omitted).
[quality] slash-delimited qualities, most to least wanted:
          audio_only,144p,240p,360p,480p,720p,720p60,1080p,1080p60,
          1440p,1440p60,2160p,2160p60,best   (default: best)

Options (ytarchive-compatible):
  -h,--help  -V,--version
  -w,--wait  -n,--no-wait
  -r,--retry-stream SECONDS
  -c,--cookies FILE
  -o,--output FMT
  -t,--thumbnail  --write-thumbnail
  -k,--keep-ts-files  --write-description
  --mkv  --add-metadata  --metadata KEY=VAL
  --vp9  --h264  --av1
  --no-audio  --no-video
  --capture-duration DUR|TIME
  --live-from TIME  --start-delay DUR
  --threads N  --retry-frags N
  --proxy URL  -4,--ipv4  -6,--ipv6
  --ffmpeg-path PATH
  -q,--quiet  --error  -v,--verbose  --debug
  --info-only  --monitor-channel
  --potoken TOKEN  --legacy-ytarchive
Any other option is passed through to yt-dlp unchanged.
"""


def is_windows():
    return os.name == "nt"


def parse_duration(value):
    value = value.strip()
    hm = re.fullmatch(r"(\d+):(\d{1,2}):(\d{1,2})", value)
    if hm:
        h, m, s = (int(x) for x in hm.groups())
        return h * 3600 + m * 60 + s
    if re.fullmatch(r"\d+:\d{1,2}", value):
        parts = [int(x) for x in value.split(":")]
        return parts[0] * 60 + parts[1]
    if re.fullmatch(r"\d+", value):
        return int(value)
    total = 0
    for amount, unit in re.findall(r"(\d+)([dhmsDHMS])", value):
        amount = int(amount)
        if unit in "dD":
            total += amount * 86400
        elif unit in "hH":
            total += amount * 3600
        elif unit in "mM":
            total += amount * 60
        elif unit in "sS":
            total += amount
    return total


def find_bin(candidates):
    for c in candidates:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    return shutil.which(candidates[0]) if candidates else None


def codec_filter(codec):
    if codec == "h264":
        return "[vcodec^=avc1]"
    if codec == "vp9":
        return "[vcodec^=vp9]"
    if codec == "av1":
        return "[vcodec^=av01]"
    return ""


def video_selector(quality, codec):
    height = QUALITY_HEIGHT.get(quality)
    if height is None:
        return "bv*"
    selector = f"bv*[height<={height}]"
    if quality in QUALITY_60:
        selector += "[fps>30]"
    return selector + codec_filter(codec)


def build_format(qualities, codec, no_audio, no_video):
    if no_video:
        return "ba/b"
    if not qualities:
        qualities = ["best"]
    if qualities == ["best"]:
        return ("bv*/b" if no_audio else "bv*+ba/b")
    if no_audio:
        return "/".join(video_selector(q, codec) for q in qualities)
    parts = []
    for q in qualities:
        if q in ("audio_only", "audio"):
            parts.append("ba/b")
        else:
            parts.append(video_selector(q, codec) + "+ba/b")
    return "/".join(parts)
def main():
    args = sys.argv[1:]
    if not args:
        sys.stderr.write("No URL provided; please paste a YouTube livestream URL and options.\n")
    if "-h" in args or "--help" in args:
        sys.stderr.write(USAGE)
        return 0
    if "-V" in args or "--version" in args:
        sys.stderr.write("archive.py launcher 1.0 (drives bundled yt-dlp + deno + ffmpeg)\n")
        return 0

    url = None
    quality_arg = None
    wait = False
    cookie = None
    output = "%(title)s-%(id)s"
    capture_duration = None
    poll_secs = None
    embed_thumb = False
    write_thumb = False
    keep_ts = False
    write_desc = False
    mkv = False
    add_meta = False
    meta_pairs = []
    codec = None
    no_audio = False
    no_video = False
    start_delay = None
    threads = None
    retry_frags = None
    proxy = None
    force_ip = None
    ffmpeg_path = None
    loglevel = "default"
    info_only = False
    monitor = False
    live_now = False
    potoken = None
    legacy = False
    passthrough = []
    positional = []

    value_opts = {
        "-f", "--format", "--exec", "--load-info-json", "--playlist-start",
        "--playlist-end", "--sub-langs", "--limit-rate", "-R", "--retries",
        "--extractor-args",
    }
    i = 0
    while i < len(args):
        a = args[i]
        nxt = args[i + 1] if i + 1 < len(args) else None
        if a in ("-w", "--wait"):
            wait = True
        elif a in ("-n", "--no-wait"):
            wait = False
        elif a in ("-c", "--cookies"):
            cookie = nxt
            i += 1
        elif a in ("-o", "--output", "--output-template"):
            output = nxt
            i += 1
        elif a in ("-t", "--thumbnail"):
            embed_thumb = True
        elif a == "--write-thumbnail":
            write_thumb = True
        elif a in ("-k", "--keep-ts-files", "--keep-video"):
            keep_ts = True
        elif a == "--write-description":
            write_desc = True
        elif a == "--mkv":
            mkv = True
        elif a == "--add-metadata":
            add_meta = True
        elif a == "--metadata":
            if nxt:
                meta_pairs.append(nxt)
            i += 1
        elif a == "--vp9":
            codec = "vp9"
        elif a == "--h264":
            codec = "h264"
        elif a == "--av1":
            codec = "av1"
        elif a == "--no-audio":
            no_audio = True
        elif a in ("--no-video", "--audio-only", "-x", "--extract-audio"):
            no_video = True
        elif a == "--capture-duration":
            capture_duration = parse_duration(nxt or "0")
            i += 1
        elif a == "--live-from":
            if nxt and nxt.strip().lower() == "now":
                live_now = True
            i += 1
        elif a == "--start-delay":
            start_delay = parse_duration(nxt or "0")
            i += 1
        elif a == "--threads":
            threads = nxt
            i += 1
        elif a == "--retry-frags":
            retry_frags = nxt
            i += 1
        elif a in ("-r", "--retry-stream"):
            poll_secs = int(nxt or "0")
            i += 1
        elif a == "--proxy":
            proxy = nxt
            i += 1
        elif a in ("-4", "--ipv4", "--force-ipv4"):
            force_ip = 4
        elif a in ("-6", "--ipv6", "--force-ipv6"):
            force_ip = 6
        elif a == "--ffmpeg-path":
            ffmpeg_path = nxt
            i += 1
        elif a in ("-q", "--quiet"):
            loglevel = "quiet"
        elif a == "--error":
            loglevel = "error"
        elif a in ("-v", "--verbose"):
            loglevel = "verbose"
        elif a == "--debug":
            loglevel = "debug"
        elif a == "--info-only":
            info_only = True
        elif a == "--monitor-channel":
            monitor = True
        elif a == "--potoken":
            potoken = nxt
            i += 1
        elif a == "--legacy-ytarchive":
            legacy = True
        elif a.startswith("-"):
            if nxt is not None and not nxt.startswith("-") and a in value_opts:
                passthrough.append(a)
                passthrough.append(nxt)
                i += 1
            else:
                passthrough.append(a)
        else:
            positional.append(a)
        i += 1

    if len(positional) > 0:
        url = positional[0]
    if len(positional) > 1:
        quality_arg = positional[1]

    if url is None:
        try:
            url = input("Enter a youtube livestream URL: ").strip()
        except EOFError:
            url = ""
        if not url:
            sys.stderr.write("No URL provided.\n")
            return 1
        if quality_arg is None:
            try:
                print("\nAvailable quality options (slash-delimited for fallbacks):")
                print("  144p    240p    360p    480p    720p    720p60")
                print("  1080p   1080p60 1440p   1440p60 2160p   2160p60")
                print("  audio   audio_only   best")
                print("\nEnter qualities separated by / (e.g. 1080p/720p60/720p/best) or just 'best':")
                quality_arg = input("> ").strip() or "best"
            except EOFError:
                quality_arg = "best"
    if quality_arg is None:
        quality_arg = "best"
    deno_path = find_bin([DENO])
    ytdlp_path = find_bin([YTDLP])
    ytarchive_path = find_bin([YTARCHIVE])

    if legacy:
        return run_legacy(ytarchive_path, ffmpeg_path, potoken, cookie, wait,
                          poll_secs, output, embed_thumb, keep_ts, mkv,
                          add_meta, meta_pairs, codec, no_audio, no_video,
                          proxy, force_ip, info_only, loglevel,
                          passthrough, url, quality_arg)

    if not ytdlp_path:
        sys.stderr.write("yt-dlp.exe not found alongside archive.py.\n")
        return 1
    if not deno_path:
        sys.stderr.write("deno.exe not found; yt-dlp needs it to solve nsig challenges.\n")
        return 1

    ffmpeg_loc = ffmpeg_path or find_bin([os.path.join(FFMPEG_DIR, "ffmpeg.exe")]) or shutil.which("ffmpeg")
    qualities = [q.strip() for q in quality_arg.split("/") if q.strip()]
    fmt = build_format(qualities, codec, no_audio, no_video)

    cmd = [ytdlp_path, "--no-colors", "--progress"]
    if ffmpeg_loc:
        cmd += ["--ffmpeg-location", ffmpeg_loc]
    if threads:
        cmd += ["--concurrent-fragments", threads]
    if retry_frags is not None:
        cmd += ["--fragment-retries", retry_frags]
    if proxy:
        cmd += ["--proxy", proxy]
    if force_ip == 4:
        cmd += ["-4"]
    elif force_ip == 6:
        cmd += ["-6"]
    if cookie:
        cmd += ["--cookies", cookie]
    cmd += ["-o", output, "-f", fmt]
    if wait:
        mins = max(0.5, poll_secs / 60.0) if poll_secs is not None else 1440
        cmd += ["--wait-for-video", ("%.2f" % mins)]
        if poll_secs is not None:
            cmd += ["--live-poll-interval", str(poll_secs)]
        cmd += ["--no-abort-on-error"]
    else:
        cmd += ["--no-wait-for-video"]
    if not live_now:
        cmd += ["--live-from-start"]
    if info_only:
        cmd += ["--simulate", "--no-part",
                "--print", "%(title)s|%(id)s|%(channel)s|live:%(is_live)s|%(upload_date)s|%(duration_string)s",
                "--list-formats"]
    if embed_thumb or write_thumb:
        cmd += ["--write-thumbnail"]
    if embed_thumb:
        cmd += ["--embed-thumbnail"]
    if keep_ts:
        cmd += ["--keep-video"]
    if write_desc:
        cmd += ["--write-description"]
    if mkv:
        cmd += ["--merge-output-format", "mkv"]
    elif not no_video:
        cmd += ["--merge-output-format", "mp4"]
    if add_meta or meta_pairs:
        cmd += ["--embed-metadata"]
        for pair in meta_pairs:
            if "=" in pair:
                key, value = pair.split("=", 1)
                if value != "":
                    cmd += ["--parse-metadata", f"{value}:{key}"]
    if potoken:
        cmd += ["--extractor-args", f"youtube:po_token=web.gvs+{potoken}"]
    if loglevel == "quiet":
        cmd += ["-q"]
    elif loglevel == "error":
        cmd += ["--no-warnings"]
    elif loglevel == "verbose":
        cmd += ["--verbose"]
    elif loglevel == "debug":
        cmd += ["--verbose", "--verbose"]
    if no_video:
        cmd += ["--audio-format", "m4a"]
    cmd += passthrough
    cmd += ["--no-playlist"]
    if url:
        cmd.append(url)

    env = os.environ.copy()
    path_var = env.get("PATH") or ""
    deno_dir = os.path.dirname(deno_path)
    if deno_dir and deno_dir.lower() not in path_var.lower():
        env["PATH"] = deno_dir + os.pathsep + path_var
    if not ffmpeg_loc and os.path.isdir(FFMPEG_DIR):
        env["PATH"] = FFMPEG_DIR + os.pathsep + env["PATH"]

    if start_delay:
        sys.stderr.write(f"Waiting {start_delay}s before starting capture...\n")
        time.sleep(start_delay)

    return run_ytdlp(cmd, env, capture_duration, monitor)


def run_legacy(ytarchive_path, ffmpeg_path, potoken, cookie, wait,
               poll_secs, output, embed_thumb, keep_ts, mkv, add_meta,
               meta_pairs, codec, no_audio, no_video, proxy, force_ip,
               info_only, loglevel, passthrough, url, quality_arg):
    if not ytarchive_path:
        sys.stderr.write("ytarchive.exe not found.\n")
        return 1
    sys.stderr.write(
        "Legacy mode: ytarchive.exe is a frozen Jan-2025 binary that does not solve\n"
        "YouTube's nsig challenge, so it will likely still fail with HTTP 403/unreachable\n"
        "URLs. Pass a fresh --potoken if you have one. The default yt-dlp mode is more reliable.\n")
    cmd = [ytarchive_path]
    cmd += ["--ffmpeg-path", ffmpeg_path or os.path.join(FFMPEG_DIR, "ffmpeg.exe")]
    if potoken:
        cmd += ["--potoken", potoken]
    if cookie:
        cmd += ["--cookies", cookie]
    if wait:
        if poll_secs is not None:
            cmd += ["-r", str(poll_secs)]
        else:
            cmd += ["-w"]
    if output != "%(title)s-%(id)s":
        cmd += ["-o", output]
    if embed_thumb:
        cmd += ["-t"]
    if keep_ts:
        cmd += ["-k"]
    if mkv:
        cmd += ["--mkv"]
    if add_meta:
        cmd += ["--add-metadata"]
        for pair in meta_pairs:
            cmd += ["--metadata", pair]
    if codec == "vp9":
        cmd += ["--vp9"]
    elif codec == "h264":
        cmd += ["--h264"]
    elif codec == "av1":
        cmd += ["--av1"]
    if no_audio:
        cmd += ["--no-audio"]
    if no_video:
        cmd += ["--no-video"]
    if proxy:
        cmd += ["--proxy", proxy]
    if force_ip == 4:
        cmd += ["-4"]
    elif force_ip == 6:
        cmd += ["-6"]
    if info_only:
        cmd += ["--info-only"]
    if loglevel == "quiet":
        cmd += ["-q"]
    elif loglevel == "error":
        cmd += ["--error"]
    elif loglevel == "verbose":
        cmd += ["-v"]
    elif loglevel == "debug":
        cmd += ["--debug"]
    cmd += passthrough
    if url:
        cmd.append(url)
    cmd.append(quality_arg)
    return subprocess.call(cmd, env=os.environ.copy())
def run_ytdlp(cmd, env, capture_duration, monitor):
    creationflags = 0
    if is_windows():
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        proc = subprocess.Popen(cmd, env=env, creationflags=creationflags)
    except OSError as e:
        sys.stderr.write(f"Failed to start yt-dlp.exe: {e}\n")
        return 1

    if capture_duration is not None:
        try:
            time.sleep(max(int(capture_duration), 0))
        except KeyboardInterrupt:
            pass
        graceful_interrupt(proc)
        return proc.wait()

    if monitor:
        try:
            while True:
                proc = subprocess.Popen(cmd, env=env, creationflags=creationflags)
                proc.wait()
                sys.stderr.write("Stream finished. Checking again in 30s...\n")
                time.sleep(30)
        except KeyboardInterrupt:
            return 0
        return 0

    return proc.wait()


def graceful_interrupt(proc):
    try:
        if proc.poll() is not None:
            return
        if is_windows():
            proc.send_signal(signal.CTRL_C_EVENT)
        else:
            proc.send_signal(signal.SIGINT)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
