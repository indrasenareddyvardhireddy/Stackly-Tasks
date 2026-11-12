// Turns an Axios error into { message, fieldErrors } for forms and toasts.
export function parseApiError(err) {
  const fieldErrors = {};
  let message = '';

  if (!err.response) {
    return { message: 'Cannot reach the server. Check your connection and try again.', fieldErrors };
  }
  const data = err.response.data;
  if (data && typeof data === 'object') {
    Object.entries(data).forEach(([key, value]) => {
      const text = Array.isArray(value) ? value.join(' ') : String(value);
      if (key === 'detail' || key === 'non_field_errors') message = text;
      else fieldErrors[key] = text;
    });
  }
  if (!message) {
    message = Object.keys(fieldErrors).length
      ? 'Please fix the highlighted fields.'
      : 'Something went wrong. Please try again.';
  }
  return { message, fieldErrors };
}

export const todayISO = () => {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
};

export const formatDate = (iso) =>
  iso
    ? new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
    : 'No due date';
