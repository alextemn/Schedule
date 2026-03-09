import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../api'
import { clearTokens, getAccessToken } from '../auth'

const BACKEND = 'http://localhost:8000'

const inputStyle = { padding: '8px', fontSize: '14px', width: '100%', boxSizing: 'border-box', display: 'block', borderRadius: '4px', border: '1px solid #ccc' }
const labelStyle = { fontSize: '13px', color: '#555', display: 'block' }
const btnStyle = { padding: '10px 16px', fontSize: '14px', cursor: 'pointer', border: 'none', borderRadius: '4px', background: '#4285f4', color: '#fff' }

export default function DashboardPage() {
  const [user, setUser] = useState(null)
  const [form, setForm] = useState({ summary: '', description: '', start_datetime: '', end_datetime: '' })
  const [eventStatus, setEventStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [assignments, setAssignments] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [analyzingId, setAnalyzingId] = useState(null)
  const [studyHours, setStudyHours] = useState({ study_start: '', study_end: '' })
  const [studyHoursStatus, setStudyHoursStatus] = useState(null)
  const [savingHours, setSavingHours] = useState(false)
  const fileInputRef = useRef(null)
  const navigate = useNavigate()

  const handleLogout = useCallback(() => {
    clearTokens()
    navigate('/login')
  }, [navigate])

  const fetchAssignments = useCallback(async () => {
    const res = await apiFetch('/api/assignments/')
    if (res.ok) setAssignments(await res.json())
  }, [])

  // Load current user on mount
  useEffect(() => {
    apiFetch('/api/auth/me/')
      .then(r => r.json())
      .then(data => {
        if (data.id) {
          setUser(data)
          setStudyHours({
            study_start: data.study_start || '',
            study_end: data.study_end || '',
          })
        } else handleLogout()
      })
      .catch(() => handleLogout())
  }, [handleLogout])

  // Load assignments on mount
  useEffect(() => {
    fetchAssignments()
  }, [fetchAssignments])

  // Handle ?google_linked=true redirect from Google OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('google_linked') === 'true') {
      window.history.replaceState({}, document.title, '/')
      apiFetch('/api/auth/me/')
        .then(r => r.json())
        .then(data => { if (data.id) setUser(data) })
    }
    if (params.get('google_error')) {
      setEventStatus({ type: 'error', message: `Google connection failed: ${params.get('google_error')}` })
      window.history.replaceState({}, document.title, '/')
    }
  }, [])

  const handleConnectGoogle = () => {
    const token = getAccessToken()
    window.location.href = `${BACKEND}/api/auth/google/?token=${token}`
  }

  const handleChange = (e) => setForm(prev => ({ ...prev, [e.target.name]: e.target.value }))

  const handleCreateEvent = async (e) => {
    e.preventDefault()
    setLoading(true)
    setEventStatus(null)

    try {
      const res = await apiFetch('/api/calendar/events/', {
        method: 'POST',
        body: JSON.stringify({
          summary: form.summary,
          description: form.description,
          start_datetime: form.start_datetime,
          end_datetime: form.end_datetime,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        }),
      })
      const data = await res.json()

      if (res.ok) {
        setEventStatus({ type: 'success', message: `Event "${data.event.summary}" created!` })
        setForm({ summary: '', description: '', start_datetime: '', end_datetime: '' })
      } else {
        setEventStatus({ type: 'error', message: `Error: ${JSON.stringify(data.error)}` })
      }
    } catch (err) {
      setEventStatus({ type: 'error', message: `Network error: ${err.message}` })
    } finally {
      setLoading(false)
    }
  }

  const handleSaveStudyHours = async (e) => {
    e.preventDefault()
    setSavingHours(true)
    setStudyHoursStatus(null)
    const res = await apiFetch('/api/auth/me/', {
      method: 'PATCH',
      body: JSON.stringify(studyHours),
    })
    const data = await res.json()
    setSavingHours(false)
    if (res.ok) {
      setUser(data)
      setStudyHoursStatus({ type: 'success', message: 'Study hours saved.' })
    } else {
      setStudyHoursStatus({ type: 'error', message: data.error || 'Failed to save' })
    }
  }

  const handleAnalyze = async (id) => {
    setAnalyzingId(id)
    const res = await apiFetch(`/api/assignments/${id}/analyze/`, { method: 'POST' })
    const data = await res.json()
    if (res.ok) {
      setAssignments(prev => prev.map(a => a.id === id ? data : a))
    } else {
      alert(`Analysis failed: ${data.error || 'Unknown error'}`)
    }
    setAnalyzingId(null)
  }

  const handleDeleteAll = async () => {
    if (!window.confirm('Delete all assignments?')) return
    setDeleting(true)
    await apiFetch('/api/assignments/all/', { method: 'DELETE' })
    setAssignments([])
    setDeleting(false)
  }

  const handleICSUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    setUploading(true)
    setUploadStatus(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const token = getAccessToken()
      const res = await fetch(`${BACKEND}/api/assignments/upload-ics/`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })
      const data = await res.json()

      if (res.ok) {
        setUploadStatus({ type: 'success', message: `Imported ${data.length} assignment${data.length !== 1 ? 's' : ''}.` })
        fetchAssignments()
      } else {
        setUploadStatus({ type: 'error', message: data.error || 'Upload failed' })
      }
    } catch (err) {
      setUploadStatus({ type: 'error', message: `Network error: ${err.message}` })
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const formatDate = (iso) => {
    if (!iso) return 'No date'
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
  }

  if (!user) return <p style={{ fontFamily: 'sans-serif', padding: '60px', textAlign: 'center' }}>Loading…</p>

  return (
    <div style={{ maxWidth: '640px', margin: '60px auto', fontFamily: 'sans-serif', padding: '0 16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <h1 style={{ margin: 0 }}>Study Schedule</h1>
        <button onClick={handleLogout} style={{ ...btnStyle, background: '#888' }}>Log Out</button>
      </div>

      <p style={{ color: '#555', marginBottom: '28px' }}>
        Signed in as <strong>{user.name || user.email}</strong>
      </p>

      {/* ── Study Hours ──────────────────────────────── */}
      <section style={{ marginBottom: '40px' }}>
        <h2 style={{ marginBottom: '12px' }}>Study Hours</h2>
        <form onSubmit={handleSaveStudyHours} style={{ display: 'flex', alignItems: 'flex-end', gap: '12px', flexWrap: 'wrap' }}>
          <label style={labelStyle}>
            Start
            <input
              type="time"
              value={studyHours.study_start}
              onChange={e => setStudyHours(p => ({ ...p, study_start: e.target.value }))}
              required
              style={{ ...inputStyle, marginTop: '4px', width: 'auto' }}
            />
          </label>
          <label style={labelStyle}>
            End
            <input
              type="time"
              value={studyHours.study_end}
              onChange={e => setStudyHours(p => ({ ...p, study_end: e.target.value }))}
              required
              style={{ ...inputStyle, marginTop: '4px', width: 'auto' }}
            />
          </label>
          <button type="submit" disabled={savingHours} style={{ ...btnStyle, alignSelf: 'flex-end' }}>
            {savingHours ? 'Saving…' : 'Save'}
          </button>
        </form>
        {studyHoursStatus && (
          <p style={{ color: studyHoursStatus.type === 'success' ? 'green' : 'red', margin: '8px 0 0' }}>
            {studyHoursStatus.message}
          </p>
        )}
      </section>

      {/* ── Assignments ─────────────────────────────── */}
      <section style={{ marginBottom: '40px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <h2 style={{ margin: 0 }}>Assignments</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {uploading && <span style={{ fontSize: '13px', color: '#888' }}>Importing…</span>}
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              style={{ ...btnStyle, fontSize: '13px', padding: '7px 12px' }}
            >
              Upload .ics
            </button>
            {assignments.length > 0 && (
              <button
                onClick={handleDeleteAll}
                disabled={deleting}
                style={{ ...btnStyle, fontSize: '13px', padding: '7px 12px', background: '#e53e3e' }}
              >
                {deleting ? 'Deleting…' : 'Delete All'}
              </button>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".ics"
              onChange={handleICSUpload}
              style={{ display: 'none' }}
            />
          </div>
        </div>

        {uploadStatus && (
          <p style={{ color: uploadStatus.type === 'success' ? 'green' : 'red', margin: '0 0 12px' }}>
            {uploadStatus.message}
          </p>
        )}

        {assignments.length === 0 ? (
          <p style={{ color: '#888' }}>No assignments yet. Upload a .ics file to import.</p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {assignments.map(a => (
              <li key={a.id} style={{ border: '1px solid #ddd', borderRadius: '6px', padding: '12px', display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: '600', marginBottom: '4px' }}>{a.title}</div>
                  <div style={{ fontSize: '13px', color: '#4285f4', marginBottom: '2px' }}>{a.course || 'No course'}</div>
                  <div style={{ fontSize: '13px', color: '#555' }}>Due: {formatDate(a.due_date)}</div>
                  {a.description && (
                    <div style={{ fontSize: '12px', color: '#888', marginTop: '4px', whiteSpace: 'pre-wrap' }}>{a.description}</div>
                  )}
                  <button
                    onClick={() => handleAnalyze(a.id)}
                    disabled={analyzingId === a.id}
                    style={{ ...btnStyle, fontSize: '12px', padding: '6px 10px', marginTop: '10px' }}
                  >
                    {analyzingId === a.id ? 'Analyzing…' : a.estimated_hours != null ? 'Re-analyze' : 'Analyze'}
                  </button>
                </div>

                {a.estimated_hours != null && (
                  <pre style={{ margin: 0, padding: '10px', background: '#f5f5f5', borderRadius: '4px', fontSize: '12px', lineHeight: '1.5', flexShrink: 0, whiteSpace: 'pre-wrap' }}>
                    {JSON.stringify({
                      estimated_hours: a.estimated_hours,
                      difficulty: a.difficulty,
                      importance: a.importance,
                      urgency: a.urgency,
                      recommended_session_minutes: a.recommended_session_minutes,
                      num_sessions: a.num_sessions,
                      start_days_before_due: a.start_days_before_due,
                    }, null, 2)}
                  </pre>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ── Add Calendar Event ───────────────────────── */}
      {!user.google_connected ? (
        <div style={{ background: '#fff3cd', border: '1px solid #ffc107', borderRadius: '6px', padding: '14px' }}>
          <p style={{ margin: '0 0 10px', fontWeight: '500' }}>Connect Google Calendar to create study events.</p>
          <button onClick={handleConnectGoogle} style={btnStyle}>
            Connect Google Calendar
          </button>
        </div>
      ) : (
        <>
          <form onSubmit={handleCreateEvent} style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '16px' }}>
            <h2 style={{ margin: '0 0 4px' }}>Add Calendar Event</h2>
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

          {eventStatus && (
            <p style={{ color: eventStatus.type === 'success' ? 'green' : 'red' }}>
              {eventStatus.message}
            </p>
          )}
        </>
      )}
    </div>
  )
}
