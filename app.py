import glob
import os
import re
import shutil
import uuid
import zipfile
from collections import defaultdict

import yt_dlp
from flask import Flask, jsonify, render_template, request, send_file

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

URL_PATTERN = re.compile(
    r"^https?://(www\.|vm\.|vt\.)?(instagram\.com|tiktok\.com)/",
    re.IGNORECASE,
)

VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi"}


class CaptureLogger:
    """Collects yt-dlp warning/error messages so we can surface a useful
    error when a download silently yields zero files (e.g. private posts)."""

    def __init__(self):
        self.messages = []

    def debug(self, msg):
        pass

    def warning(self, msg):
        self.messages.append(msg)

    def error(self, msg):
        self.messages.append(msg)


def dedupe_thumbnails(files):
    """Instagram photo posts have no 'video format', so we fall back to
    downloading their thumbnail (the actual full-res photo). But video
    posts also get a poster thumbnail written alongside the real video
    file — drop that poster whenever a video file exists in the group.
    Files are grouped by id (the outtmpl has no other varying part), and
    the poster's extension varies (.jpg/.webp/.image) so we key off known
    video extensions rather than guessing every possible image one."""
    groups = defaultdict(list)
    for f in files:
        base, ext = os.path.splitext(f)
        groups[base].append((f, ext.lower()))

    result = []
    for entries in groups.values():
        video = [f for f, ext in entries if ext in VIDEO_EXTS]
        result.extend(video or [f for f, _ in entries])
    return sorted(result, key=os.path.getmtime)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "Bitte einen Link einfügen."}), 400
    if not URL_PATTERN.match(url):
        return jsonify({"error": "Das ist kein gültiger Instagram- oder TikTok-Link."}), 400

    job_id = uuid.uuid4().hex
    job_dir = os.path.join(DOWNLOAD_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    outtmpl = os.path.join(job_dir, "%(id)s.%(ext)s")
    logger = CaptureLogger()

    ydl_opts = {
        "outtmpl": outtmpl,
        "format": "bv*+ba/best",
        "merge_output_format": "mp4",
        "noplaylist": False,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        # Instagram photo posts (and photo slides in carousels) have no
        # video format at all; ignore that and fall back to their
        # thumbnail, which is the actual full-resolution photo.
        "ignore_no_formats_error": True,
        "writethumbnail": True,
        # Don't let one failed carousel item abort the whole post.
        "ignoreerrors": True,
        "logger": logger,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": clean_error(e)}), 500

    files = dedupe_thumbnails(
        f for f in glob.glob(os.path.join(job_dir, "*")) if os.path.isfile(f)
    )

    if not files:
        shutil.rmtree(job_dir, ignore_errors=True)
        fallback = next((m for m in reversed(logger.messages) if m), None)
        return jsonify({"error": clean_error(fallback) if fallback else "Es wurden keine Medien gefunden."}), 500

    platform = "instagram" if "instagram.com" in url else "tiktok"

    if len(files) == 1:
        src = files[0]
        ext = os.path.splitext(src)[1]
        download_name = f"{platform}_download{ext}"
        response = send_file(src, as_attachment=True, download_name=download_name)
    else:
        zip_path = os.path.join(job_dir, f"{platform}_download.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for idx, f in enumerate(files, start=1):
                ext = os.path.splitext(f)[1]
                zf.write(f, arcname=f"{platform}_{idx}{ext}")
        response = send_file(zip_path, as_attachment=True, download_name=f"{platform}_download.zip")

    response.call_on_close(lambda: shutil.rmtree(job_dir, ignore_errors=True))
    return response


def clean_error(e) -> str:
    msg = str(e)
    lowered = msg.lower()
    if "private" in lowered or "login" in lowered or "rate-limit" in lowered:
        return "Dieser Inhalt ist privat, erfordert einen Login oder wurde von der Plattform blockiert."
    if "unsupported url" in lowered:
        return "Dieser Link wird nicht unterstützt."
    if "unable to extract" in lowered or "404" in lowered:
        return "Der Inhalt konnte nicht gefunden werden. Ist der Link korrekt?"
    return "Download fehlgeschlagen: " + msg[:200]


if __name__ == "__main__":
    # Startup cleanup of any leftover temp folders from previous runs
    for d in glob.glob(os.path.join(DOWNLOAD_DIR, "*")):
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
    app.run(debug=True, port=5050)
