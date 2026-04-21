from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
import os
from urllib.parse import urlencode
import httpx
from database import (
    init_db, save_user, save_top_tracks, get_school_top_tracks,
    set_school, detect_school, SCHOOLS, get_listeners_also_like,
    get_school_track_ids, get_user, vote_for_track, get_user_track_vote,
    vote_for_school, get_school_rankings, get_user_school_vote
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
        "scope": "user-read-private user-top-read user-read-email playlist-modify-public"
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

    async with httpx.AsyncClient() as client:
        for tr in ["short_term", "medium_term", "long_term"]:
            tracks_resp = await client.get(
                f"https://api.spotify.com/v1/me/top/tracks?time_range={tr}&limit=50",
                headers={"Authorization": f"Bearer {token_store['access_token']}"},
            )
            tracks_data = tracks_resp.json()
            if "items" in tracks_data:
                await save_top_tracks(profile["id"], tracks_data["items"], tr)

    return RedirectResponse("http://localhost:5173")

@app.get("/me")
async def me():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.spotify.com/v1/me",
            headers={"Authorization": f"Bearer {token_store['access_token']}"},
        )
    profile = response.json()
    # Include school from DB
    user_data = await get_user(token_store.get("spotify_id"))
    if user_data:
        profile["school"] = user_data.get("school")
    return profile

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

@app.post("/vote-track")
async def vote_track(track_id: str, school: str):
    spotify_id = token_store.get("spotify_id")
    if not spotify_id:
        return {"error": "Not logged in"}
    user_data = await get_user(spotify_id)
    if not user_data or user_data.get("school") != school:
        return {"error": "You can only vote for tracks at your own school"}
    await vote_for_track(spotify_id, track_id, school)
    return {"message": "Vote recorded"}

@app.get("/my-track-vote")
async def my_track_vote(school: str):
    spotify_id = token_store.get("spotify_id")
    if not spotify_id:
        return {"vote": None}
    vote = await get_user_track_vote(spotify_id, school)
    return {"vote": vote}

@app.post("/vote-school")
async def vote_school_endpoint(voted_for: str):
    spotify_id = token_store.get("spotify_id")
    if not spotify_id:
        return {"error": "Not logged in"}
    if voted_for not in SCHOOLS:
        return {"error": "Invalid school"}
    user_data = await get_user(spotify_id)
    if user_data and user_data.get("school") == voted_for:
        return {"error": "You can't vote for your own school"}
    await vote_for_school(spotify_id, voted_for)
    return {"message": f"Voted for {voted_for}"}

@app.get("/school-rankings")
async def school_rankings():
    rankings = await get_school_rankings()
    return {"rankings": rankings}

@app.get("/my-school-vote")
async def my_school_vote():
    spotify_id = token_store.get("spotify_id")
    if not spotify_id:
        return {"vote": None}
    vote = await get_user_school_vote(spotify_id)
    return {"vote": vote}

@app.get("/listeners-also-like")
async def listeners_also_like(time_range: str = "short_term"):
    spotify_id = token_store.get("spotify_id")
    if not spotify_id:
        return {"error": "Not logged in"}
    tracks = await get_listeners_also_like(spotify_id, time_range)
    return {"tracks": tracks}

@app.get("/create-campus-playlist")
async def create_campus_playlist(school: str, time_range: str = "short_term"):
    if school not in SCHOOLS:
        return {"error": "Invalid school"}
    spotify_id = token_store.get("spotify_id")
    if not spotify_id:
        return {"error": "Not logged in"}

    tracks = await get_school_track_ids(school, time_range, limit=20)
    if not tracks:
        return {"error": "No tracks found for this school"}

    track_uris = [f"spotify:track:{t['track_id']}" for t in tracks]

    async with httpx.AsyncClient() as client:
        create_resp = await client.post(
            f"https://api.spotify.com/v1/users/{spotify_id}/playlists",
            headers={
                "Authorization": f"Bearer {token_store['access_token']}",
                "Content-Type": "application/json",
            },
            json={
                "name": f"{school} Top Tracks",
                "description": f"The most popular tracks at {school} right now",
                "public": True,
            },
        )
        playlist = create_resp.json()

        await client.post(
            f"https://api.spotify.com/v1/playlists/{playlist['id']}/tracks",
            headers={
                "Authorization": f"Bearer {token_store['access_token']}",
                "Content-Type": "application/json",
            },
            json={"uris": track_uris},
        )

    return {
        "message": f"Created '{school} Top Tracks' playlist",
        "playlist_url": playlist["external_urls"]["spotify"],
        "track_count": len(track_uris),
    }