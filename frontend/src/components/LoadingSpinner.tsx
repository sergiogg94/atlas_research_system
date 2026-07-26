interface LoadingSpinnerProps {
  message?: string;
}

export function LoadingSpinner({ message = "Loading..." }: LoadingSpinnerProps) {
  return (
    <div className="spinner-wrapper">
      <div className="spinner" />
      <p>{message}</p>
    </div>
  );
}
