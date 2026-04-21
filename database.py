import aiosqlite
import os
import time

DB_PATH = os.getenv("DB_PATH", "app.db")

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
    domain = email.split("@")[-1].lower()
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
                token_expires_at INTEGER DEFAULT 0,
                image_url TEXT,
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS taste_battles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spotify_id TEXT,
                winner_school TEXT,
                loser_school TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_battles_winner ON taste_battles(winner_school)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_battles_loser ON taste_battles(loser_school)")
        # Helpful indexes for the queries that matter
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tt_user_range ON top_tracks(spotify_id, time_range)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tt_track_range ON top_tracks(track_id, time_range)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_school ON users(school)")
        await db.commit()


async def save_user(spotify_id, display_name, email, access_token, refresh_token,
                    expires_in=3600, school=None, image_url=None):
    expires_at = int(time.time()) + expires_in - 60  # refresh 1 min early
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (spotify_id, display_name, email, access_token, refresh_token,
                               token_expires_at, school, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(spotify_id) DO UPDATE SET
                display_name = excluded.display_name,
                email = COALESCE(excluded.email, users.email),
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                token_expires_at = excluded.token_expires_at,
                image_url = COALESCE(excluded.image_url, users.image_url),
                school = COALESCE(excluded.school, users.school)
        """, (spotify_id, display_name, email, access_token, refresh_token,
              expires_at, school, image_url))
        await db.commit()


async def update_tokens(spotify_id, access_token, expires_in, refresh_token=None):
    expires_at = int(time.time()) + expires_in - 60
    async with aiosqlite.connect(DB_PATH) as db:
        if refresh_token:
            await db.execute("""
                UPDATE users SET access_token = ?, refresh_token = ?, token_expires_at = ?
                WHERE spotify_id = ?
            """, (access_token, refresh_token, expires_at, spotify_id))
        else:
            await db.execute("""
                UPDATE users SET access_token = ?, token_expires_at = ?
                WHERE spotify_id = ?
            """, (access_token, expires_at, spotify_id))
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
                INSERT INTO top_tracks (spotify_id, track_id, track_name, artist_name,
                                        image_url, time_range, rank)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                spotify_id, track["id"], track["name"],
                track["artists"][0]["name"], image_url, time_range, rank,
            ))
        await db.commit()


async def get_user_top_tracks(spotify_id, time_range="short_term", limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT track_id, track_name, artist_name, image_url, rank
            FROM top_tracks
            WHERE spotify_id = ? AND time_range = ?
            ORDER BY rank ASC
            LIMIT ?
        """, (spotify_id, time_range, limit))
        return [dict(r) for r in await cursor.fetchall()]


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
                SELECT track_id, COUNT(*) as vote_count
                FROM track_votes
                WHERE school = ?
                GROUP BY track_id
            ) v ON t.track_id = v.track_id
            WHERE u.school = ? AND t.time_range = ?
            GROUP BY t.track_id
            ORDER BY listener_count DESC, vote_count DESC
            LIMIT ?
        """, (school, school, time_range, limit))
        return [dict(r) for r in await cursor.fetchall()]


async def get_school_stats(school, time_range="short_term"):
    """Aggregate stats for the hero: listener count, top artist, unique tracks."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT COUNT(DISTINCT u.spotify_id) as listeners,
                   COUNT(DISTINCT t.track_id) as unique_tracks
            FROM users u
            LEFT JOIN top_tracks t ON u.spotify_id = t.spotify_id AND t.time_range = ?
            WHERE u.school = ?
        """, (time_range, school))
        row = await cursor.fetchone()
        stats = dict(row) if row else {"listeners": 0, "unique_tracks": 0}

        cursor = await db.execute("""
            SELECT artist_name, COUNT(DISTINCT t.spotify_id) as fans
            FROM top_tracks t
            JOIN users u ON t.spotify_id = u.spotify_id
            WHERE u.school = ? AND t.time_range = ?
            GROUP BY artist_name
            ORDER BY fans DESC
            LIMIT 1
        """, (school, time_range))
        row = await cursor.fetchone()
        stats["top_artist"] = dict(row) if row else None
        return stats


async def set_school(spotify_id, school):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET school = ? WHERE spotify_id = ?",
            (school, spotify_id)
        )
        await db.commit()


async def vote_for_track(spotify_id, track_id, school):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO track_votes (spotify_id, track_id, school) VALUES (?, ?, ?)
            ON CONFLICT(spotify_id, school) DO UPDATE SET track_id = excluded.track_id
        """, (spotify_id, track_id, school))
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
    """Full leaderboard including zero-vote schools, with listener counts."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT s.school,
                   COALESCE(v.votes, 0) as votes,
                   COALESCE(l.listeners, 0) as listeners
            FROM (SELECT DISTINCT school FROM users WHERE school IS NOT NULL) s
            LEFT JOIN (
                SELECT voted_for as school, COUNT(*) as votes
                FROM school_votes GROUP BY voted_for
            ) v ON s.school = v.school
            LEFT JOIN (
                SELECT school, COUNT(*) as listeners
                FROM users WHERE school IS NOT NULL GROUP BY school
            ) l ON s.school = l.school
            ORDER BY votes DESC, listeners DESC
        """)
        return [dict(r) for r in await cursor.fetchall()]


async def get_user_school_vote(spotify_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT voted_for FROM school_votes WHERE spotify_id = ?",
            (spotify_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def get_listeners_also_like(spotify_id, time_range="short_term", limit=10):
    """People who share at least one track with you - what else do they listen to?"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            WITH my_tracks AS (
                SELECT track_id FROM top_tracks
                WHERE spotify_id = ? AND time_range = ?
            ),
            similar_users AS (
                SELECT DISTINCT spotify_id FROM top_tracks
                WHERE time_range = ?
                  AND track_id IN (SELECT track_id FROM my_tracks)
                  AND spotify_id != ?
            )
            SELECT t.track_name, t.artist_name, t.image_url, t.track_id,
                   COUNT(DISTINCT t.spotify_id) as listener_count
            FROM top_tracks t
            WHERE t.time_range = ?
              AND t.spotify_id IN (SELECT spotify_id FROM similar_users)
              AND t.track_id NOT IN (SELECT track_id FROM my_tracks)
            GROUP BY t.track_id
            ORDER BY listener_count DESC
            LIMIT ?
        """, (spotify_id, time_range, time_range, spotify_id, time_range, limit))
        return [dict(r) for r in await cursor.fetchall()]


async def get_school_compatibility(spotify_id, time_range="short_term"):
    """What % of the user's top tracks overlap with each school's top 50 tracks?
    Returns list sorted by compatibility descending."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT COUNT(*) as total FROM top_tracks
            WHERE spotify_id = ? AND time_range = ?
        """, (spotify_id, time_range))
        total = (await cursor.fetchone())["total"]
        if total == 0:
            return []

        cursor = await db.execute("""
            WITH school_tracks AS (
                SELECT u.school, t.track_id,
                       COUNT(DISTINCT t.spotify_id) as school_listeners
                FROM top_tracks t
                JOIN users u ON t.spotify_id = u.spotify_id
                WHERE u.school IS NOT NULL AND t.time_range = ?
                GROUP BY u.school, t.track_id
            ),
            my_tracks AS (
                SELECT track_id FROM top_tracks
                WHERE spotify_id = ? AND time_range = ?
            )
            SELECT st.school,
                   COUNT(DISTINCT st.track_id) as overlap,
                   (SELECT MAX(cnt) FROM (
                       SELECT COUNT(*) as cnt FROM top_tracks tt
                       JOIN users uu ON tt.spotify_id = uu.spotify_id
                       WHERE uu.school = st.school AND tt.time_range = ?
                       GROUP BY tt.track_id
                   )) as _unused
            FROM school_tracks st
            WHERE st.track_id IN (SELECT track_id FROM my_tracks)
            GROUP BY st.school
        """, (time_range, spotify_id, time_range, time_range))
        rows = await cursor.fetchall()

        results = []
        for r in rows:
            r = dict(r)
            results.append({
                "school": r["school"],
                "overlap": r["overlap"],
                "compatibility": round(100 * r["overlap"] / total),
            })
        # Fill in schools with 0 overlap
        present = {r["school"] for r in results}
        for s in SCHOOLS:
            if s not in present:
                results.append({"school": s, "overlap": 0, "compatibility": 0})
        results.sort(key=lambda x: x["compatibility"], reverse=True)
        return results


async def get_school_track_ids(school, time_range="short_term", limit=20):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT t.track_id, t.track_name, t.artist_name,
                   COUNT(DISTINCT t.spotify_id) as listener_count
            FROM top_tracks t
            JOIN users u ON t.spotify_id = u.spotify_id
            WHERE u.school = ? AND t.time_range = ?
            GROUP BY t.track_id
            ORDER BY listener_count DESC
            LIMIT ?
        """, (school, time_range, limit))
        return [dict(r) for r in await cursor.fetchall()]


async def get_schools_with_tracks(min_tracks=5):
    """Return schools that have at least N tracks (for battle matchups)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT u.school, COUNT(DISTINCT t.track_id) as track_count
            FROM users u
            JOIN top_tracks t ON u.spotify_id = t.spotify_id
            WHERE u.school IS NOT NULL AND t.time_range = 'short_term'
            GROUP BY u.school
            HAVING track_count >= ?
        """, (min_tracks,))
        return [r[0] for r in await cursor.fetchall()]


async def record_battle(spotify_id, winner_school, loser_school):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO taste_battles (spotify_id, winner_school, loser_school)
            VALUES (?, ?, ?)
        """, (spotify_id, winner_school, loser_school))
        await db.commit()


async def get_battle_leaderboard():
    """Rank schools by battle win rate. Wilson lower bound would be fancier,
    but raw win rate with a min-battle threshold is fine for this scale."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            WITH wins AS (
                SELECT winner_school as school, COUNT(*) as n
                FROM taste_battles GROUP BY winner_school
            ),
            losses AS (
                SELECT loser_school as school, COUNT(*) as n
                FROM taste_battles GROUP BY loser_school
            ),
            schools AS (
                SELECT DISTINCT school FROM users WHERE school IS NOT NULL
            )
            SELECT s.school,
                   COALESCE(w.n, 0) as wins,
                   COALESCE(l.n, 0) as losses,
                   COALESCE(w.n, 0) + COALESCE(l.n, 0) as battles
            FROM schools s
            LEFT JOIN wins w ON s.school = w.school
            LEFT JOIN losses l ON s.school = l.school
            ORDER BY
              CASE WHEN battles = 0 THEN 1 ELSE 0 END,
              CAST(wins AS REAL) / (wins + losses + 0.0001) DESC,
              battles DESC
        """)
        rows = [dict(r) for r in await cursor.fetchall()]
        for r in rows:
            total = r["wins"] + r["losses"]
            r["win_rate"] = round(100 * r["wins"] / total) if total > 0 else 0
        return rows