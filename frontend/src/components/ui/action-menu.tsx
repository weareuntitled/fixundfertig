/**
 * @schema ActionMenu
 * @purpose "Mehr" dropdown that keeps rarely used page actions out of the header row
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { MoreHorizontal } from "lucide-react";

export interface ActionMenuItem {
  label: string;
  icon: ReactNode;
  onSelect: () => void;
  disabled?: boolean;
  danger?: boolean;
}

export interface ActionMenuProps {
  items: ActionMenuItem[];
  /** Text of the trigger; default "Mehr". */
  label?: string;
  /** Icon of the trigger; default the three-dot icon. */
  icon?: ReactNode;
  /** Look of the trigger; default the quiet "Mehr" look. */
  triggerClassName?: string;
  /** Further attributes of the trigger, e.g. `data-primary` on the quote page. */
  triggerAttributes?: Record<string, string>;
}

export function ActionMenu({
  items,
  label = "Mehr",
  icon,
  triggerClassName,
  triggerAttributes,
}: ActionMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent) {
        if (event.key === "Escape") setOpen(false);
      } else if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        {...triggerAttributes}
        className={
          triggerClassName ??
          "inline-flex min-h-[44px] items-center gap-2 rounded-[var(--radius-lg)] sm:min-h-0 border border-[var(--color-border)] bg-white px-[var(--space-md)] py-[var(--space-xs)] text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-heading)] transition-colors hover:bg-[var(--color-surface-container-high)]"
        }
      >
        {icon ?? <MoreHorizontal size={16} />}
        {label}
      </button>
      {open && (
        <div
          role="menu"
          className="animate-fade-in-scale absolute right-0 z-30 mt-1 w-56 origin-top-right overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white py-1 shadow-lg"
        >
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              disabled={item.disabled}
              onClick={() => {
                setOpen(false);
                item.onSelect();
              }}
              className={`flex min-h-[44px] w-full items-center gap-2 px-3 py-2 text-left text-[13px] font-medium transition-colors hover:bg-[var(--color-surface-container-high)] disabled:opacity-50 ${
                item.danger ? "text-red-600 hover:bg-red-50" : "text-[var(--color-text-primary)]"
              }`}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
