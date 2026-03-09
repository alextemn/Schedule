import { useEffect, useState, useCallback } from 'react'
import './App.css'

const BACKEND = 'http://localhost:8000'

function App() {
  const [user, setUser] = useState(null)
  const [accessToken, setAccessToken] = useState(null)
  const [events, setEvents] = useState([])
  const [form, setForm] = useState({ summary: '', description: '', start_datetime: '', end_datetime: '' })
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [deletingId, setDeletingId] = useState(null)

  const fetchEvents = useCallback(async (token) => {
    const res = await fetch(`${BACKEND}/api/calendar/events/?access_token=${token}`)
    const data = await res.json()
    if (res.ok) {
      setEvents(data.events)
      console.log('Upcoming events:', data.events)
    } else {
      console.error('Failed to fetch events:', data)
    }
  }, [])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const userParam = params.get('user')
    const errorParam = params.get('auth_error')

    if (userParam) {
      const userInfo = JSON.parse(decodeURIComponent(userParam))
      const { access_token, ...rest } = userInfo
      setUser(rest)
      setAccessToken(access_token)
      console.log('Google user info:', rest)
      window.history.replaceState({}, document.title, '/')
      fetchEvents(access_token)
    } else if (errorParam) {
      console.error('OAuth error:', errorParam)
      window.history.replaceState({}, document.title, '/')
    }
  }, [fetchEvents])

  const handleGoogleLogin = () => {
    window.location.href = `${BACKEND}/api/auth/google/`
  }

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleCreateEvent = async (e) => {
    e.preventDefault()
    setLoading(true)
    setStatus(null)

    try {
      const res = await fetch(`${BACKEND}/api/calendar/events/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          access_token: accessToken,
          summary: form.summary,
          description: form.description,
          start_datetime: form.start_datetime,
          end_datetime: form.end_datetime,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        }),
      })
      const data = await res.json()

      if (res.ok) {
        console.log('Created event:', data.event)
        setStatus({ type: 'success', message: `Event "${data.event.summary}" created!` })
        setForm({ summary: '', description: '', start_datetime: '', end_datetime: '' })
        fetchEvents(accessToken)
      } else {
        console.error('Failed to create event:', data)
        setStatus({ type: 'error', message: `Error: ${JSON.stringify(data.error)}` })
      }
    } catch (err) {
      setStatus({ type: 'error', message: `Network error: ${err.message}` })
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteEvent = async (eventId, eventSummary) => {
    setDeletingId(eventId)
    try {
      const res = await fetch(`${BACKEND}/api/calendar/events/${eventId}/`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_token: accessToken }),
      })

      if (res.ok) {
        console.log(`Deleted event: ${eventId} — "${eventSummary}"`)
        setEvents((prev) => prev.filter((e) => e.id !== eventId))
      } else {
        const data = await res.json()
        console.error('Failed to delete event:', data)
        setStatus({ type: 'error', message: `Delete failed: ${JSON.stringify(data.error)}` })
      }
    } catch (err) {
      setStatus({ type: 'error', message: `Network error: ${err.message}` })
    } finally {
      setDeletingId(null)
    }
  }

  const formatDateTime = (dateTime) => {
    if (!dateTime) return ''
    return new Date(dateTime).toLocaleString()
  }

  return (
    <div style={{ maxWidth: '600px', margin: '60px auto', fontFamily: 'sans-serif', padding: '0 16px' }}>
      <h1>Study Schedule</h1>

      {!user ? (
        <button onClick={handleGoogleLogin} style={btnStyle}>
          Sign in with Google
        </button>
      ) : (
        <>
          <p>Signed in as <strong>{user.name}</strong> ({user.email})</p>

          {/* Create event form */}
          <form onSubmit={handleCreateEvent} style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '32px' }}>
            <h2 style={{ margin: '0 0 4px' }}>Create Event</h2>
            <input name="summary" placeholder="Title *" value={form.summary} onChange={handleChange} required style={inputStyle} />
            <input name="description" placeholder="Description (optional)" value={form.description} onChange={handleChange} style={inputStyle} />
            <label style={labelStyle}>
              Start
              <input type="datetime-local" name="start_datetime" value={form.start_datetime} onChange={handleChange} required style={{ ...inputStyle, marginTop: '4px' }} />
            </label>
            <label style={labelStyle}>
              End
              <input type="datetime-local" name="end_datetime" value={form.end_datetime} onChange={handleChange} required style={{ ...inputStyle, marginTop: '4px' }} />
            </label>
            <button type="submit" disabled={loading} style={btnStyle}>
              {loading ? 'Creating…' : 'Create Event'}
            </button>
          </form>

          {status && (
            <p style={{ color: status.type === 'success' ? 'green' : 'red', marginBottom: '24px' }}>
              {status.message}
            </p>
          )}

          {/* Events list */}
          <h2 style={{ marginBottom: '12px' }}>Upcoming Events</h2>
          {events.length === 0 ? (
            <p style={{ color: '#888' }}>No upcoming events.</p>
          ) : (
            <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {events.map((event) => (
                <li key={event.id} style={{ border: '1px solid #ddd', borderRadius: '6px', padding: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
                  <div>
                    <strong>{event.summary}</strong>
                    <div style={{ fontSize: '13px', color: '#555', marginTop: '4px' }}>
                      {formatDateTime(event.start?.dateTime || event.start?.date)}
                      {' → '}
                      {formatDateTime(event.end?.dateTime || event.end?.date)}
                    </div>
                    {event.description && (
                      <div style={{ fontSize: '12px', color: '#888', marginTop: '4px' }}>{event.description}</div>
                    )}
                  </div>
                  <button
                    onClick={() => handleDeleteEvent(event.id, event.summary)}
                    disabled={deletingId === event.id}
                    style={{ ...btnStyle, background: '#e53e3e', color: '#fff', whiteSpace: 'nowrap', flexShrink: 0 }}
                  >
                    {deletingId === event.id ? 'Deleting…' : 'Delete'}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}

const inputStyle = {
  padding: '8px',
  fontSize: '14px',
  width: '100%',
  boxSizing: 'border-box',
  display: 'block',
}

const labelStyle = {
  fontSize: '13px',
  color: '#555',
  display: 'block',
}

const btnStyle = {
  padding: '10px 16px',
  fontSize: '14px',
  cursor: 'pointer',
  border: 'none',
  borderRadius: '4px',
  background: '#4285f4',
  color: '#fff',
}

export default App
