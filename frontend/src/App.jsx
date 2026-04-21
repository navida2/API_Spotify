import { useState, useEffect } from 'react'
import './App.css'
import axios from 'axios'

function App() {
  const [user, setUser] = useState(null)
  const [topTracks, setTopTracks] = useState([])
  const [topArtists, setTopArtists] = useState([])
  const [school, setSchool] = useState(null)
  const [schools, setSchools] = useState([])
  const [schoolTracks, setSchoolTracks] = useState([])
  const [viewingSchool, setViewingSchool] = useState(null)
  const [timeRange, setTimeRange] = useState('short_term')
  const [alsoLike, setAlsoLike] = useState([])
  const [alsoLikeLoaded, setAlsoLikeLoaded] = useState(false)
  const [playlistLoading, setPlaylistLoading] = useState(false)
  const [playlistUrl, setPlaylistUrl] = useState(null)
  const [loading, setLoading] = useState(false)
  const [myTrackVote, setMyTrackVote] = useState(null)
  const [schoolRankings, setSchoolRankings] = useState([])
  const [mySchoolVote, setMySchoolVote] = useState(null)

  useEffect(() => {
    loadUser()
    loadSchools()
    loadSchoolRankings()
    loadMySchoolVote()
  }, [])

  useEffect(() => {
    if (user) {
      loadTopTracks()
      loadTopArtists()
      if (user.school) {
        setSchool(user.school)
        setViewingSchool(user.school)
        loadSchoolTracks(user.school)
        loadMyTrackVote(user.school)
      }
    }
  }, [user, timeRange])

  async function loadUser() {
    try {
      const res = await axios.get('/api/me')
      setUser(res.data)
    } catch {
      setUser(null)
    }
  }

  async function loadSchools() {
    try {
      const res = await axios.get('/api/schools')
      setSchools(res.data)
    } catch {}
  }

  async function loadTopTracks() {
    const res = await axios.get(`/api/top-tracks?time_range=${timeRange}&limit=10`)
    setTopTracks(res.data.items || [])
  }

  async function loadTopArtists() {
    const res = await axios.get(`/api/top-artists?time_range=${timeRange}&limit=10`)
    setTopArtists(res.data.items || [])
  }

  async function handleSetSchool(s) {
    await axios.post(`/api/set-school?school=${encodeURIComponent(s)}`)
    setSchool(s)
    setViewingSchool(s)
    loadSchoolTracks(s)
    loadMyTrackVote(s)
  }

  async function loadSchoolTracks(s) {
    const res = await axios.get(`/api/school-top-tracks?school=${encodeURIComponent(s)}&time_range=short_term`)
    setSchoolTracks(res.data.top_tracks || [])
  }

  async function loadMyTrackVote(s) {
    const res = await axios.get(`/api/my-track-vote?school=${encodeURIComponent(s)}`)
    setMyTrackVote(res.data.vote)
  }

  async function handleVoteTrack(trackId) {
    await axios.post(`/api/vote-track?track_id=${trackId}&school=${encodeURIComponent(school)}`)
    setMyTrackVote(trackId)
    loadSchoolTracks(viewingSchool)
  }

  async function loadSchoolRankings() {
    try {
      const res = await axios.get('/api/school-rankings')
      setSchoolRankings(res.data.rankings || [])
    } catch {}
  }

  async function loadMySchoolVote() {
    try {
      const res = await axios.get('/api/my-school-vote')
      setMySchoolVote(res.data.vote)
    } catch {}
  }

  async function handleVoteSchool(s) {
    await axios.post(`/api/vote-school?voted_for=${encodeURIComponent(s)}`)
    setMySchoolVote(s)
    loadSchoolRankings()
  }

  async function loadAlsoLike() {
    setLoading(true)
    const res = await axios.get(`/api/listeners-also-like?time_range=${timeRange}`)
    setAlsoLike(res.data.tracks || [])
    setAlsoLikeLoaded(true)
    setLoading(false)
  }

  async function createPlaylist() {
    setPlaylistLoading(true)
    const res = await axios.get(`/api/create-campus-playlist?school=${encodeURIComponent(school)}&time_range=short_term`)
    setPlaylistUrl(res.data.playlist_url || null)
    setPlaylistLoading(false)
  }

  if (!user) {
    return (
      <div className="login-page">
        <h1>Spotify Profile</h1>
        <p>See your stats, discover new music, and compare with your campus.</p>
        <a href="http://127.0.0.1:8080/login" className="login-btn">
          Log in with Spotify
        </a>
      </div>
    )
  }

  return (
    <div className="app">
      <header>
        <div className="user-info">
          {user.images?.[0] && <img src={user.images[0].url} alt="pfp" className="pfp" />}
          <div>
            <h1>{user.display_name}</h1>
            <p>{user.followers?.total} followers</p>
          </div>
        </div>
        {!school ? (
          <select onChange={(e) => handleSetSchool(e.target.value)} defaultValue="">
            <option value="" disabled>Pick your school</option>
            {schools.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        ) : (
          <span className="school-badge">{school}</span>
        )}
      </header>

      <div className="time-toggle">
        {[['short_term', '4 Weeks'], ['medium_term', '6 Months'], ['long_term', 'All Time']].map(([val, label]) => (
          <button key={val} className={timeRange === val ? 'active' : ''} onClick={() => setTimeRange(val)}>
            {label}
          </button>
        ))}
      </div>

      <div className="grid">
        <div className="card">
          <h2>Top Tracks</h2>
          <ol>
            {topTracks.map(t => (
              <li key={t.id}>
                <img src={t.album.images[2]?.url} alt="" />
                <div>
                  <strong>{t.name}</strong>
                  <span>{t.artists[0].name}</span>
                </div>
              </li>
            ))}
          </ol>
        </div>

        <div className="card">
          <h2>Top Artists</h2>
          <ol>
            {topArtists.map(a => (
              <li key={a.id}>
                <img src={a.images[2]?.url} alt="" style={{borderRadius: '50%'}} />
                <div>
                  <strong>{a.name}</strong>
                  <span>{a.genres?.slice(0, 2).join(', ')}</span>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <section className="school-section">
        <div className="section-header">
          <h2>Campus Top Tracks</h2>
          <select
            value={viewingSchool || ''}
            onChange={(e) => {
              setViewingSchool(e.target.value)
              loadSchoolTracks(e.target.value)
            }}
          >
            {schools.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="school-card">
          {viewingSchool && schoolTracks.length > 0 ? (
            <>
              {viewingSchool === school && (
                <p className="subtitle">Vote for the best track at your school</p>
              )}
              {viewingSchool !== school && (
                <p className="subtitle">Viewing {viewingSchool}'s top tracks</p>
              )}
              <ol>
                {schoolTracks.map((t, i) => (
                  <li key={i} className="votable-track">
                    {t.image_url && <img src={t.image_url} alt="" />}
                    <div style={{flex: 1}}>
                      <strong>{t.track_name}</strong>
                      <span>{t.artist_name} • {t.listener_count} listener{t.listener_count > 1 ? 's' : ''}</span>
                    </div>
                    {viewingSchool === school && (
                      <button
                        className={`vote-btn ${myTrackVote === t.track_id ? 'voted' : ''}`}
                        onClick={() => handleVoteTrack(t.track_id)}
                      >
                        {myTrackVote === t.track_id ? '✓' : '▲'} {t.vote_count || 0}
                      </button>
                    )}
                  </li>
                ))}
              </ol>
            </>
          ) : viewingSchool ? (
            <p className="empty-state">No listeners from {viewingSchool} yet. Share the app!</p>
          ) : null}
        </div>
      </section>

      <section className="school-section">
        <h2>Best Music Taste</h2>
        <p className="subtitle">Vote for the school with the best music taste (not your own)</p>
        <div className="school-vote-grid">
          {schools.filter(s => s !== school).map(s => {
            const ranking = schoolRankings.find(r => r.school === s)
            const votes = ranking ? ranking.votes : 0
            return (
              <button
                key={s}
                className={`school-vote-btn ${mySchoolVote === s ? 'voted' : ''}`}
                onClick={() => handleVoteSchool(s)}
              >
                <strong>{s}</strong>
                <span>{votes} vote{votes !== 1 ? 's' : ''}</span>
              </button>
            )
          })}
        </div>
      </section>

      <section className="discover-section">
        <h2>Listeners Also Like</h2>
        <button className="action-btn" onClick={loadAlsoLike} disabled={loading}>
          {loading ? 'Finding...' : 'Find Similar Tracks'}
        </button>
        {alsoLike.length > 0 ? (
          <div className="school-card">
            <ol>
              {alsoLike.map((t, i) => (
                <li key={i}>
                  {t.image_url && <img src={t.image_url} alt="" />}
                  <div>
                    <strong>{t.track_name}</strong>
                    <span>{t.artist_name} • {t.listener_count} similar listener{t.listener_count > 1 ? 's' : ''}</span>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        ) : alsoLikeLoaded ? (
          <p className="empty-state">Not enough users yet to find matches. Invite friends!</p>
        ) : null}
      </section>

      {school && (
        <section className="discover-section">
          <h2>{school} Playlist</h2>
          <button className="action-btn" onClick={createPlaylist} disabled={playlistLoading}>
            {playlistLoading ? 'Creating...' : 'Create Campus Playlist on Spotify'}
          </button>
          {playlistUrl && (
            <p style={{marginTop: '12px'}}>
              <a href={playlistUrl} target="_blank" rel="noreferrer" className="playlist-link">
                Open playlist in Spotify →
              </a>
            </p>
          )}
        </section>
      )}
    </div>
  )
}

export default App