/**
 * @schema Button
 * @purpose Apple-style refined button: 4 variants, 3 sizes, subtle interactions
 */
import type { ReactNode, ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "outline" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  icon?: ReactNode;
  children: ReactNode;
}

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-[var(--color-text-heading)] text-white shadow-sm hover:bg-[var(--color-gray-700)] active:scale-[0.97]",
  secondary:
    "bg-white text-[var(--color-text-primary)] border border-[var(--color-border-strong)] hover:bg-[var(--color-gray-50)] active:scale-[0.97]",
  outline:
    "bg-transparent text-[var(--color-text-primary)] border border-[var(--color-border)] hover:bg-[var(--color-gray-50)]",
  ghost:
    "bg-transparent text-[var(--color-text-secondary)] hover:bg-[var(--color-gray-50)] hover:text-[var(--color-text-primary)]",
  danger:
    "bg-[var(--color-red-500)] text-white shadow-sm hover:bg-[var(--color-red-600)] active:scale-[0.97]",
};

const sizeClasses: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5",
  md: "h-9 px-4 text-[14px] gap-2",
  lg: "h-10 px-5 text-[15px] gap-2",
};

export function Button({
  variant = "primary",
  size = "md",
  icon,
  children,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center rounded-[8px] font-medium transition-all duration-150 ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    >
      {icon}
      {children}
    </button>
  );
}
