import api from './axios.js';

export const register = (data) => api.post('/auth/register/', data).then((r) => r.data);
export const login = (email, password) =>
  api.post('/auth/login/', { email, password }).then((r) => r.data);
export const logout = (refresh) => api.post('/auth/logout/', { refresh });
export const getMe = () => api.get('/auth/me/').then((r) => r.data);
export const changePassword = (data) => api.put('/auth/change-password/', data).then((r) => r.data);
