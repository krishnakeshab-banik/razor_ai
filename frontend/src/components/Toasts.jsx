import { useApp } from '../AppContext';

export default function Toasts() {
  const { toasts } = useApp();
  return (
    <div className="toast-container">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast-${toast.type}`}>
          <span>{toast.message}</span>
        </div>
      ))}
    </div>
  );
}
