import { createContext, useContext, useReducer, type ReactNode } from "react";

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

  function addToast(message: string, type: ToastType = "info") {
    const id = `toast-${++toastCounter}`;
    dispatch({ type: "ADD", toast: { id, message, type } });
    setTimeout(() => dispatch({ type: "REMOVE", id }), 4000);
  }

  function removeToast(id: string) {
    dispatch({ type: "REMOVE", id });
  }

  return (
    <ToastContext.Provider value={{ toasts: state.toasts, addToast, removeToast }}>
      {children}
      {/* Toast container fixed at bottom-right */}
      <div style={{
        position: "fixed",
        bottom: "1rem",
        right: "1rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.5rem",
        zIndex: 1000,
      }}>
        {state.toasts.map((toast) => (
          <div
            key={toast.id}
            style={{
              padding: "0.75rem 1rem",
              borderRadius: "4px",
              color: "white",
              background: toast.type === "success" ? "#090"
                : toast.type === "error" ? "#c00"
                : "#1a1a2e",
              boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
              animation: "slideIn 0.3s ease-out",
              cursor: "pointer",
              minWidth: "250px",
            }}
            onClick={() => removeToast(toast.id)}
          >
            {toast.type === "success" && "✓ "}
            {toast.type === "error" && "✗ "}
            {toast.message}
          </div>
        ))}
      </div>
      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
