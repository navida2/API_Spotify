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