interface StatusBadgeProps {
  status: string;
}

const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  completed: { bg: "#dfd", color: "#090" },
  failed: { bg: "#fdd", color: "#c00" },
  running: { bg: "#ffd", color: "#960" },
  pending: { bg: "#eef", color: "#66c" },
  timeout: { bg: "#fdd", color: "#c00" },
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const colors = STATUS_COLORS[status] || { bg: "var(--accent-bg)", color: "var(--accent)" };
  return (
    <span style={{
      padding: "0.25rem 0.5rem",
      borderRadius: "4px",
      fontSize: "0.875rem",
      background: colors.bg,
      color: colors.color,
      fontWeight: 600,
    }}>
      {status}
    </span>
  );
}
