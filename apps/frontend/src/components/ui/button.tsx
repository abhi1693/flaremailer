import { LoaderCircle, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { forwardRef, type AnchorHTMLAttributes, type ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg" | "icon";
  icon?: LucideIcon;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className = "", variant = "primary", size = "md", icon: Icon, loading, children, disabled, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      className={buttonClass(variant, size, className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <LoaderCircle className="spin" size={17} aria-hidden="true" /> : Icon ? <Icon size={17} aria-hidden="true" /> : null}
      {children}
    </button>
  );
});

export function ButtonLink({
  href,
  variant = "primary",
  size = "md",
  icon: Icon,
  className = "",
  children,
  ...props
}: AnchorHTMLAttributes<HTMLAnchorElement> & {
  href: string;
  variant?: ButtonProps["variant"];
  size?: ButtonProps["size"];
  icon?: LucideIcon;
}) {
  return (
    <Link href={href} className={buttonClass(variant, size, className)} {...props}>
      {Icon ? <Icon size={17} aria-hidden="true" /> : null}
      {children}
    </Link>
  );
}

function buttonClass(variant: NonNullable<ButtonProps["variant"]>, size: NonNullable<ButtonProps["size"]>, className: string) {
  return `button button-${variant} button-${size} ${className}`;
}
