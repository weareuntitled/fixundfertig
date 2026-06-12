/**
 * @schema Card
 * @purpose Reusable card container with consistent border, radius, and shadow
 * @input {string} classes - Additional CSS classes
 * @input {ReactNode} children - Card content
 * @output Renders div with card styling tokens
 * @tokens Uses: card-bg, card-border, card-radius, card-shadow
 */
import type { ReactNode } from "react";

interface CardProps {
  classes?: string;
  children: ReactNode;
}

export function Card({ classes = "", children }: CardProps) {
  return (
    <div
      className={`bg-[var(--card-bg)] border border-[var(--card-border)] rounded-[var(--card-radius)] shadow-[var(--card-shadow)] ${classes}`}
    >
      {children}
    </div>
  );
}
