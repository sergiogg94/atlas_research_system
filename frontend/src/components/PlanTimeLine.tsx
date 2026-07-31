interface PlanStep {
  type: string;
  description: string;
  status: "pending" | "running" | "completed" | "failed";
}

interface PlanTimeLineProps {
  objective: string;
  steps: PlanStep[];
}

const STEP_ICONS: Record<string, string> = {
  scoping: "🎯",
  research: "🔍",
  analysis: "📊",
  synthesis: "📝",
};

export function PlanTimeLine({ objective, steps }: PlanTimeLineProps) {
  return (
    <div className="plan-timeline">
      <h3 className="plan-timeline-objective">{objective}</h3>
      <div className="plan-timeline-steps">
        {steps.map((step, index) => (
          <div
            key={index}
            className={`plan-step plan-step--${step.status}`}
          >
            <div className="plan-step-marker">
              <span className="plan-step-icon">
                {STEP_ICONS[step.type] || "•"}
              </span>
              {index < steps.length - 1 && <div className="plan-step-line" />}
            </div>
            <div className="plan-step-content">
              <div className="plan-step-header">
                <span className="plan-step-type">{step.type}</span>
                <span className={`plan-step-status plan-step-status--${step.status}`}>
                  {step.status}
                </span>
              </div>
              <p className="plan-step-description">{step.description}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
