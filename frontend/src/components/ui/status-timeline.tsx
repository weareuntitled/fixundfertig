/**
 * @schema StatusTimeline
 * @purpose Horizontal stepper showing invoice status progression with visual indicators
 * @input {string} currentStatus - Current invoice status value
 * @output Renders 4-step timeline: Entwurf → Finalisiert → Gesendet → Bezahlt
 * @tokens Uses: color-brand, color-brand-text, color-border, color-text-primary, color-text-muted
 */
import { Check, Circle, Mail, CreditCard } from "lucide-react";

interface StatusTimelineProps {
  currentStatus: string;
}

const STEPS = [
  { key: "DRAFT", label: "Entwurf", icon: Check },
  { key: "OPEN", label: "Finalisiert", icon: Circle },
  { key: "SENT", label: "Gesendet", icon: Mail },
  { key: "PAID", label: "Bezahlt", icon: CreditCard },
] as const;

function getStepIndex(status: string): number {
  if (status === "DRAFT") return 0;
  if (status === "OPEN" || status === "FINALIZED") return 1;
  if (status === "SENT") return 2;
  if (status === "PAID") return 3;
  if (status === "CANCELLED") return -1;
  return 1;
}

export function StatusTimeline({ currentStatus }: StatusTimelineProps) {
  const currentIdx = getStepIndex(currentStatus);

  return (
    <div className="relative">
      {/* Connecting line */}
      <div className="absolute top-4 left-[10%] right-[10%] h-[2px] bg-[var(--color-border)] -translate-y-1/2 z-0 hidden md:block" />
      <div
        className="absolute top-4 left-[10%] right-[60%] h-[2px] bg-[var(--color-brand)] -translate-y-1/2 z-0 hidden md:block"
        style={{ opacity: currentIdx >= 0 ? 1 : 0 }}
      />

      <div className="flex flex-col md:flex-row justify-between relative z-10 gap-6 md:gap-0">
        {STEPS.map((step, idx) => {
          const isCompleted = idx < currentIdx;
          const isCurrent = idx === currentIdx;
          const isPending = idx > currentIdx;
          const Icon = step.icon;

          return (
            <div
              key={step.key}
              className={`flex flex-row md:flex-col items-center gap-4 md:gap-2 ${
                isPending ? "opacity-50" : ""
              }`}
            >
              {/* Circle */}
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 shadow-sm ${
                  isCompleted
                    ? "bg-[var(--color-brand)] text-[var(--color-text-on-brand)] border-2 border-white"
                    : isCurrent
                      ? "bg-white border-2 border-[var(--color-brand)] text-[var(--color-brand)]"
                      : "bg-[var(--color-surface-container-highest)] border border-[var(--color-border)] text-[var(--color-text-muted)]"
                }`}
              >
                {isCompleted ? (
                  <Check size={14} style={{ fontVariationSettings: "'FILL' 1" }} />
                ) : isCurrent ? (
                  <div className="w-3 h-3 bg-[var(--color-brand)] rounded-full" />
                ) : (
                  <Icon size={14} />
                )}
              </div>

              {/* Label */}
              <div className="md:text-center">
                <p
                  className={`text-[10px] font-semibold uppercase tracking-wider ${
                    isCurrent
                      ? "text-[var(--color-text-primary)] font-bold"
                      : isCompleted
                        ? "text-[var(--color-text-primary)]"
                        : "text-[var(--color-text-muted)]"
                  }`}
                >
                  {step.label}
                </p>
                <p className="text-[11px] text-[var(--color-text-muted)]">
                  {isCompleted ? "Abgeschlossen" : isCurrent ? "Aktuell" : "Ausstehend"}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
