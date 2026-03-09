import { getAccessToken, getRefreshToken, setTokens, clearTokens } from './auth';

const BACKEND = 'http://localhost:8000';

let isRefreshing = false;
let refreshSubscribers = [];

function subscribeTokenRefresh(callback) {
  refreshSubscribers.push(callback);
}

function onTokenRefreshed(newToken) {
  refreshSubscribers.forEach(cb => cb(newToken));
  refreshSubscribers = [];
}

async function refreshAccessToken() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) throw new Error('No refresh token');

  const res = await fetch(`${BACKEND}/api/auth/token/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh: refreshToken }),
  });

  if (!res.ok) throw new Error('Refresh failed');

  const data = await res.json();
  setTokens({ access: data.access, refresh: data.refresh });
  return data.access;
}

export async function apiFetch(path, options = {}) {
  const url = `${BACKEND}${path}`;
  const token = getAccessToken();

  const makeRequest = (accessToken) => fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
  });

  let response = await makeRequest(token);

  if (response.status === 401) {
    if (!isRefreshing) {
      isRefreshing = true;
      try {
        const newToken = await refreshAccessToken();
        isRefreshing = false;
        onTokenRefreshed(newToken);
        response = await makeRequest(newToken);
      } catch {
        isRefreshing = false;
        clearTokens();
        window.location.href = '/login';
        throw new Error('Session expired');
      }
    } else {
      return new Promise((resolve, reject) => {
        subscribeTokenRefresh(async (newToken) => {
          try {
            resolve(await makeRequest(newToken));
          } catch (err) {
            reject(err);
          }
        });
      });
    }
  }

  return response;
}
