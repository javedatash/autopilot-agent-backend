"""
YouTube Autopilot Agent - backend v0.1
OAuth2 (PKCE) + YouTube Data API v3 upload.

Secrets (client_id, client_secret, refresh_token) are NEVER stored here.
Pass them in at runtime from the Secure Vault / environment.
"""
import json
import urllib.parse
import urllib.request

CLIENT_ID = "839967876688-bk7d4tv9lvbm2vr9hr6sgkucabeohf58.apps.googleusercontent.com"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://www.googleapis.com/youtube/v3"
UPLOAD_BASE = "https://www.googleapis.com/upload/youtube/v3"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]
REDIRECT_URI = "http://localhost:8080/"


def build_auth_url(code_challenge: str) -> str:
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def exchange_code(code: str, code_verifier: str, client_secret: str) -> dict:
    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": client_secret,
        "code": code,
        "code_verifier": code_verifier,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data)
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def refresh_access_token(refresh_token: str, client_secret: str) -> dict:
    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data)
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def my_channels(access_token: str) -> dict:
    req = urllib.request.Request(
        API_BASE + "/channels?part=snippet,statistics&mine=true",
        headers={"Authorization": "Bearer " + access_token})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def upload_video(access_token: str, video_path: str, title: str,
                 description: str = "", privacy: str = "private",
                 category_id: str = "22") -> dict:
    metadata = {
        "snippet": {"title": title, "description": description,
                    "categoryId": category_id},
        "status": {"privacyStatus": privacy},
    }
    req = urllib.request.Request(
        UPLOAD_BASE + "/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(metadata).encode(),
        headers={"Authorization": "Bearer " + access_token,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        session_url = r.headers.get("Location")
    with open(video_path, "rb") as f:
        blob = f.read()
    up = urllib.request.Request(
        session_url, data=blob, method="PUT",
        headers={"Content-Type": "video/mp4",
                 "Content-Length": str(len(blob))})
    with urllib.request.urlopen(up) as r2:
        return json.load(r2)


# Verified 2026-10-13: OAuth PKCE flow + private test upload to
# Khamosh Alfaaz (UC6QhFUeSu1ur-qRXtaSVFRQ) succeeded.
# Test video id: 8ZVNlsAt2QU (private).
#
# 2026-10-14: OAuth re-done (tokens were lost in VM restart). Tested OK:
# - update_video (SEO: title/desc/tags/category/privacy) on 8ZVNlsAt2QU
# - set_thumbnail on 8ZVNlsAt2QU
# NOTE: no durable vault store fits Google's split-domain OAuth
# (accounts.google.com vs oauth2.googleapis.com), so refresh tokens live
# only for the session — re-auth after VM restart (2-min flow).


# ---------------------------------------------------------------------------
# Thumbnails
# ---------------------------------------------------------------------------
def set_thumbnail(access_token: str, video_id: str, image_path: str) -> dict:
    """Upload a custom thumbnail (JPG/PNG) for a video the user owns."""
    with open(image_path, "rb") as f:
        blob = f.read()
    ctype = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"
    req = urllib.request.Request(
        UPLOAD_BASE + "/thumbnails/set?videoId=" + urllib.parse.quote(video_id),
        data=blob, method="POST",
        headers={"Authorization": "Bearer " + access_token,
                 "Content-Type": ctype,
                 "Content-Length": str(len(blob))})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


# ---------------------------------------------------------------------------
# SEO / metadata update (title, description, tags, category, language, privacy)
# ---------------------------------------------------------------------------
def update_video(access_token: str, video_id: str, title: str = None,
                 description: str = None, tags: list = None,
                 category_id: str = None, language: str = None,
                 privacy: str = None, made_for_kids: bool = False) -> dict:
    """Update a video's metadata. Only provided fields are changed."""
    snippet = {}
    if title is not None:
        snippet["title"] = title
    if description is not None:
        snippet["description"] = description
    if tags is not None:
        snippet["tags"] = tags
    if category_id is not None:
        snippet["categoryId"] = category_id
    if language is not None:
        snippet["defaultLanguage"] = language
    status = {"madeForKids": made_for_kids,
              "selfDeclaredMadeForKids": made_for_kids}
    if privacy is not None:
        status["privacyStatus"] = privacy
    body = {"id": video_id}
    parts = []
    if snippet:
        body["snippet"] = snippet
        parts.append("snippet")
    if status:
        body["status"] = status
        parts.append("status")
    req = urllib.request.Request(
        API_BASE + "/videos?part=" + ",".join(parts),
        data=json.dumps(body).encode(), method="PUT",
        headers={"Authorization": "Bearer " + access_token,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


# ---------------------------------------------------------------------------
# Comments: list + reply (for AI-suggested, one-tap replies)
# ---------------------------------------------------------------------------
def list_comments(access_token: str, video_id: str, max_results: int = 20,
                  order: str = "time") -> dict:
    params = {"part": "snippet", "videoId": video_id,
              "maxResults": str(max_results), "order": order,
              "textFormat": "plainText"}
    req = urllib.request.Request(
        API_BASE + "/commentThreads?" + urllib.parse.urlencode(params),
        headers={"Authorization": "Bearer " + access_token})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def reply_to_comment(access_token: str, parent_id: str, text: str) -> dict:
    body = {"snippet": {"parentId": parent_id, "textOriginal": text}}
    req = urllib.request.Request(
        API_BASE + "/comments?part=snippet",
        data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": "Bearer " + access_token,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)
