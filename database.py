import aiosqlite

DB_PATH = "app.db"

SCHOOLS = [
    "UC Berkeley",
    "UC Davis",
    "UC Irvine",
    "UC Los Angeles",
    "UC Merced",
    "UC Riverside",
    "UC San Diego",
    "UC San Francisco",
    "UC Santa Barbara",
    "UC Santa Cruz",
]

SCHOOL_DOMAINS = {
    "uci.edu": "UC Irvine",
    "berkeley.edu": "UC Berkeley",
    "ucla.edu": "UC Los Angeles",
    "ucsd.edu": "UC San Diego",
    "ucdavis.edu": "UC Davis",
    "ucsb.edu": "UC Santa Barbara",
    "ucsc.edu": "UC Santa Cruz",
    "ucr.edu": "UC Riverside",
    "ucmerced.edu": "UC Merced",
    "ucsf.edu": "UC San Francisco",
}

def detect_school(email):
    if not email:
        return None
    domain = email.split("@")[-1]
    return SCHOOL_DOMAINS.get(domain)

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
                image_url TEXT,
                time_range TEXT,
                rank INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (spotify_id) REFERENCES users(spotify_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS track_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spotify_id TEXT,
                track_id TEXT,
                school TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(spotify_id, school)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS school_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spotify_id TEXT,
                voted_for TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(spotify_id)
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

async def get_user(spotify_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE spotify_id = ?", (spotify_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def save_top_tracks(spotify_id, tracks, time_range):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM top_tracks WHERE spotify_id = ? AND time_range = ?",
            (spotify_id, time_range)
        )
        for rank, track in enumerate(tracks, 1):
            images = track.get("album", {}).get("images", [])
            image_url = images[0]["url"] if images else None
            await db.execute("""
                INSERT INTO top_tracks (spotify_id, track_id, track_name, artist_name, image_url, time_range, rank)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                spotify_id,
                track["id"],
                track["name"],
                track["artists"][0]["name"],
                image_url,
                time_range,
                rank
            ))
        await db.commit()

async def get_school_top_tracks(school, time_range="short_term", limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT t.track_name, t.artist_name, t.image_url, t.track_id,
                   COUNT(DISTINCT t.spotify_id) as listener_count,
                   COALESCE(v.vote_count, 0) as vote_count
            FROM top_tracks t
            JOIN users u ON t.spotify_id = u.spotify_id
            LEFT JOIN (
                SELECT track_id, school, COUNT(*) as vote_count
                FROM track_votes
                WHERE school = ?
                GROUP BY track_id
            ) v ON t.track_id = v.track_id
            WHERE u.school = ? AND t.time_range = ?
            GROUP BY t.track_id
            ORDER BY listener_count DESC
            LIMIT ?
        """, (school, school, time_range, limit))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def set_school(spotify_id, school):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET school = ? WHERE spotify_id = ?",
            (school, spotify_id)
        )
        await db.commit()

async def vote_for_track(spotify_id, track_id, school):
    async with aiosqlite.connect(DB_PATH) as db:
        # Check if user already voted for this school
        cursor = await db.execute(
            "SELECT id, track_id FROM track_votes WHERE spotify_id = ? AND school = ?",
            (spotify_id, school)
        )
        existing = await cursor.fetchone()
        if existing:
            # Change vote
            await db.execute(
                "UPDATE track_votes SET track_id = ? WHERE spotify_id = ? AND school = ?",
                (track_id, spotify_id, school)
            )
        else:
            await db.execute(
                "INSERT INTO track_votes (spotify_id, track_id, school) VALUES (?, ?, ?)",
                (spotify_id, track_id, school)
            )
        await db.commit()

async def get_user_track_vote(spotify_id, school):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT track_id FROM track_votes WHERE spotify_id = ? AND school = ?",
            (spotify_id, school)
        )
        row = await cursor.fetchone()
        return row[0] if row else None

async def vote_for_school(spotify_id, voted_for):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO school_votes (spotify_id, voted_for) VALUES (?, ?)
            ON CONFLICT(spotify_id) DO UPDATE SET voted_for = excluded.voted_for
        """, (spotify_id, voted_for))
        await db.commit()

async def get_school_rankings():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT voted_for as school, COUNT(*) as votes
            FROM school_votes
            GROUP BY voted_for
            ORDER BY votes DESC
        """)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_user_school_vote(spotify_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT voted_for FROM school_votes WHERE spotify_id = ?",
            (spotify_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None

async def get_listeners_also_like(spotify_id, time_range="short_term", limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT t3.track_name, t3.artist_name, t3.image_url, t3.track_id, COUNT(DISTINCT t3.spotify_id) as listener_count
            FROM top_tracks t1
            JOIN top_tracks t2 ON t1.spotify_id != t2.spotify_id
                AND t1.track_id = t2.track_id
                AND t1.time_range = t2.time_range
            JOIN top_tracks t3 ON t2.spotify_id = t3.spotify_id
                AND t3.time_range = t2.time_range
            WHERE t1.spotify_id = ?
                AND t1.time_range = ?
                AND t3.track_id NOT IN (
                    SELECT track_id FROM top_tracks
                    WHERE spotify_id = ? AND time_range = ?
                )
            GROUP BY t3.track_id
            ORDER BY listener_count DESC
            LIMIT ?
        """, (spotify_id, time_range, spotify_id, time_range, limit))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_school_track_ids(school, time_range="short_term", limit=20):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT track_id, track_name, artist_name, COUNT(*) as listener_count
            FROM top_tracks
            JOIN users ON top_tracks.spotify_id = users.spotify_id
            WHERE users.school = ? AND top_tracks.time_range = ?
            GROUP BY track_id
            ORDER BY listener_count DESC
            LIMIT ?
        """, (school, time_range, limit))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]