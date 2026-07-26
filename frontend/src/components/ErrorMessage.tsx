interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorMessage({ message, onRetry }: ErrorMessageProps) {
  return (
    <div className="error-box">
      <strong>Error:</strong> {message}
      {onRetry && (
        <button
          onClick={onRetry}
          className="btn btn-sm"
          style={{ marginLeft: "1rem" }}
        >
          Retry
        </button>
      )}
    </div>
  );
}
