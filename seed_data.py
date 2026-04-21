import sqlite3
import random

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

# Pool of real popular tracks with Spotify IDs and image URLs
TRACKS = [
    ("0VjIjW4GlUZAMYd2vXMi3b", "Blinding Lights", "The Weeknd", "https://i.scdn.co/image/ab67616d0000b2738863bc11d2aa12b54f5aeb36"),
    ("7qiZfU4dY1lWllzX7mPBI3", "Shape of You", "Ed Sheeran", "https://i.scdn.co/image/ab67616d0000b273ba5db46f4b838ef6027e6f96"),
    ("3n3Ppam7vgaVa1iaRUc9Lp", "Mr. Brightside", "The Killers", "https://i.scdn.co/image/ab67616d0000b273ccdddd46119a4ff53eaf1f5d"),
    ("4cOdK2wGLETKBW3PvgPWqT", "Never Gonna Give You Up", "Rick Astley", "https://i.scdn.co/image/ab67616d0000b27315b811d70c37fcf7e24e7b03"),
    ("1zi7xx7UVEFkmKfv06H8x0", "One Dance", "Drake", "https://i.scdn.co/image/ab67616d0000b273fcf75ead8a32ac0020d2ce86"),
    ("2Fxmhks0bxGSBdJ92vM42m", "bad guy", "Billie Eilish", "https://i.scdn.co/image/ab67616d0000b27350a3147b4edd7701a876c6ce"),
    ("6habFhsOp2NvshLv26DqMb", "Levitating", "Dua Lipa", "https://i.scdn.co/image/ab67616d0000b273bd26ede1ae69327010d49946"),
    ("0e7ipj03S05BNilyu5bRzt", "rockstar", "Post Malone", "https://i.scdn.co/image/ab67616d0000b2739478c87599550dd73bfa7e02"),
    ("3KkXRkHbMCARz0aVfEt68P", "Sunflower", "Post Malone", "https://i.scdn.co/image/ab67616d0000b273e2e352d89826aef6dbd5ff8f"),
    ("5HCyWlXZPP0y6Gqq8TgA20", "HUMBLE.", "Kendrick Lamar", "https://i.scdn.co/image/ab67616d0000b2738b52c6b9bc4e43d873869699"),
    ("2LBqCSwhJGcFQeTHMVGwy3", "Die For You", "The Weeknd", "https://i.scdn.co/image/ab67616d0000b2734718e2b124f79258be7571c1"),
    ("7x9aauaA9cu6tyfpHnqDLo", "Starboy", "The Weeknd", "https://i.scdn.co/image/ab67616d0000b2734718e2b124f79258be7571c1"),
    ("0pqnGhzmwnNhPidYXDuK3l", "Sicko Mode", "Travis Scott", "https://i.scdn.co/image/ab67616d0000b273072e9faef2ef7b6db63834a3"),
    ("2xLMifQCjDGFmkHkpNLD9h", "STAY", "The Kid LAROI", "https://i.scdn.co/image/ab67616d0000b273a8b4a48c030e87b709e77053"),
    ("6AI3ezQ4o3HUoP6Dhudph3", "Peaches", "Justin Bieber", "https://i.scdn.co/image/ab67616d0000b2738913bc0a0b64cb1c16bfcdd9"),
    ("1BxfuPKGuaTgP7aM0Bbdwh", "Heat Waves", "Glass Animals", "https://i.scdn.co/image/ab67616d0000b273712a838c4ecfc751a0533b52"),
    ("5QO79kh1waicV47BqGRL3g", "Save Your Tears", "The Weeknd", "https://i.scdn.co/image/ab67616d0000b2638863bc11d2aa12b54f5aeb36"),
    ("4Dvkj6JhhA12EX05fT7y2e", "As It Was", "Harry Styles", "https://i.scdn.co/image/ab67616d0000b2732e8ed79e177ff6011076f5f0"),
    ("0yLdNVWF3Srea0uzk55zFo", "Circles", "Post Malone", "https://i.scdn.co/image/ab67616d0000b27339c8e6eb0dc76fa4c2a891bd"),
    ("3USxtqRwSYz57Ewm6wWRMp", "Mood", "24kGoldn", "https://i.scdn.co/image/ab67616d0000b2738de7a26537e6e71bf4fe2ef4"),
    ("2SAqBLGA283SUiwMznrfVG", "montero", "Lil Nas X", "https://i.scdn.co/image/ab67616d0000b273be82673b5f79d9658ec0a9a1"),
    ("3Ofmpyhv5UAQ70mENLoCZh", "Butter", "BTS", "https://i.scdn.co/image/ab67616d0000b2732c8b88ef4a43feeb1dce1049"),
    ("0TK2YIli9AX0LEap0WbNcN", "positions", "Ariana Grande", "https://i.scdn.co/image/ab67616d0000b2735ef878a782c987d38d82b605"),
    ("6WrI0LAC5M1Rw2MnX2ZvEg", "Good Days", "SZA", "https://i.scdn.co/image/ab67616d0000b2730c471c36970b9406233842a5"),
    ("0SF5hRPVBG8SG1KbDO6oMK", "Kiss Me More", "Doja Cat", "https://i.scdn.co/image/ab67616d0000b2734df3245f26298a1579ecc321"),
    ("4fouWK6XVHhzl78KzQ1UjL", "Industry Baby", "Lil Nas X", "https://i.scdn.co/image/ab67616d0000b273be82673b5f79d9658ec0a9a1"),
    ("5uEYRdEIh9Bo4fpjDd4Na9", "Goosebumps", "Travis Scott", "https://i.scdn.co/image/ab67616d0000b273f54b99bf27cda88f4a7f7f07"),
    ("2dHHgzDwk4BJdRYgS804Y0", "Night Changes", "One Direction", "https://i.scdn.co/image/ab67616d0000b273535a40fb5e9b8bd8e498d2f5"),
    ("6RUKPb4LETWmmr3iAEQktW", "Something In The Way", "Nirvana", "https://i.scdn.co/image/ab67616d0000b2737a393b04e8ced571618223e8"),
    ("3eR23VReFzcdmS7TYCrhCe", "Redbone", "Childish Gambino", "https://i.scdn.co/image/ab67616d0000b273d6c04e4b41f6e05e1ddc9a22"),
]

def seed():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    user_count = 0
    for school in SCHOOLS:
        num_users = random.randint(15, 40)
        school_tracks = random.sample(TRACKS, min(len(TRACKS), 20))

        for i in range(num_users):
            user_id = f"fake_{school.replace(' ', '_').lower()}_{i}"
            display_name = f"User {i+1}"
            email = f"{user_id}@example.com"

            c.execute("""
                INSERT OR IGNORE INTO users (spotify_id, display_name, email, school, access_token, refresh_token)
                VALUES (?, ?, ?, ?, 'fake_token', 'fake_refresh')
            """, (user_id, display_name, email, school))

            # Each user gets 10-20 random tracks from the school pool
            num_tracks = random.randint(10, 20)
            user_tracks = random.sample(school_tracks, min(num_tracks, len(school_tracks)))

            # Clear existing
            c.execute("DELETE FROM top_tracks WHERE spotify_id = ? AND time_range = 'short_term'", (user_id,))

            for rank, (track_id, track_name, artist_name, image_url) in enumerate(user_tracks, 1):
                c.execute("""
                    INSERT INTO top_tracks (spotify_id, track_id, track_name, artist_name, image_url, time_range, rank)
                    VALUES (?, ?, ?, ?, ?, 'short_term', ?)
                """, (user_id, track_id, track_name, artist_name, image_url, rank))

            user_count += 1

    # Add some track votes
    c.execute("SELECT spotify_id, school FROM users WHERE school IS NOT NULL AND spotify_id LIKE 'fake_%'")
    fake_users = c.fetchall()
    for user_id, school in fake_users:
        if random.random() < 0.6:  # 60% of users vote
            # Pick a random track from their school
            c.execute("""
                SELECT DISTINCT track_id FROM top_tracks t
                JOIN users u ON t.spotify_id = u.spotify_id
                WHERE u.school = ? AND t.time_range = 'short_term'
                LIMIT 20
            """, (school,))
            tracks = [r[0] for r in c.fetchall()]
            if tracks:
                voted_track = random.choice(tracks)
                c.execute("""
                    INSERT OR IGNORE INTO track_votes (spotify_id, track_id, school)
                    VALUES (?, ?, ?)
                """, (user_id, voted_track, school))

    # Add some school votes
    for user_id, school in fake_users:
        if random.random() < 0.5:  # 50% vote for best taste
            other_schools = [s for s in SCHOOLS if s != school]
            voted_for = random.choice(other_schools)
            c.execute("""
                INSERT OR IGNORE INTO school_votes (spotify_id, voted_for)
                VALUES (?, ?)
            """, (user_id, voted_for))

    conn.commit()
    conn.close()

    print(f"Seeded {user_count} fake users across {len(SCHOOLS)} schools")
    print("Track votes and school votes added")
    print("Done!")

if __name__ == "__main__":
    seed()