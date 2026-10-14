"""
Autopilot Agent - Backend API Server v1.0
Wraps youtube_api.py + tiktok_api.py as REST endpoints for the Android app.

Run: python3 api_server.py
"""
import os
import sys
import json
import secrets
from flask import Flask, request, jsonify

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import youtube_api
import tiktok_api

app = Flask(__name__)

# In-memory token store (use encrypted DB in production)
TOKENS = {}


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": "1.0"})


# ---------------------------------------------------------------------------
# YouTube OAuth
# ---------------------------------------------------------------------------
@app.route("/api/youtube/auth-url", methods=["GET"])
def yt_auth_url():
    verifier = secrets.token_urlsafe(32)
    # Simple PKCE challenge (S256 needs hashlib - simplified here)
    import hashlib, base64
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    url = youtube_api.build_auth_url(challenge)
    return jsonify({"auth_url": url, "code_verifier": verifier})


@app.route("/api/youtube/exchange", methods=["POST"])
def yt_exchange():
    data = request.get_json(force=True)
    client_secret = os.environ.get("YT_CLIENT_SECRET", "")
    result = youtube_api.exchange_code(
        data["code"], data["code_verifier"], client_secret)
    user_id = data.get("user_id", "default")
    TOKENS[user_id] = {"youtube": result}
    return jsonify({"ok": True})


@app.route("/api/youtube/channels", methods=["GET"])
def yt_channels():
    user_id = request.args.get("user_id", "default")
    token = TOKENS.get(user_id, {}).get("youtube", {}).get("access_token", "")
    if not token:
        return jsonify({"error": "not_connected"}), 401
    return jsonify(youtube_api.my_channels(token))


@app.route("/api/youtube/upload", methods=["POST"])
def yt_upload():
    user_id = request.form.get("user_id", "default")
    token = TOKENS.get(user_id, {}).get("youtube", {}).get("access_token", "")
    if not token:
        return jsonify({"error": "not_connected"}), 401
    video = request.files.get("video")
    if not video:
        return jsonify({"error": "no_video"}), 400
    tmp = f"/tmp/yt_upload_{secrets.token_hex(8)}.mp4"
    video.save(tmp)
    try:
        result = youtube_api.upload_video(
            token, tmp,
            request.form.get("title", "Untitled"),
            request.form.get("description", ""),
            request.form.get("privacy", "private"))
        return jsonify(result)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


@app.route("/api/youtube/seo", methods=["POST"])
def yt_seo():
    data = request.get_json(force=True)
    user_id = data.get("user_id", "default")
    token = TOKENS.get(user_id, {}).get("youtube", {}).get("access_token", "")
    if not token:
        return jsonify({"error": "not_connected"}), 401
    result = youtube_api.update_video(
        token, data["video_id"],
        title=data.get("title"), description=data.get("description"),
        tags=data.get("tags"), category_id=data.get("category_id"),
        privacy=data.get("privacy"))
    return jsonify(result)


@app.route("/api/youtube/thumbnail", methods=["POST"])
def yt_thumbnail():
    user_id = request.form.get("user_id", "default")
    token = TOKENS.get(user_id, {}).get("youtube", {}).get("access_token", "")
    if not token:
        return jsonify({"error": "not_connected"}), 401
    img = request.files.get("thumbnail")
    if not img:
        return jsonify({"error": "no_image"}), 400
    tmp = f"/tmp/yt_thumb_{secrets.token_hex(8)}.jpg"
    img.save(tmp)
    try:
        result = youtube_api.set_thumbnail(token, request.form["video_id"], tmp)
        return jsonify(result)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ---------------------------------------------------------------------------
# TikTok OAuth + Upload
# ---------------------------------------------------------------------------
@app.route("/api/tiktok/auth-url", methods=["GET"])
def tt_auth_url():
    redirect = request.args.get("redirect_uri", "")
    url = tiktok_api.auth_url(redirect, secrets.token_hex(8))
    return jsonify({"auth_url": url})


@app.route("/api/tiktok/exchange", methods=["POST"])
def tt_exchange():
    data = request.get_json(force=True)
    result = tiktok_api.exchange_code(data["code"], data["redirect_uri"])
    user_id = data.get("user_id", "default")
    TOKENS.setdefault(user_id, {})["tiktok"] = result
    return jsonify({"ok": True})


@app.route("/api/tiktok/upload", methods=["POST"])
def tt_upload():
    data = request.get_json(force=True)
    user_id = data.get("user_id", "default")
    token = TOKENS.get(user_id, {}).get("tiktok", {}).get("access_token", "")
    if not token:
        return jsonify({"error": "not_connected"}), 401
    result = tiktok_api.publish_video(
        token, data.get("title", ""),
        video_url=data.get("video_url"),
        privacy=data.get("privacy", "PUBLIC_TO_EVERYONE"))
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
