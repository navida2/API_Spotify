import aiosqlite

DB_PATH = "app.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                spotify_id TEXT PRIMARY KEY,
                display_name TEXT,
                email TEXT,
                school TEXT,
                access_token TEXT,
                refresh_token TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS top_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spotify_id TEXT,
                track_id TEXT,
                track_name TEXT,
                artist_name TEXT,
                time_range TEXT,
                rank INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (spotify_id) REFERENCES users(spotify_id)
            )
        """)
        await db.commit()

async def save_user(spotify_id, display_name, email, access_token, refresh_token, school=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (spotify_id, display_name, email, access_token, refresh_token, school)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(spotify_id) DO UPDATE SET
                display_name = excluded.display_name,
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                school = COALESCE(excluded.school, users.school)
        """, (spotify_id, display_name, email, access_token, refresh_token, school))
        await db.commit()

async def save_top_tracks(spotify_id, tracks, time_range):
    async with aiosqlite.connect(DB_PATH) as db:
        # Clear old tracks for this user/time_range
        await db.execute(
            "DELETE FROM top_tracks WHERE spotify_id = ? AND time_range = ?",
            (spotify_id, time_range)
        )
        for rank, track in enumerate(tracks, 1):
            await db.execute("""
                INSERT INTO top_tracks (spotify_id, track_id, track_name, artist_name, time_range, rank)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                spotify_id,
                track["id"],
                track["name"],
                track["artists"][0]["name"],
                time_range,
                rank
            ))
        await db.commit()

async def get_school_top_tracks(school, time_range="short_term", limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT track_name, artist_name, COUNT(*) as listener_count
            FROM top_tracks
            JOIN users ON top_tracks.spotify_id = users.spotify_id
            WHERE users.school = ? AND top_tracks.time_range = ?
            GROUP BY track_id
            ORDER BY listener_count DESC
            LIMIT ?
        """, (school, time_range, limit))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def set_school(spotify_id, school):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET school = ? WHERE spotify_id = ?",
            (school, spotify_id)
        )
        await db.commit()