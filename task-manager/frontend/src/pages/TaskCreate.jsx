import { useNavigate } from 'react-router-dom';
import TaskForm from '../components/TaskForm.jsx';
import { createTask } from '../api/taskApi.js';
import { useToast } from '../context/ToastContext.jsx';

export default function TaskCreate() {
  const navigate = useNavigate();
  const toast = useToast();

  const handleSubmit = async (payload) => {
    await createTask(payload);
    toast.success('Task created.');
    navigate('/tasks');
  };

  return (
    <>
      <div className="page-head"><h1>New task</h1></div>
      <TaskForm onSubmit={handleSubmit} submitLabel="Create task" />
    </>
  );
}
