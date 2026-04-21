from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
import os
from urllib.parse import urlencode
import httpx
load_dotenv()

app = FastAPI()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
import os
from urllib.parse import urlencode

load_dotenv()
print("CLIENT_ID:", CLIENT_ID)
print("REDIRECT_URI:", REDIRECT_URI)
app = FastAPI()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
print("CLIENT_ID:", CLIENT_ID)
print("REDIRECT_URI:", REDIRECT_URI)
@app.get("/login")
def login():
    # Build the Spotify authorize URL with query params:
    # - client_id
    # - response_type (should be "code")
    # - redirect_uri
    # - scope (start with "user-read-private user-top-read")
    # Then return RedirectResponse(url)
    params = urlencode({
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "user-read-private user-top-read"
    })
    return RedirectResponse(f"https://accounts.spotify.com/authorize?{params}")
# Add this after your CLIENT_SECRET/REDIRECT_URI lines
token_store = {}

# Update your callback to save the token
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
    return {"message": "Logged in successfully"}

# Add this new route
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
    return response.json()

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
        # First get top tracks
        tracks_response = await client.get(
            f"https://api.spotify.com/v1/me/top/tracks?time_range={time_range}&limit={limit}",
            headers={"Authorization": f"Bearer {token_store['access_token']}"},
        )
        tracks = tracks_response.json()["items"]
        track_ids = ",".join([t["id"] for t in tracks])

        # Then get audio features for those tracks
        features_response = await client.get(
            f"https://api.spotify.com/v1/audio-features?ids={track_ids}",
            headers={"Authorization": f"Bearer {token_store['access_token']}"},
        )
    return features_response.json()

@app.get("/discover")
async def discover(time_range: str = "short_term", limit: int = 20):
    async with httpx.AsyncClient() as client:
        # Get top tracks and artists for seeds
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

        # Get audio features for your top tracks
        track_ids = ",".join([t["id"] for t in tracks])
        features_resp = await client.get(
            f"https://api.spotify.com/v1/audio-features?ids={track_ids}",
            headers={"Authorization": f"Bearer {token_store['access_token']}"},
        )
        features = [f for f in features_resp.json()["audio_features"] if f]

        # Calculate your averages
        avg = {}
        for key in ["danceability", "energy", "valence", "acousticness", "tempo"]:
            vals = [f[key] for f in features]
            avg[key] = round(sum(vals) / len(vals), 2) if vals else 0

        # Seeds: 3 tracks + 2 artists
        seed_tracks = ",".join([t["id"] for t in tracks[:3]])
        seed_artists = ",".join([a["id"] for a in artists[:2]])

        # Recommendations with your audio profile as targets
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