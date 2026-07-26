interface StatusBadgeProps {
  status: string;
}

const STATUS_CLASSES: Record<string, string> = {
  completed: "badge--completed",
  failed: "badge--failed",
  running: "badge--running",
  pending: "badge--pending",
  timeout: "badge--timeout",
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const className = STATUS_CLASSES[status] || "";
  return (
    <span className={`badge ${className}`}>
      {status}
    </span>
  );
}
