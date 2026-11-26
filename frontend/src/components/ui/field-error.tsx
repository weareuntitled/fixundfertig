import type { ReactNode } from "react";

/** A field's own error line; link it to the field with aria-describedby={id} (WCAG 3.3.1). */
export function FieldError({ id, children }: { id: string; children: ReactNode }) {
  return (
    <p id={id} className="mt-1 text-[12px] font-medium text-[var(--color-text-danger)]">
      {children}
    </p>
  );
}
