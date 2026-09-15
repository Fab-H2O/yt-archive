# yt-archive

A modernized YouTube livestream archiving tool written in python that fixes the original [`ytarchive`](https://github.com/Kethsar/ytarchive)
## Problem Solved

The original `ytarchive.exe` (v0.5.0, built January 2025) communicates directly with YouTube's innertube API to download DASH fragments. However, it was built before YouTube's current security requirements and **cannot solve the `nsig` challenge**. As a result, it no longer archives properly -- even with a manually supplied `poToken`, streams typically fail with HTTP 403 errors or unreachable URLs.

I also wanted an easy solution, dump URL, select quality and be done.

This project rewires the ytarchive front-end onto the yt-dlp engine, which natively handles all current YouTube authentication and challenge resolution automatically.

## What This Project Does

- **`archive.py`** -- A ytarchive-compatible command-line launcher that orchestrates the `yt-dlp + deno + ffmpeg` pipeline with a familiar interface
- **`run-ytarchive.bat`** -- A Windows batch wrapper for easy double-click or console execution of `archive.py`


## How It Works

Create a Root folder with both **`archive.py`** and **`run-ytarchive.bat`**, you MUST add yt-dlp.exe and deno.exe in that folder. Create a subfolder named (the sub-folder already exist (not the files) if you download the release version) **`ffmpeg`** and put the : 7z.dll / ffmpeg.exe / ffplay.exe / ffprobe.exe in it.
**Please download them from the original source. Link at the bottom.**


```
+-----------------------------------------------------------------+
|                 run-ytarchive.bat                                |
|            (user-friendly wrapper)                               |
+-----------------------------------------------------------------+
                              |
                              v
+-----------------------------------------------------------------+
|                   archive.py                                     |
|     (ytarchive-compatible CLI interface)                         |
+-----------------------------------------------------------------+
                              |
                              v
+-----------------------------------------------------------------+
|                  yt-dlp.exe                                      |
|   YouTube extraction + poToken/nsig resolution                   |
+-----------------------------------------------------------------+
                       /                     \
                      v                       v
+-------------------------+  +-------------------------+
|      deno.exe           |  |     yt-dlp.exe          |
| Challenge engine        |  | Core extraction         |
+-------------------------+  +-------------------------+
                      |
                      v
+-----------------------------------------------------------------+
|                  ffmpeg.exe                                      |
|          Video/audio muxing and encoding                         |
+-----------------------------------------------------------------+
```

## Quick Start

1. **Download** or **clone** this repository
2. **Navigate** to the `bin/` folder:
   ```
   cd bin
   ```
3. **Run** the batch file or archive script:

   ```
   :: Archive a specific stream
   run-ytarchive.bat https://www.youtube.com/watch?v=XXXX best

   :: Wait for a stream to go live
   run-ytarchive.bat -w https://www.youtube.com/watch?v=XXXX 1080p60

   :: Monitor a channel for live streams
   run-ytarchive.bat --monitor-channel https://www.youtube.com/channel/UCXXX

   :: Archive audio only
   run-ytarchive.bat https://www.youtube.com/watch?v=XXXX audio_only
   ```

## Supported Quality Options

| Quality | Description |
|---|---|
| `audio_only` | Audio only |
| `144p` - `480p` | Standard definition |
| `720p`, `720p60` | HD 720p / 60fps |
| `1080p`, `1080p60` | Full HD 1080p / 60fps |
| `1440p`, `1440p60` | 2K / 60fps |
| `2160p`, `2160p60` | 4K / 60fps |
| `best` | Automatically select the best quality |

## Common Options

| Option | Description |
|---|---|
| `-w, --wait` | Wait for a stream to go live |
| `-n, --no-wait` | Exit if stream is not live |
| `-r, --retry-stream N` | Retry every N seconds if stream goes down |
| `-c, --cookies FILE` | Use a cookies file (Netscape format) |
| `-o, --output FMT` | Output filename format |
| `-t, --thumbnail` | Embed thumbnail in the file |
| `-k, --keep-ts-files` | Keep raw TS files instead of merging |
| `--mkv` | Output MKV container |
| `--add-metadata` | Add metadata to the file |
| `--vp9, --h264, --av1` | Force a specific video codec |
| `--capture-duration T` | Record for T seconds, minutes, or hours (e.g., `1h30m`) |
| `--live-from TIME` | Start recording at a specific time |
| `--monitor-channel` | Continuously monitor a channel for live streams |
| `--proxy URL` | Use a proxy server |
| `-4, --ipv4` | Force IPv4 |
| `-6, --ipv6` | Force IPv6 |
| `--legacy-ytarchive` | Use the original ytarchive.exe (likely to fail) |

Run `archive.py --help` for the full list of options. Any unrecognized option is passed directly to yt-dlp.

## Dependencies
* [**ffmpeg** and **ffprobe**](https://www.ffmpeg.org) - Required for [merging separate video and audio files](#format-selection), as well as for various [post-processing](#post-processing-options) tasks. License [depends on the build](https://www.ffmpeg.org/legal.html)
    **Important**: What you need is ffmpeg *binary*, **NOT** [the Python package of the same name](https://pypi.org/project/ffmpeg)
* A JavaScript runtime/engine like [**deno**](https://deno.land)  
* yt-dlp is required [**yt-dlp.exe**]([https://github.com/yt-dlp/yt-dlp0](https://github.com/yt-dlp/yt-dlp)
### Required

| **Python** | 3.10+ | Required to run `archive.py` (must be added to PATH) |


### Python

This project requires **Python 3.10** or later. The `run-ytarchive.bat` file launches `archive.py` via Python.

Ensure Python is installed and added to your system `PATH`. You can verify the installation with:

```
python --version
```

### yt-dlp

Keep your yt-dlp up to date by getting the latest version.

See the original project for more details: https://github.com/yt-dlp/yt-dlp

### Original ytarchive

The original project (https://github.com/Kethsar/ytarchive) is located in the `ytarchive-dev/` folder as reference. The `ytarchive.exe` binary is kept but will likely fail on current YouTube streams due to the unsolved `nsig` challenge.

## Known Limitations

1. The default yt-dlp clients (`android_vr`/`visionos`) work without a token. Forcing `--extractor-args youtube:player_client=web` may require a `poToken` since this yt-dlp build only solves `nsig` (no HTTP poToken provider). Stick to the defaults unless you supply a token.
2. Some low-level ytarchive flags (file/dir permissions, save-state, fragment file handling) have no yt-dlp equivalent and are intentionally not translated.
3. This project targets Windows -- the `run-ytarchive.bat` wrapper and all binaries are `.exe` files.


## Legacy Mode

If you download the original ytarchive.exe you can fallback to it. This was done for testing purpose.

The `--legacy-ytarchive` flag invokes the original `ytarchive.exe` binary. This is **not recommended** because:

- It is a frozen binary that does not solve YouTube's `nsig` challenge
- It will likely fail with HTTP 403 or unreachable URL errors
- It requires a manually provided `--potoken` that is generally insufficient

Use this only if you have a working `poToken` and accept that archival may still fail.

## License

This project is a modification of the original [ytarchive](https://github.com/Kethsar/ytarchive) project.

## Credits

- **Original ytarchive**: [Kethsar/ytarchive](https://github.com/Kethsar/ytarchive)
- **yt-dlp**: [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp)
- **FFmpeg**: [FFmpeg](https://ffmpeg.org/)
- **Deno**: [denoland/deno](https://deno.com/)
