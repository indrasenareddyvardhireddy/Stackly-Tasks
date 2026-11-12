import api from './axios.js';

export const listTasks = (params) => api.get('/tasks/', { params }).then((r) => r.data);
export const getTask = (id) => api.get(`/tasks/${id}/`).then((r) => r.data);
export const createTask = (data) => api.post('/tasks/', data).then((r) => r.data);
export const updateTask = (id, data) => api.put(`/tasks/${id}/`, data).then((r) => r.data);
export const patchTask = (id, data) => api.patch(`/tasks/${id}/`, data).then((r) => r.data);
export const deleteTask = (id) => api.delete(`/tasks/${id}/`);
export const toggleComplete = (id) => api.patch(`/tasks/${id}/toggle-complete/`).then((r) => r.data);
export const getDashboard = () => api.get('/tasks/dashboard/').then((r) => r.data);

// subtasks (bonus)
export const addSubtask = (taskId, title) =>
  api.post(`/tasks/${taskId}/subtasks/`, { title }).then((r) => r.data);
export const updateSubtask = (taskId, id, data) =>
  api.patch(`/tasks/${taskId}/subtasks/${id}/`, data).then((r) => r.data);
export const deleteSubtask = (taskId, id) => api.delete(`/tasks/${taskId}/subtasks/${id}/`);
