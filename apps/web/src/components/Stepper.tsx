type Step = {
  label: string;
  description?: string;
};

type Props = {
  steps: Step[];
  active: number;
};

export function Stepper({ steps, active }: Props) {
  return (
    <ol
      className="stepper"
      aria-label="Progreso"
      style={{
        gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))`,
      }}
    >
      {steps.map((step, index) => {
        const number = index + 1;
        const state =
          number < active ? "is-done" : number === active ? "is-active" : "";
        return (
          <li key={step.label} className={"stepper__item " + state}>
            <span className="stepper__number">
              {number < active ? "✓" : number}
            </span>
            <span>
              <strong>{step.label}</strong>
              {step.description && <small>{step.description}</small>}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
