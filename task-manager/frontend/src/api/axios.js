import axios from 'axios';

// The only place the backend URL is read.
const API_URL = import.meta.env.VITE_API_URL;

const ACCESS_KEY = 'access_token';
const REFRESH_KEY = 'refresh_token';

export const tokenStore = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  setTokens: (access, refresh) => {
    if (access) localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear: () => {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Request: attach the access token to every request.
api.interceptors.request.use((config) => {
  const token = tokenStore.getAccess();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Response: on 401 refresh once, store the new access token, retry the request.
const NO_REFRESH_URLS = ['/auth/login/', '/auth/register/', '/auth/token/refresh/', '/auth/logout/'];
let refreshPromise = null; // shared so parallel 401s trigger a single refresh

function forceLogout() {
  tokenStore.clear();
  window.dispatchEvent(new Event('auth:logout'));
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const skip = !original || NO_REFRESH_URLS.some((u) => original.url?.includes(u));
    if (error.response?.status !== 401 || original?._retry || skip) {
      return Promise.reject(error);
    }
    original._retry = true;

    const refresh = tokenStore.getRefresh();
    if (!refresh) {
      forceLogout();
      return Promise.reject(error);
    }
    try {
      if (!refreshPromise) {
        // plain axios (no interceptors) so a failing refresh cannot loop
        refreshPromise = axios
          .post(`${API_URL}/auth/token/refresh/`, { refresh })
          .finally(() => {
            refreshPromise = null;
          });
      }
      const { data } = await refreshPromise;
      tokenStore.setTokens(data.access, data.refresh);
      original.headers.Authorization = `Bearer ${data.access}`;
      return api(original);
    } catch {
      forceLogout();
      return Promise.reject(error);
    }
  }
);

export default api;
