from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
import os
from urllib.parse import urlencode
import httpx
from database import (
    init_db, save_user, save_top_tracks, get_school_top_tracks,
    set_school, detect_school, SCHOOLS
)

load_dotenv()

app = FastAPI()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

token_store = {}

@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/login")
def login():
    params = urlencode({
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "user-read-private user-top-read user-read-email"
    })
    return RedirectResponse(f"https://accounts.spotify.com/authorize?{params}")

@app.get("/callback")
async def callback(code: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )
    token_data = response.json()
    token_store["access_token"] = token_data["access_token"]
    token_store["refresh_token"] = token_data["refresh_token"]

    async with httpx.AsyncClient() as client:
        me_resp = await client.get(
            "https://api.spotify.com/v1/me",
            headers={"Authorization": f"Bearer {token_store['access_token']}"},
        )
    profile = me_resp.json()
    token_store["spotify_id"] = profile["id"]

    school = detect_school(profile.get("email"))
    await save_user(
        spotify_id=profile["id"],
        display_name=profile.get("display_name"),
        email=profile.get("email"),
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        school=school,
    )
    # Auto-save top tracks to DB
    async with httpx.AsyncClient() as client:
        for tr in ["short_term", "medium_term", "long_term"]:
            tracks_resp = await client.get(
                f"https://api.spotify.com/v1/me/top/tracks?time_range={tr}&limit=50",
                headers={"Authorization": f"Bearer {token_store['access_token']}"},
            )
            tracks_data = tracks_resp.json()
            if "items" in tracks_data:
                await save_top_tracks(profile["id"], tracks_data["items"], tr)

    return {"message": "Logged in successfully", "user": profile["display_name"], "school": school}

@app.get("/me")
async def me():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.spotify.com/v1/me",
            headers={"Authorization": f"Bearer {token_store['access_token']}"},
        )
    return response.json()

@app.get("/top-tracks")
async def top_tracks(time_range: str = "short_term", limit: int = 10):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.spotify.com/v1/me/top/tracks?time_range={time_range}&limit={limit}",
            headers={"Authorization": f"Bearer {token_store['access_token']}"},
        )
    tracks = response.json()
    if "items" in tracks:
        await save_top_tracks(token_store["spotify_id"], tracks["items"], time_range)
    return tracks

@app.get("/top-artists")
async def top_artists(time_range: str = "short_term", limit: int = 10):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.spotify.com/v1/me/top/artists?time_range={time_range}&limit={limit}",
            headers={"Authorization": f"Bearer {token_store['access_token']}"},
        )
    return response.json()

@app.get("/audio-features")
async def audio_features(time_range: str = "short_term", limit: int = 10):
    async with httpx.AsyncClient() as client:
        tracks_response = await client.get(
            f"https://api.spotify.com/v1/me/top/tracks?time_range={time_range}&limit={limit}",
            headers={"Authorization": f"Bearer {token_store['access_token']}"},
        )
        tracks = tracks_response.json()["items"]
        track_ids = ",".join([t["id"] for t in tracks])
        features_response = await client.get(
            f"https://api.spotify.com/v1/audio-features?ids={track_ids}",
            headers={"Authorization": f"Bearer {token_store['access_token']}"},
        )
    return features_response.json()

@app.get("/discover")
async def discover(time_range: str = "short_term", limit: int = 20):
    async with httpx.AsyncClient() as client:
        tracks_resp = await client.get(
            f"https://api.spotify.com/v1/me/top/tracks?time_range={time_range}&limit=5",
            headers={"Authorization": f"Bearer {token_store['access_token']}"},
        )
        tracks = tracks_resp.json()["items"]

        artists_resp = await client.get(
            f"https://api.spotify.com/v1/me/top/artists?time_range={time_range}&limit=5",
            headers={"Authorization": f"Bearer {token_store['access_token']}"},
        )
        artists = artists_resp.json()["items"]

        track_ids = ",".join([t["id"] for t in tracks])
        features_resp = await client.get(
            f"https://api.spotify.com/v1/audio-features?ids={track_ids}",
            headers={"Authorization": f"Bearer {token_store['access_token']}"},
        )
        features = [f for f in features_resp.json()["audio_features"] if f]

        avg = {}
        for key in ["danceability", "energy", "valence", "acousticness", "tempo"]:
            vals = [f[key] for f in features]
            avg[key] = round(sum(vals) / len(vals), 2) if vals else 0

        seed_tracks = ",".join([t["id"] for t in tracks[:3]])
        seed_artists = ",".join([a["id"] for a in artists[:2]])

        recs_resp = await client.get(
            f"https://api.spotify.com/v1/recommendations"
            f"?seed_tracks={seed_tracks}"
            f"&seed_artists={seed_artists}"
            f"&limit={limit}"
            f"&target_danceability={avg['danceability']}"
            f"&target_energy={avg['energy']}"
            f"&target_valence={avg['valence']}"
            f"&target_acousticness={avg['acousticness']}"
            f"&target_tempo={avg['tempo']}",
            headers={"Authorization": f"Bearer {token_store['access_token']}"},
        )
        recs = recs_resp.json()["tracks"]

        results = []
        for t in recs:
            results.append({
                "name": t["name"],
                "artist": t["artists"][0]["name"],
                "album": t["album"]["name"],
                "preview_url": t["preview_url"],
                "spotify_url": t["external_urls"]["spotify"],
                "image": t["album"]["images"][0]["url"] if t["album"]["images"] else None,
            })

    return {
        "seeds": {
            "tracks": [t["name"] for t in tracks[:3]],
            "artists": [a["name"] for a in artists[:2]],
        },
        "audio_profile": avg,
        "recommendations": results,
    }

@app.get("/schools")
def schools():
    return SCHOOLS

@app.post("/set-school")
async def update_school(school: str):
    if school not in SCHOOLS:
        return {"error": "Invalid school"}
    spotify_id = token_store.get("spotify_id")
    if not spotify_id:
        return {"error": "Not logged in"}
    await set_school(spotify_id, school)
    return {"message": f"School set to {school}"}

@app.get("/school-top-tracks")
async def school_top_tracks(school: str, time_range: str = "short_term"):
    if school not in SCHOOLS:
        return {"error": "Invalid school"}
    tracks = await get_school_top_tracks(school, time_range)
    return {"school": school, "top_tracks": tracks}