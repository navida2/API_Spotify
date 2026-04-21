import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import './App.css'

// In dev, VITE_API_URL is undefined and we use the Vite proxy at /api.
// In prod, set VITE_API_URL=https://your-backend.up.railway.app
const API_BASE = import.meta.env.VITE_API_URL || ''
const API = API_BASE ? API_BASE : '/api'
const LOGIN_URL = `${API_BASE || 'http://127.0.0.1:8080'}/login`
axios.defaults.withCredentials = true

const TIME_RANGES = [
  ['short_term', '4 weeks'],
  ['medium_term', '6 months'],
  ['long_term', 'all time'],
]

const MEDALS = ['01', '02', '03']

export default function App() {
  const [user, setUser] = useState(null)
  const [authChecked, setAuthChecked] = useState(false)
  const [schools, setSchools] = useState([])
  const [timeRange, setTimeRange] = useState('short_term')

  const [topTracks, setTopTracks] = useState([])
  const [viewingSchool, setViewingSchool] = useState(null)
  const [schoolTracks, setSchoolTracks] = useState([])
  const [schoolStats, setSchoolStats] = useState(null)
  const [myTrackVote, setMyTrackVote] = useState(null)

  const [rankings, setRankings] = useState([])
  const [mySchoolVote, setMySchoolVote] = useState(null)

  // Battle state
  const [battle, setBattle] = useState(null)   // { a: {...}, b: {...} } with _school hidden until reveal
  const [battleResult, setBattleResult] = useState(null)  // { winner, loser, chose: 'a' | 'b' } after vote
  const [battleLoading, setBattleLoading] = useState(false)
  const [battleCount, setBattleCount] = useState(0)

  const [compatibility, setCompatibility] = useState([])
  const [alsoLike, setAlsoLike] = useState([])
  const [alsoLikeLoading, setAlsoLikeLoading] = useState(false)
  const [alsoLikeRequested, setAlsoLikeRequested] = useState(false)

  const [playlistLoading, setPlaylistLoading] = useState(false)
  const [playlistUrl, setPlaylistUrl] = useState(null)

  // ---- initial load ----
  useEffect(() => {
    (async () => {
      try {
        const res = await axios.get(`${API}/me`)
        setUser(res.data)
      } catch {
        setUser(null)
      } finally {
        setAuthChecked(true)
      }
      try {
        const res = await axios.get(`${API}/schools`)
        setSchools(res.data)
      } catch {}
      try {
        const res = await axios.get(`${API}/battle/leaderboard`)
        setRankings(res.data.rankings || [])
      } catch {}
    })()
  }, [])

  // ---- when user or timeRange changes ----
  useEffect(() => {
    if (!user) return
    loadTopTracks()
    loadCompatibility()
    if (user.school) {
      setViewingSchool(prev => prev || user.school)
      loadMyTrackVote(user.school)
    }
    loadMySchoolVote()
  }, [user, timeRange]) // eslint-disable-line

  useEffect(() => {
    if (viewingSchool) loadSchoolTracks(viewingSchool)
  }, [viewingSchool]) // eslint-disable-line

  async function loadTopTracks() {
    try {
      const res = await axios.get(`${API}/top-tracks?time_range=${timeRange}&limit=10`)
      setTopTracks(res.data.tracks || [])
    } catch {}
  }

  async function loadSchoolTracks(s) {
    try {
      const res = await axios.get(
        `${API}/school-top-tracks?school=${encodeURIComponent(s)}&time_range=short_term`
      )
      setSchoolTracks(res.data.top_tracks || [])
      setSchoolStats(res.data.stats || null)
    } catch {}
  }

  async function loadCompatibility() {
    try {
      const res = await axios.get(`${API}/compatibility?time_range=${timeRange}`)
      setCompatibility(res.data.compatibility || [])
    } catch {}
  }

  async function loadMyTrackVote(s) {
    try {
      const res = await axios.get(`${API}/my-track-vote?school=${encodeURIComponent(s)}`)
      setMyTrackVote(res.data.vote)
    } catch {}
  }

  async function loadMySchoolVote() {
    try {
      const res = await axios.get(`${API}/my-school-vote`)
      setMySchoolVote(res.data.vote)
    } catch {}
  }

  async function handleSetSchool(s) {
    await axios.post(`${API}/set-school?school=${encodeURIComponent(s)}`)
    setUser(u => ({ ...u, school: s }))
    setViewingSchool(s)
  }

  async function handleVoteTrack(trackId) {
    if (!user?.school) return
    await axios.post(
      `${API}/vote-track?track_id=${trackId}&school=${encodeURIComponent(user.school)}`
    )
    setMyTrackVote(trackId)
    loadSchoolTracks(viewingSchool)
  }

  async function loadBattle() {
    setBattleLoading(true)
    setBattleResult(null)
    try {
      const res = await axios.get(`${API}/battle/next`)
      setBattle(res.data)
    } catch {
      setBattle(null)
    } finally {
      setBattleLoading(false)
    }
  }

  async function voteBattle(choice) {
    if (!battle) return
    const winnerSide = battle[choice]
    const loserSide = choice === 'a' ? battle.b : battle.a
    try {
      await axios.post(
        `${API}/battle/vote?winner=${encodeURIComponent(winnerSide._school)}&loser=${encodeURIComponent(loserSide._school)}`
      )
      setBattleResult({
        chose: choice,
        winner: winnerSide._school,
        loser: loserSide._school,
      })
      setBattleCount(c => c + 1)
      // Refresh the leaderboard in the background
      const res = await axios.get(`${API}/battle/leaderboard`)
      setRankings(res.data.rankings || [])
    } catch {}
  }

  function nextBattle() {
    loadBattle()
  }

  async function handleLoadAlsoLike() {
    setAlsoLikeLoading(true)
    setAlsoLikeRequested(true)
    try {
      const res = await axios.get(`${API}/listeners-also-like?time_range=${timeRange}`)
      setAlsoLike(res.data.tracks || [])
    } finally {
      setAlsoLikeLoading(false)
    }
  }

  async function handleCreatePlaylist() {
    if (!user?.school) return
    setPlaylistLoading(true)
    try {
      const res = await axios.post(
        `${API}/create-campus-playlist?school=${encodeURIComponent(user.school)}&time_range=${timeRange}`
      )
      setPlaylistUrl(res.data.playlist_url)
    } finally {
      setPlaylistLoading(false)
    }
  }

  async function handleLogout() {
    await axios.post(`${API}/logout`)
    setUser(null)
    window.location.reload()
  }

  if (!authChecked) {
    return <div className="boot" />
  }

  if (!user) return <LoginPage />

  const myCompat = compatibility.find(c => c.school === user.school)
  const topSchool = rankings[0]

  return (
    <div className="app">
      <nav className="nav">
        <div className="mark">
          <span className="mark-dot" />
          <span className="mark-text">ucampus<em>.fm</em></span>
        </div>
        <div className="nav-right">
          {user.image_url && <img src={user.image_url} alt="" className="pfp" />}
          <span className="nav-name">{user.display_name}</span>
          <button className="link-btn" onClick={handleLogout}>log out</button>
        </div>
      </nav>

      <header className="hero">
        <div className="hero-meta">
          <span className="eyebrow">Issue №{new Date().toISOString().slice(0, 10)}</span>
          <div className="time-toggle">
            {TIME_RANGES.map(([val, label]) => (
              <button
                key={val}
                className={timeRange === val ? 'active' : ''}
                onClick={() => setTimeRange(val)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <h1 className="hero-title">
          <span className="hero-word">what</span>{' '}
          <span className="hero-word">your</span>
          <br />
          <span className="hero-word italic">campus</span>{' '}
          <span className="hero-word">is</span>{' '}
          <span className="hero-word italic">listening to.</span>
        </h1>

        <div className="hero-grid">
          <div className="hero-box">
            <span className="label">Your school</span>
            {user.school ? (
              <span className="hero-value">{user.school}</span>
            ) : (
              <select
                className="school-picker"
                defaultValue=""
                onChange={(e) => e.target.value && handleSetSchool(e.target.value)}
              >
                <option value="" disabled>choose yours →</option>
                {schools.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            )}
          </div>
          <div className="hero-box">
            <span className="label">Taste match w/ {user.school || 'your school'}</span>
            <span className="hero-value big">
              {myCompat ? `${myCompat.compatibility}%` : '-'}
            </span>
          </div>
          <div className="hero-box">
            <span className="label">Top taste on campus</span>
            <span className="hero-value">
              {topSchool && topSchool.battles > 0 ? topSchool.school : '-'}
              {topSchool && topSchool.battles > 0 && (
                <em className="vote-count"> · {topSchool.win_rate}% win rate</em>
              )}
            </span>
          </div>
        </div>
      </header>

      {/* CAMPUS - the star of the show */}
      <section className="section campus">
        <div className="section-head">
          <span className="section-num">01</span>
          <h2>Campus top tracks</h2>
          <span className="section-tag">last 4 weeks</span>
          <div className="school-select">
            <select
              value={viewingSchool || ''}
              onChange={(e) => setViewingSchool(e.target.value)}
            >
              {schools.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>

        {schoolStats && schoolStats.listeners > 0 && (
          <div className="stat-bar">
            <div><em>{schoolStats.listeners}</em> listeners</div>
            <div><em>{schoolStats.unique_tracks}</em> tracks tracked</div>
            {schoolStats.top_artist && (
              <div>top artist · <em>{schoolStats.top_artist.artist_name}</em></div>
            )}
          </div>
        )}

        {schoolTracks.length > 0 ? (
          <ol className="big-list">
            {schoolTracks.map((t, i) => (
              <li key={t.track_id} className="big-row">
                <span className="big-rank">{String(i + 1).padStart(2, '0')}</span>
                {t.image_url && <img src={t.image_url} alt="" className="big-art" />}
                <div className="big-info">
                  <strong>{t.track_name}</strong>
                  <span>{t.artist_name}</span>
                </div>
                <span className="big-meta">
                  {t.listener_count} listener{t.listener_count !== 1 ? 's' : ''}
                </span>
                {viewingSchool === user.school && (
                  <button
                    className={`vote-pill ${myTrackVote === t.track_id ? 'voted' : ''}`}
                    onClick={() => handleVoteTrack(t.track_id)}
                    title={user.school ? 'Vote for anthem of the month' : 'Set your school first'}
                  >
                    {myTrackVote === t.track_id ? '★' : '☆'} {t.vote_count || 0}
                  </button>
                )}
              </li>
            ))}
          </ol>
        ) : (
          <p className="empty">
            Silence. No listeners at {viewingSchool} yet - be the one who starts it.
          </p>
        )}
      </section>

      {/* BATTLE - blind taste test */}
      <section className="section">
        <div className="section-head">
          <span className="section-num">02</span>
          <h2>Battle of the campuses</h2>
        </div>
        <p className="sub">
          Two campuses. Five songs each. Pick the side you'd rather listen to.
          Names are hidden - no bias, just taste.
        </p>

        {!battle && !battleLoading && (
          <button className="cta" onClick={loadBattle}>
            Start a battle →
          </button>
        )}

        {battleLoading && (
          <div className="loading-lines">
            <span /><span />
          </div>
        )}

        {battle && !battleResult && (
          <div className="battle">
            {['a', 'b'].map(side => (
              <button
                key={side}
                className={`battle-side side-${side}`}
                onClick={() => voteBattle(side)}
              >
                <div className="battle-head">
                  <span className="battle-label">Campus {side.toUpperCase()}</span>
                  <span className="battle-hint">click to vote</span>
                </div>
                <ol className="battle-list">
                  {battle[side].tracks.map((t, i) => (
                    <li key={t.track_id}>
                      <span className="battle-rank">{String(i + 1).padStart(2, '0')}</span>
                      {t.image_url && <img src={t.image_url} alt="" />}
                      <div>
                        <strong>{t.track_name}</strong>
                        <span>{t.artist_name}</span>
                      </div>
                    </li>
                  ))}
                </ol>
              </button>
            ))}
          </div>
        )}

        {battleResult && battle && (
          <div className="battle reveal">
            {['a', 'b'].map(side => {
              const isPicked = battleResult.chose === side
              const schoolName = battle[side]._school
              return (
                <div
                  key={side}
                  className={`battle-side reveal ${isPicked ? 'picked' : 'not-picked'}`}
                >
                  <div className="battle-head">
                    <span className="battle-label revealed">{schoolName}</span>
                    {isPicked && <span className="battle-hint picked-tag">your pick</span>}
                  </div>
                  <ol className="battle-list">
                    {battle[side].tracks.map((t, i) => (
                      <li key={t.track_id}>
                        <span className="battle-rank">{String(i + 1).padStart(2, '0')}</span>
                        {t.image_url && <img src={t.image_url} alt="" />}
                        <div>
                          <strong>{t.track_name}</strong>
                          <span>{t.artist_name}</span>
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
              )
            })}
          </div>
        )}

        {battleResult && (
          <div className="battle-next-row">
            <span className="battle-counter">
              {battleCount} {battleCount === 1 ? 'battle' : 'battles'} voted
            </span>
            <button className="cta" onClick={nextBattle}>
              Next battle →
            </button>
          </div>
        )}
      </section>

      {/* LEADERBOARD - by battle win rate */}
      <section className="section">
        <div className="section-head">
          <span className="section-num">03</span>
          <h2>Taste rankings</h2>
          <span className="section-tag">by battle win rate</span>
        </div>
        <p className="sub">
          Every campus's score is calculated from all the battle votes across the app.
        </p>

        <div className="board">
          {rankings.map((r, i) => {
            const isMine = r.school === user.school
            const maxRate = Math.max(...rankings.map(x => x.win_rate), 1)
            const pct = (r.win_rate / maxRate) * 100
            return (
              <div
                key={r.school}
                className={`row ${isMine ? 'is-mine' : ''} ${r.battles === 0 ? 'no-battles' : ''}`}
              >
                <span className="row-rank">{MEDALS[i] || String(i + 1).padStart(2, '0')}</span>
                <span className="row-school">
                  {r.school}
                  {isMine && <em className="tag">you</em>}
                </span>
                <span className="row-bar">
                  <span className="row-bar-fill" style={{ width: `${pct}%` }} />
                </span>
                <span className="row-votes">
                  {r.battles > 0 ? `${r.win_rate}%` : '-'}
                  <em className="row-sub">
                    {r.wins}W {r.losses}L
                  </em>
                </span>
              </div>
            )
          })}
        </div>
      </section>

      {/* COMPATIBILITY */}
      <section className="section">
        <div className="section-head">
          <span className="section-num">04</span>
          <h2>Where else you'd fit in</h2>
        </div>
        <p className="sub">How much your taste overlaps with each campus.</p>
        <div className="compat-grid">
          {compatibility.slice(0, 6).map(c => (
            <div key={c.school} className={`compat-card ${c.school === user.school ? 'mine' : ''}`}>
              <div className="compat-school">{c.school}</div>
              <div className="compat-score">{c.compatibility}<em>%</em></div>
              <div className="compat-bar">
                <div className="compat-bar-fill" style={{ width: `${c.compatibility}%` }} />
              </div>
              <div className="compat-foot">{c.overlap} shared track{c.overlap !== 1 ? 's' : ''}</div>
            </div>
          ))}
        </div>
      </section>

      {/* PERSONAL TOP TRACKS */}
      <section className="section">
        <div className="section-head">
          <span className="section-num">05</span>
          <h2>On your rotation</h2>
        </div>
        <div className="grid-tracks">
          {topTracks.map((t, i) => (
            <div key={t.track_id} className="track-card">
              <span className="track-rank">{String(i + 1).padStart(2, '0')}</span>
              {t.image_url && <img src={t.image_url} alt="" />}
              <div>
                <strong>{t.track_name}</strong>
                <span>{t.artist_name}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* DISCOVERY */}
      <section className="section">
        <div className="section-head">
          <span className="section-num">06</span>
          <h2>Listeners like you also play</h2>
        </div>
        {!alsoLikeRequested ? (
          <button className="cta" onClick={handleLoadAlsoLike}>
            Find my taste twins →
          </button>
        ) : alsoLikeLoading ? (
          <div className="loading-lines">
            <span /><span /><span />
          </div>
        ) : alsoLike.length > 0 ? (
          <div className="grid-tracks">
            {alsoLike.map(t => (
              <div key={t.track_id} className="track-card">
                {t.image_url && <img src={t.image_url} alt="" />}
                <div>
                  <strong>{t.track_name}</strong>
                  <span>{t.artist_name} · {t.listener_count} match{t.listener_count !== 1 ? 'es' : ''}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="empty">No taste twins yet. Tell a friend - this works better in pairs.</p>
        )}
      </section>

      {/* PLAYLIST CTA */}
      {user.school && (
        <section className="section section-cta">
          <div className="cta-wrap">
            <div>
              <h2 className="cta-title">
                Take <em>{user.school}</em> with you.
              </h2>
              <p className="cta-sub">Bundle the top 20 into a real Spotify playlist in one click.</p>
            </div>
            {playlistUrl ? (
              <a className="cta" href={playlistUrl} target="_blank" rel="noreferrer">
                Open in Spotify →
              </a>
            ) : (
              <button className="cta" onClick={handleCreatePlaylist} disabled={playlistLoading}>
                {playlistLoading ? 'Building…' : 'Create playlist →'}
              </button>
            )}
          </div>
        </section>
      )}

      <footer className="foot">
        <span>ucampus.fm</span>
        <span>a student project · not affiliated with spotify</span>
      </footer>
    </div>
  )
}

function LoginPage() {
  return (
    <div className="login">
      <div className="login-nav">
        <span className="mark-dot" />
        <span className="mark-text">ucampus<em>.fm</em></span>
      </div>

      <div className="login-main">
        <span className="eyebrow">for uc students · built on spotify</span>
        <h1 className="login-title">
          what does your <em>campus</em><br />actually <em>listen to?</em>
        </h1>
        <p className="login-sub">
          Link your Spotify. See the songs your school has on repeat,
          vote for the anthem of the month, and find out which UC has better taste.
        </p>
        <a href={LOGIN_URL} className="login-btn">
          Continue with Spotify →
        </a>
        <div className="login-stats">
          <div><em>10</em> UC campuses</div>
          <div><em>200+</em> students</div>
          <div><em>3.7k</em> tracks tracked</div>
        </div>
      </div>

      <div className="login-marquee">
        <div className="marquee-track">
          {['Blinding Lights', 'HUMBLE.', 'As It Was', 'Heat Waves', 'Good Days', 'bad guy', 'Levitating', 'Sicko Mode', 'Sunflower', 'Peaches'].map((s, i) => (
            <span key={i}>{s} <span className="dot">●</span></span>
          ))}
          {['Blinding Lights', 'HUMBLE.', 'As It Was', 'Heat Waves', 'Good Days', 'bad guy', 'Levitating', 'Sicko Mode', 'Sunflower', 'Peaches'].map((s, i) => (
            <span key={`b-${i}`}>{s} <span className="dot">●</span></span>
          ))}
        </div>
      </div>
    </div>
  )
}