import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import Loader from '../components/Loader.jsx';
import SubtaskList from '../components/SubtaskList.jsx';
import TaskForm from '../components/TaskForm.jsx';
import { getTask, updateTask } from '../api/taskApi.js';
import { useToast } from '../context/ToastContext.jsx';
import { parseApiError } from '../utils/errors.js';

export default function TaskEdit() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [task, setTask] = useState(null);

  useEffect(() => {
    getTask(id)
      .then(setTask)
      .catch((err) => {
        toast.error(err.response?.status === 404 ? 'That task does not exist.' : parseApiError(err).message);
        navigate('/tasks', { replace: true });
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const handleSubmit = async (payload) => {
    await updateTask(id, payload);
    toast.success('Task updated.');
    navigate('/tasks');
  };

  if (!task) return <Loader />;

  const initialValues = {
    title: task.title,
    description: task.description,
    category: task.category ?? '',
    priority: task.priority,
    status: task.status,
    due_date: task.due_date ?? '',
    recurrence: task.recurrence,
  };

  return (
    <>
      <div className="page-head"><h1>Edit task</h1></div>
      <TaskForm isEdit initialValues={initialValues} onSubmit={handleSubmit} submitLabel="Save changes" />
      <SubtaskList taskId={task.id} initial={task.subtasks} />
    </>
  );
}
