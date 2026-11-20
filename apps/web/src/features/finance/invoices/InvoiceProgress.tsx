import { Check } from "lucide-react";

const STEPS = ["Cargar PDF", "Moderar", "Exportar"] as const;

type Props = {
  currentStep: number;
};

export function InvoiceProgress({ currentStep }: Props) {
  return (
    <ol className="stepper" aria-label="Progreso">
      {STEPS.map((label, index) => {
        const step = index + 1;
        const stateClass =
          step < currentStep
            ? "is-done"
            : step === currentStep
              ? "is-active"
              : "";

        return (
          <li key={label} className={stateClass}>
            <span>{step < currentStep ? <Check size={15} /> : step}</span>
            <strong>{label}</strong>
          </li>
        );
      })}
    </ol>
  );
}

