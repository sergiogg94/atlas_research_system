interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorMessage({ message, onRetry }: ErrorMessageProps) {
  return (
    <div style={{
      padding: "1rem",
      background: "var(--accent-bg)",
      border: "1px solid var(--accent-border)",
      borderRadius: "4px",
      color: "var(--accent)",
      margin: "1rem 0",
    }}>
      <strong>Error:</strong> {message}
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            marginLeft: "1rem",
            padding: "0.25rem 0.75rem",
            background: "var(--accent)",
            color: "var(--text-h)",
            border: "none",
            borderRadius: "4px",
            cursor: "pointer",
          }}
        >
          Retry
        </button>
      )}
    </div>
  );
}
