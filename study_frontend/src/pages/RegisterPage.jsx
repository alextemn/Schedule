import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { setTokens } from '../auth';

const BACKEND = 'http://localhost:8000';

const inputStyle = { padding: '10px', fontSize: '14px', width: '100%', boxSizing: 'border-box', borderRadius: '4px', border: '1px solid #ccc' };
const btnStyle = { padding: '10px 16px', fontSize: '14px', cursor: 'pointer', border: 'none', borderRadius: '4px', background: '#4285f4', color: '#fff', width: '100%' };

export default function RegisterPage() {
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) => setForm(p => ({ ...p, [e.target.name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const res = await fetch(`${BACKEND}/api/auth/register/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    });

    const data = await res.json();
    setLoading(false);

    if (res.ok) {
      setTokens({ access: data.access, refresh: data.refresh });
      navigate('/');
    } else {
      const messages = Object.values(data).flat().join(' ');
      setError(messages || 'Registration failed');
    }
  };

  return (
    <div style={{ maxWidth: '380px', margin: '80px auto', fontFamily: 'sans-serif', padding: '0 16px' }}>
      <h1 style={{ marginBottom: '24px' }}>Create Account</h1>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <input
          name="name"
          placeholder="Name"
          value={form.name}
          onChange={handleChange}
          style={inputStyle}
        />
        <input
          name="email"
          type="email"
          placeholder="Email *"
          value={form.email}
          onChange={handleChange}
          required
          style={inputStyle}
        />
        <input
          name="password"
          type="password"
          placeholder="Password (8+ chars) *"
          value={form.password}
          onChange={handleChange}
          required
          minLength={8}
          style={inputStyle}
        />
        {error && <p style={{ color: 'red', margin: 0 }}>{error}</p>}
        <button type="submit" disabled={loading} style={btnStyle}>
          {loading ? 'Creating account…' : 'Register'}
        </button>
      </form>
      <p style={{ marginTop: '16px', textAlign: 'center' }}>
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </div>
  );
}
