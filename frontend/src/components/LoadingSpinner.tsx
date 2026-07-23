interface LoadingSpinnerProps {
  message?: string;
}

export function LoadingSpinner({ message = "Loading..." }: LoadingSpinnerProps) {
  return (
    <div style={{ textAlign: "center", padding: "3rem", color: "var(--text)" }}>
      <div style={{
        width: "40px",
        height: "40px",
        margin: "0 auto 1rem",
        border: "4px solid var(--border)",
        borderTop: "4px solid var(--accent)",
        borderRadius: "50%",
        animation: "spin 1s linear infinite",
      }} />
      <p>{message}</p>
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
