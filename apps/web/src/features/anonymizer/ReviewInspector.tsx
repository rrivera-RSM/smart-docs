import { Check, ChevronDown, ChevronUp, CircleCheck, CircleHelp, CircleAlert, Layers3, X } from "lucide-react";

import styles from "./anonymizer.module.css";
import type { Finding, FindingGroup } from "./contract";

export type GroupReview = Record<string, { selected: boolean; replacement: string; expanded: boolean }>;

const bandMeta = {
  validated: { label: "Validado", icon: CircleCheck },
  probable: { label: "Probable", icon: CircleHelp },
  review: { label: "Revisar", icon: CircleAlert },
};

export function ReviewInspector({
  groups,
  findings,
  review,
  onChange,
}: {
  groups: FindingGroup[];
  findings: Finding[];
  review: GroupReview;
  onChange: (id: string, next: GroupReview[string]) => void;
}) {
  if (!groups.length) {
    return (
      <div className={styles.emptyState}>
        <CircleCheck size={28} />
        <strong>No hay grupos con estos filtros</strong>
        <span>Ajusta los filtros para volver a mostrar detecciones.</span>
      </div>
    );
  }

  return (
    <div className={styles.groupList} aria-label="Grupos de información sensible">
      {groups.map((group) => {
        const state = review[group.id] ?? {
          selected: group.selected_by_default,
          replacement: group.replacement,
          expanded: false,
        };
        const BandIcon = bandMeta[group.confidence_band].icon;
        const occurrences = findings.filter((finding) => finding.group_id === group.id);
        return (
          <article
            className={`${styles.groupCard} ${state.selected ? styles.groupSelected : ""}`}
            key={group.id}
          >
            <div className={styles.groupTopline}>
              <span className={styles.entityBadge}>{group.label}</span>
              <span className={`${styles.band} ${styles[`band_${group.confidence_band}`]}`}>
                <BandIcon size={13} />
                {bandMeta[group.confidence_band].label}
              </span>
              <div className={styles.decisionActions} aria-label={`Decisión para ${group.value}`}>
                <button type="button" className={state.selected ? styles.decisionActive : ""} aria-pressed={state.selected} onClick={() => onChange(group.id, { ...state, selected: true })}><Check size={14} /> Aprobar</button>
                <button type="button" className={!state.selected ? styles.decisionActive : ""} aria-pressed={!state.selected} onClick={() => onChange(group.id, { ...state, selected: false })}><X size={14} /> Omitir</button>
              </div>
            </div>

            <div className={styles.groupBody}>
              <div className={styles.sensitiveValue} title={group.value}>{group.value}</div>
              <button
                type="button"
                className={styles.expandButton}
                onClick={() => onChange(group.id, { ...state, expanded: !state.expanded })}
                aria-expanded={state.expanded}
              >
                <Layers3 size={15} />
                {group.occurrence_count} {group.occurrence_count === 1 ? "aparición" : "apariciones"}
                {state.expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
              </button>
            </div>

            {state.expanded && (
              <div className={styles.occurrences}>
                {occurrences.map((finding, index) => (
                  <div className={styles.occurrence} key={finding.id}>
                    <div>
                      <span>#{index + 1}</span>
                      <strong>{finding.location.label}</strong>
                      <small>{Math.round(finding.confidence * 100)}% confianza</small>
                    </div>
                    <p>{finding.context}</p>
                  </div>
                ))}
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}
