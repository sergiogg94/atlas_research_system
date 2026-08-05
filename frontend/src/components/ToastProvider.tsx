import { createContext, useContext, useReducer, useCallback, type ReactNode } from "react";

type ToastType = "success" | "error" | "info";

interface Toast {
  id: string;
  message: string;
  type: ToastType;
}

interface ToastState {
  toasts: Toast[];
}

type ToastAction =
  | { type: "ADD"; toast: Toast }
  | { type: "REMOVE"; id: string };

function toastReducer(state: ToastState, action: ToastAction): ToastState {
  switch (action.type) {
    case "ADD":
      return { toasts: [...state.toasts, action.toast] };
    case "REMOVE":
      return { toasts: state.toasts.filter((t) => t.id !== action.id) };
    default:
      return state;
  }
}

interface ToastContextValue {
  toasts: Toast[];
  addToast: (message: string, type?: ToastType) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let toastCounter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(toastReducer, { toasts: [] });

  const addToast = useCallback(function addToast(message: string, type: ToastType = "info") {
    const id = `toast-${++toastCounter}`;
    dispatch({ type: "ADD", toast: { id, message, type } });
    setTimeout(() => dispatch({ type: "REMOVE", id }), 4000);
  }, []);

  const removeToast = useCallback(function removeToast(id: string) {
    dispatch({ type: "REMOVE", id });
  }, []);

  return (
    <ToastContext.Provider value={{ toasts: state.toasts, addToast, removeToast }}>
      {children}
      {/* Toast container fixed at bottom-right */}
      <div className="toast-container">
        {state.toasts.map((toast) => (
          <div
            key={toast.id}
            className={`toast toast--${toast.type}`}
            onClick={() => removeToast(toast.id)}
          >
            {toast.type === "success" && "✓ "}
            {toast.type === "error" && "✗ "}
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
