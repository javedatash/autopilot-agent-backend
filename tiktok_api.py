# tiktok_api.py — TikTok Content Posting API module for the Autopilot Agent app.
#
# Phase: 2 (one-by-one: Facebook -> Instagram -> TikTok — javed 2026-10-14)
# Each customer connects their OWN TikTok account via OAuth.
# Docs: https://developers.tiktok.com/docs/en/content-posting-api-get-started-upload-content
#
# TikTok setup needed (one-time, by javed):
#   1. developers.tiktok.com -> Create App
#   2. Add "Content Posting API" product, request scopes: video.upload, video.publish, user.info.basic
#   3. App Review required before public use (unaudited apps: video.publish needs private account)
#   4. API is FREE (no per-call fee) — we pay only our own hosting.
#
# Two modes:
#   - DIRECT POST (scope video.publish): publishes straight to the creator's feed.
#   - INBOX UPLOAD (scope video.upload): lands in creator's TikTok drafts inbox.

import json
import urllib.parse
import urllib.request

API = "https://open.tiktokapis.com/v2"
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"

CLIENT_KEY = "awca0xblypj854t3"  # "Autopilot Agent" TikTok app (created 2026-10-14, App ID 7696376195096512533)

def _client_secret():
    """Client secret lives in a 600-perm file, never in code/chat."""
    import os
    p = os.path.expanduser("~/workspace/goals/youtube-autopilot-agent-app-apk-bana-kar-bechna/hidden_files/tiktok_client_secret.txt")
    try:
        with open(p) as f:
            return f.read().strip()
    except OSError:
        return os.environ.get("TIKTOK_CLIENT_SECRET", "")  # set at deploy time

CLIENT_SECRET = ""  # use _client_secret() at runtime

SCOPES = ["video.upload", "video.publish", "user.info.basic"]


def auth_url(redirect_uri, state=""):
    q = urllib.parse.urlencode({
        "client_key": CLIENT_KEY,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": ",".join(SCOPES),
        "state": state,
    })
    return f"{AUTH_URL}?{q}"


def _call(path, token, payload):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json; charset=UTF-8"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def exchange_code(code, redirect_uri):
    payload = {"client_key": CLIENT_KEY, "client_secret": _client_secret(),
               "code": code, "grant_type": "authorization_code",
               "redirect_uri": redirect_uri}
    req = urllib.request.Request(API + "/oauth/token/",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def refresh_token(refresh_token):
    payload = {"client_key": CLIENT_KEY, "client_secret": _client_secret(),
               "grant_type": "refresh_token", "refresh_token": refresh_token}
    req = urllib.request.Request(API + "/oauth/token/",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def creator_info(token):
    """Limits for this creator (max durations, privacy options...)."""
    return _call("/post/publish/creator_info/query/", token, {})


def publish_video(token, title, video_url=None, file_size=None,
                  privacy="PUBLIC_TO_EVERYONE", direct=True):
    """Start a publish. video_url = PULL_FROM_URL (server-hosted, domain must be
    verified in the TikTok app dashboard). file_size set -> FILE_UPLOAD (chunked)."""
    if video_url:
        source_info = {"source": "PULL_FROM_URL", "video_url": video_url}
    else:
        source_info = {"source": "FILE_UPLOAD", "video_size": file_size,
                       "chunk_size": file_size, "total_chunk_count": 1}
    payload = {"post_info": {"title": title, "privacy_level": privacy},
               "source_info": source_info}
    path = "/post/publish/video/init/" if direct else "/post/publish/inbox/video/init/"
    return _call(path, token, payload)


def upload_chunk(upload_url, chunk_bytes, start, end, total):
    """PUT one chunk for FILE_UPLOAD mode."""
    req = urllib.request.Request(
        upload_url, data=chunk_bytes, method="PUT",
        headers={"Content-Type": "video/mp4",
                 "Content-Length": str(len(chunk_bytes)),
                 "Content-Range": f"bytes {start}-{end}/{total}"})
    with urllib.request.urlopen(req) as r:
        return r.status


def publish_status(token, publish_id):
    return _call("/post/publish/status/fetch/", token, {"publish_id": publish_id})
