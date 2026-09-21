import type { LucideIcon } from "lucide-react";
import { ArrowRight, Check } from "lucide-react";
import Link from "next/link";

type Props = {
  to: string;
  eyebrow: string;
  title: string;
  description: string;
  action: string;
  icon: LucideIcon;
  tone: "blue" | "green";
  features: string[];
};

export function ToolCard({
  to,
  eyebrow,
  title,
  description,
  action,
  icon: Icon,
  tone,
  features,
}: Props) {
  return (
    <Link className={"tool-card tool-card--" + tone} href={to}>
      <div className="tool-card__top">
        <span className="tool-card__icon">
          <Icon size={22} strokeWidth={1.9} aria-hidden="true" />
        </span>
        <span className="tool-card__eyebrow">{eyebrow}</span>
      </div>
      <h2>{title}</h2>
      <p>{description}</p>
      <ul>
        {features.map((feature) => (
          <li key={feature}>
            <Check size={14} aria-hidden="true" />
            {feature}
          </li>
        ))}
      </ul>
      <span className="tool-card__action">
        {action}
        <ArrowRight size={17} aria-hidden="true" />
      </span>
    </Link>
  );
}
