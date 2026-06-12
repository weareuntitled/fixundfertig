import type { ChangeEvent } from "react";

interface SelectOption {
  value: string | number;
  label: string;
}

interface SelectProps {
  label: string;
  value: string | number | null;
  onChange: (value: string) => void;
  options: SelectOption[];
  required?: boolean;
  disabled?: boolean;
  className?: string;
  placeholder?: string;
}

export function Select({
  label,
  value,
  onChange,
  options,
  required = false,
  disabled = false,
  className = "",
  placeholder = "Bitte wählen…",
}: SelectProps) {
  const handle = (e: ChangeEvent<HTMLSelectElement>) => onChange(e.target.value);
  return (
    <label className={`block ${className}`}>
      <span className="mb-1.5 block text-[13px] font-medium text-[var(--color-text-primary)]">
        {label} {required && <span className="text-[var(--color-red-500)]">*</span>}
      </span>
      <select
        value={value ?? ""}
        onChange={handle}
        required={required}
        disabled={disabled}
        className="block w-full h-10 rounded-[8px] border border-[var(--color-border-strong)] bg-white px-3 text-[14px] text-[var(--color-text-primary)] outline-none transition-all focus:border-[var(--color-border-focus)] focus:shadow-[0_0_0_3px_rgba(0,122,255,0.12)] disabled:bg-[var(--color-gray-50)] disabled:text-[var(--color-text-tertiary)]"
      >
        <option value="" disabled>
          {placeholder}
        </option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}
