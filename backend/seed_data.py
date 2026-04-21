"""Seeds 100 fake users, biased toward YOUR real tracks so discovery works.
Run: python seed_100.py"""
import sqlite3, random

DB_PATH = "app.db"
SCHOOLS = ["UC Berkeley","UC Davis","UC Irvine","UC Los Angeles","UC Merced",
           "UC Riverside","UC San Diego","UC San Francisco","UC Santa Barbara","UC Santa Cruz"]

BACKUP = [
    ("0VjIjW4GlUZAMYd2vXMi3b","Blinding Lights","The Weeknd","https://i.scdn.co/image/ab67616d0000b2738863bc11d2aa12b54f5aeb36"),
    ("3n3Ppam7vgaVa1iaRUc9Lp","Mr. Brightside","The Killers","https://i.scdn.co/image/ab67616d0000b273ccdddd46119a4ff53eaf1f5d"),
    ("2Fxmhks0bxGSBdJ92vM42m","bad guy","Billie Eilish","https://i.scdn.co/image/ab67616d0000b27350a3147b4edd7701a876c6ce"),
    ("6habFhsOp2NvshLv26DqMb","Levitating","Dua Lipa","https://i.scdn.co/image/ab67616d0000b273bd26ede1ae69327010d49946"),
    ("5HCyWlXZPP0y6Gqq8TgA20","HUMBLE.","Kendrick Lamar","https://i.scdn.co/image/ab67616d0000b2738b52c6b9bc4e43d873869699"),
    ("1BxfuPKGuaTgP7aM0Bbdwh","Heat Waves","Glass Animals","https://i.scdn.co/image/ab67616d0000b273712a838c4ecfc751a0533b52"),
    ("3eR23VReFzcdmS7TYCrhCe","Redbone","Childish Gambino","https://i.scdn.co/image/ab67616d0000b273d6c04e4b41f6e05e1ddc9a22"),
    ("4Li2WHPkuyCdtmokzW2007","Kill Bill","SZA","https://i.scdn.co/image/ab67616d0000b273070d80f73cfd42d5d0a58ac0"),
    ("6PQ88X9TkUIAUIZJHL2b8A","Cruel Summer","Taylor Swift","https://i.scdn.co/image/ab67616d0000b273e787cffec20aa2a396a61647"),
    ("4ZtFanR9U6ndgddUvNcjcG","good 4 u","Olivia Rodrigo","https://i.scdn.co/image/ab67616d0000b273a91c10fe9472d9bd89802e5a"),
    ("0pqnGhzmwnNhPidYXDuK3l","Sicko Mode","Travis Scott","https://i.scdn.co/image/ab67616d0000b273072e9faef2ef7b6db63834a3"),
    ("4Dvkj6JhhA12EX05fT7y2e","As It Was","Harry Styles","https://i.scdn.co/image/ab67616d0000b2732e8ed79e177ff6011076f5f0"),
    ("6WrI0LAC5M1Rw2MnX2ZvEg","Good Days","SZA","https://i.scdn.co/image/ab67616d0000b2730c471c36970b9406233842a5"),
    ("4fouWK6XVHhzl78KzQ1UjL","Industry Baby","Lil Nas X","https://i.scdn.co/image/ab67616d0000b273be82673b5f79d9658ec0a9a1"),
    ("2xLMifQCjDGFmkHkpNLD9h","STAY","The Kid LAROI","https://i.scdn.co/image/ab67616d0000b273a8b4a48c030e87b709e77053"),
    ("3KkXRkHbMCARz0aVfEt68P","Sunflower","Post Malone","https://i.scdn.co/image/ab67616d0000b273e2e352d89826aef6dbd5ff8f"),
    ("1zi7xx7UVEFkmKfv06H8x0","One Dance","Drake","https://i.scdn.co/image/ab67616d0000b273fcf75ead8a32ac0020d2ce86"),
    ("0yLdNVWF3Srea0uzk55zFo","Circles","Post Malone","https://i.scdn.co/image/ab67616d0000b27339c8e6eb0dc76fa4c2a891bd"),
    ("6AI3ezQ4o3HUoP6Dhudph3","Peaches","Justin Bieber","https://i.scdn.co/image/ab67616d0000b2738913bc0a0b64cb1c16bfcdd9"),
    ("5uEYRdEIh9Bo4fpjDd4Na9","Goosebumps","Travis Scott","https://i.scdn.co/image/ab67616d0000b273f54b99bf27cda88f4a7f7f07"),
]

def seed():
    c = sqlite3.connect(DB_PATH)
    cur = c.cursor()

    real = cur.execute("""
        SELECT DISTINCT t.track_id, t.track_name, t.artist_name, t.image_url
        FROM top_tracks t JOIN users u ON t.spotify_id = u.spotify_id
        WHERE u.spotify_id NOT LIKE 'fake%' AND t.time_range='short_term'
    """).fetchall()
    print(f"Found {len(real)} real tracks from your account")

    seen = set()
    pool = []
    for t in list(real) + BACKUP:
        if t[0] not in seen:
            seen.add(t[0]); pool.append(t)

    cur.execute("DELETE FROM top_tracks WHERE spotify_id LIKE 'fake100_%'")
    cur.execute("DELETE FROM users WHERE spotify_id LIKE 'fake100_%'")

    for i in range(100):
        uid = f"fake100_{i}"
        school = SCHOOLS[i % 10]
        cur.execute("INSERT INTO users (spotify_id, display_name, email, school, access_token, refresh_token) VALUES (?, ?, ?, ?, 'fake', 'fake')",
                    (uid, f"Student {i+1}", f"{uid}@example.com", school))

        # Half real, half backup — guarantees overlap
        real_picks = random.sample(real, min(len(real), 15)) if real else []
        backup_needed = 30 - len(real_picks)
        backup_picks = random.sample(BACKUP, min(backup_needed, len(BACKUP)))
        picks = list(real_picks) + list(backup_picks)
        random.shuffle(picks)

        for rank, (tid, tn, an, img) in enumerate(picks, 1):
            cur.execute("INSERT INTO top_tracks (spotify_id, track_id, track_name, artist_name, image_url, time_range, rank) VALUES (?, ?, ?, ?, ?, 'short_term', ?)",
                        (uid, tid, tn, an, img, rank))

    c.commit(); c.close()
    print(f"Done. 100 users, each with {len(real_picks) if real else 0} of your real tracks.")

if __name__ == "__main__":
    seed()