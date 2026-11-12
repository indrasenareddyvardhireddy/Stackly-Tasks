import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import * as authApi from '../api/authApi.js';
import { tokenStore } from '../api/axios.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // If a token exists we must verify it before deciding where to route.
  const [loading, setLoading] = useState(() => Boolean(tokenStore.getAccess() || tokenStore.getRefresh()));

  // Stay logged in after a page refresh.
  useEffect(() => {
    if (!loading) return;
    authApi
      .getMe()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The Axios interceptor fires this when refreshing fails.
  useEffect(() => {
    const onForcedLogout = () => setUser(null);
    window.addEventListener('auth:logout', onForcedLogout);
    return () => window.removeEventListener('auth:logout', onForcedLogout);
  }, []);

  const login = useCallback(async (email, password) => {
    const tokens = await authApi.login(email, password);
    tokenStore.setTokens(tokens.access, tokens.refresh);
    setUser(await authApi.getMe());
  }, []);

  const logout = useCallback(async () => {
    const refresh = tokenStore.getRefresh();
    try {
      if (refresh) await authApi.logout(refresh); // blacklist the refresh token
    } catch {
      /* already invalid - ignore */
    }
    tokenStore.clear();
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
