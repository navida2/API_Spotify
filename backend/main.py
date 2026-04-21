import os
import time
import secrets
from contextlib import asynccontextmanager
from urllib.parse import urlencode
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Cookie
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from itsdangerous import URLSafeSerializer, BadSignature

from backend.database import (
    init_db, save_user, update_tokens, save_top_tracks, get_user_top_tracks,
    get_school_top_tracks, get_school_stats, set_school, detect_school, SCHOOLS,
    get_listeners_also_like, get_school_track_ids, get_user,
    vote_for_track, get_user_track_vote, vote_for_school, get_school_rankings,
    get_user_school_vote, get_school_compatibility,
    get_schools_with_tracks, record_battle, get_battle_leaderboard,
)

load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8080/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
SESSION_SECRET = os.getenv("SESSION_SECRET") or secrets.token_urlsafe(32)
COOKIE_NAME = "ucampus_session"
# In production, cookies must be Secure + SameSite=None for cross-site flow
IS_PROD = os.getenv("ENV") == "production"

serializer = URLSafeSerializer(SESSION_SECRET, salt="session")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)

# CORS — allow the deployed frontend to hit the backend with cookies
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Session helpers ----------

def set_session(response: Response, spotify_id: str):
    token = serializer.dumps({"sid": spotify_id, "iat": int(time.time())})
    response.set_cookie(
        COOKIE_NAME, token,
        httponly=True,
        samesite="none" if IS_PROD else "lax",
        secure=IS_PROD,
        path="/",
        max_age=60 * 60 * 24 * 30,
    )


def read_session(cookie_val: Optional[str]) -> Optional[str]:
    if not cookie_val:
        return None
    try:
        data = serializer.loads(cookie_val)
        return data.get("sid")
    except BadSignature:
        return None


async def get_current_user(request: Request) -> dict:
    """Auth dependency: returns the logged-in user or 401s."""
    sid = read_session(request.cookies.get(COOKIE_NAME))
    if not sid:
        raise HTTPException(status_code=401, detail="Not logged in")
    user = await get_user(sid)
    if not user:
        raise HTTPException(status_code=401, detail="Session invalid")
    return user


async def get_optional_user(request: Request) -> Optional[dict]:
    sid = read_session(request.cookies.get(COOKIE_NAME))
    if not sid:
        return None
    return await get_user(sid)


# ---------- Spotify token handling ----------

async def refresh_access_token(user: dict) -> str:
    """Use the stored refresh_token to get a new access_token."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": user["refresh_token"],
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Refresh failed; please re-login")
    data = resp.json()
    new_refresh = data.get("refresh_token")  # Spotify may rotate it
    await update_tokens(
        user["spotify_id"], data["access_token"],
        data.get("expires_in", 3600), refresh_token=new_refresh,
    )
    return data["access_token"]


async def get_valid_access_token(user: dict) -> str:
    if user.get("token_expires_at", 0) > int(time.time()):
        return user["access_token"]
    return await refresh_access_token(user)


async def spotify_get(user: dict, url: str) -> dict:
    """GET a Spotify URL, auto-refreshing on 401."""
    token = await get_valid_access_token(user)
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 401:
            token = await refresh_access_token(user)
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    return resp.json()


async def spotify_post(user: dict, url: str, json_body: dict) -> dict:
    token = await get_valid_access_token(user)
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=json_body,
        )
        if resp.status_code == 401:
            token = await refresh_access_token(user)
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=json_body,
            )
    resp.raise_for_status()
    return resp.json()


# ---------- Auth routes ----------

@app.get("/login")
def login():
    params = urlencode({
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "user-read-private user-top-read user-read-email playlist-modify-public",
    })
    return RedirectResponse(f"https://accounts.spotify.com/authorize?{params}")


@app.get("/callback")
async def callback(code: str, response: Response):
    async with httpx.AsyncClient(timeout=10.0) as client:
        token_resp = await client.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )
    if token_resp.status_code != 200:
        print(f"[callback] Spotify token exchange failed: {token_resp.status_code} {token_resp.text}")
        print(f"[callback] redirect_uri we sent: {REDIRECT_URI!r}")
        print(f"[callback] client_id we sent: {CLIENT_ID!r}")
        print(f"[callback] client_secret length: {len(CLIENT_SECRET) if CLIENT_SECRET else 0}")
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_resp.text}")
    token_data = token_resp.json()

    async with httpx.AsyncClient(timeout=10.0) as client:
        me_resp = await client.get(
            "https://api.spotify.com/v1/me",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
    profile = me_resp.json()

    school = detect_school(profile.get("email"))
    images = profile.get("images") or []
    image_url = images[0]["url"] if images else None

    await save_user(
        spotify_id=profile["id"],
        display_name=profile.get("display_name"),
        email=profile.get("email"),
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        expires_in=token_data.get("expires_in", 3600),
        school=school,
        image_url=image_url,
    )

    # Fetch top tracks for all time ranges
    user = await get_user(profile["id"])
    for tr in ("short_term", "medium_term", "long_term"):
        try:
            data = await spotify_get(
                user, f"https://api.spotify.com/v1/me/top/tracks?time_range={tr}&limit=50"
            )
            if "items" in data:
                await save_top_tracks(profile["id"], data["items"], tr)
        except Exception as e:
            print(f"[callback] failed to fetch {tr}: {e}")

    redirect = RedirectResponse(FRONTEND_URL)
    set_session(redirect, profile["id"])
    return redirect


@app.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


# ---------- User routes ----------

@app.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {
        "spotify_id": user["spotify_id"],
        "display_name": user["display_name"],
        "email": user["email"],
        "school": user["school"],
        "image_url": user["image_url"],
    }


@app.get("/top-tracks")
async def top_tracks(
    time_range: str = "short_term",
    limit: int = 10,
    user: dict = Depends(get_current_user),
):
    # Serve from DB first (fast), refresh in background could be added later
    cached = await get_user_top_tracks(user["spotify_id"], time_range, limit)
    if cached:
        return {"tracks": cached}
    # Fall back to Spotify
    data = await spotify_get(
        user, f"https://api.spotify.com/v1/me/top/tracks?time_range={time_range}&limit={limit}"
    )
    items = data.get("items", [])
    if items:
        await save_top_tracks(user["spotify_id"], items, time_range)
    return {"tracks": await get_user_top_tracks(user["spotify_id"], time_range, limit)}


# ---------- School routes ----------

@app.get("/schools")
def schools():
    return SCHOOLS


@app.post("/set-school")
async def set_school_endpoint(school: str, user: dict = Depends(get_current_user)):
    if school not in SCHOOLS:
        raise HTTPException(status_code=400, detail="Invalid school")
    await set_school(user["spotify_id"], school)
    return {"ok": True, "school": school}


@app.get("/school-top-tracks")
async def school_top_tracks(school: str, time_range: str = "short_term"):
    if school not in SCHOOLS:
        raise HTTPException(status_code=400, detail="Invalid school")
    tracks = await get_school_top_tracks(school, time_range)
    stats = await get_school_stats(school, time_range)
    return {"school": school, "top_tracks": tracks, "stats": stats}


@app.post("/vote-track")
async def vote_track(
    track_id: str,
    school: str,
    user: dict = Depends(get_current_user),
):
    if user.get("school") != school:
        raise HTTPException(
            status_code=403,
            detail="You can only vote at your own school. Set your school first.",
        )
    await vote_for_track(user["spotify_id"], track_id, school)
    return {"ok": True}


@app.get("/my-track-vote")
async def my_track_vote(school: str, user: dict = Depends(get_current_user)):
    return {"vote": await get_user_track_vote(user["spotify_id"], school)}


@app.post("/vote-school")
async def vote_school_endpoint(voted_for: str, user: dict = Depends(get_current_user)):
    if voted_for not in SCHOOLS:
        raise HTTPException(status_code=400, detail="Invalid school")
    if user.get("school") == voted_for:
        raise HTTPException(status_code=400, detail="You can't vote for your own school")
    await vote_for_school(user["spotify_id"], voted_for)
    return {"ok": True}


@app.get("/school-rankings")
async def school_rankings():
    return {"rankings": await get_school_rankings()}


@app.get("/my-school-vote")
async def my_school_vote(user: dict = Depends(get_current_user)):
    return {"vote": await get_user_school_vote(user["spotify_id"])}


# ---------- Discovery ----------

@app.get("/listeners-also-like")
async def listeners_also_like(
    time_range: str = "short_term",
    user: dict = Depends(get_current_user),
):
    tracks = await get_listeners_also_like(user["spotify_id"], time_range)
    return {"tracks": tracks}


@app.get("/compatibility")
async def compatibility(
    time_range: str = "short_term",
    user: dict = Depends(get_current_user),
):
    """Returns the user's taste compatibility with every school, sorted."""
    results = await get_school_compatibility(user["spotify_id"], time_range)
    return {"compatibility": results, "my_school": user.get("school")}


import random


@app.get("/battle/next")
async def battle_next(user: dict = Depends(get_current_user)):
    """Serve two random schools with their top 5 tracks, labeled A and B.
    School names are NOT returned - only after the user votes."""
    eligible = await get_schools_with_tracks(min_tracks=5)
    if len(eligible) < 2:
        raise HTTPException(status_code=404, detail="Not enough schools with tracks yet")

    a_school, b_school = random.sample(eligible, 2)
    a_tracks = await get_school_top_tracks(a_school, "short_term", limit=5)
    b_tracks = await get_school_top_tracks(b_school, "short_term", limit=5)

    # Strip anything revealing the school from the track payload
    def sanitize(tracks):
        return [
            {"track_id": t["track_id"], "track_name": t["track_name"],
             "artist_name": t["artist_name"], "image_url": t["image_url"]}
            for t in tracks
        ]

    return {
        "a": {"tracks": sanitize(a_tracks), "_school": a_school},
        "b": {"tracks": sanitize(b_tracks), "_school": b_school},
    }


@app.post("/battle/vote")
async def battle_vote(
    winner: str,
    loser: str,
    user: dict = Depends(get_current_user),
):
    """Record a battle outcome. The frontend sends the real school names
    that it got from /battle/next, after the user clicks a side."""
    if winner not in SCHOOLS or loser not in SCHOOLS or winner == loser:
        raise HTTPException(status_code=400, detail="Invalid matchup")
    await record_battle(user["spotify_id"], winner, loser)
    return {"ok": True, "winner": winner, "loser": loser}


@app.get("/battle/leaderboard")
async def battle_leaderboard():
    return {"rankings": await get_battle_leaderboard()}


# ---------- Playlist ----------

@app.post("/create-campus-playlist")
async def create_campus_playlist(
    school: str,
    time_range: str = "short_term",
    user: dict = Depends(get_current_user),
):
    if school not in SCHOOLS:
        raise HTTPException(status_code=400, detail="Invalid school")

    tracks = await get_school_track_ids(school, time_range, limit=20)
    if not tracks:
        raise HTTPException(status_code=404, detail="No tracks found for this school yet")

    track_uris = [f"spotify:track:{t['track_id']}" for t in tracks]

    playlist = await spotify_post(
        user,
        f"https://api.spotify.com/v1/users/{user['spotify_id']}/playlists",
        {
            "name": f"{school} - Campus Top 20",
            "description": f"What {school} is listening to right now. Built with UCampus.",
            "public": True,
        },
    )

    await spotify_post(
        user,
        f"https://api.spotify.com/v1/playlists/{playlist['id']}/tracks",
        {"uris": track_uris},
    )

    return {
        "playlist_url": playlist["external_urls"]["spotify"],
        "track_count": len(track_uris),
    }