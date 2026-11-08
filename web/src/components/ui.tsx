import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link, type LinkProps } from "react-router-dom";
import { Loader2 } from "lucide-react";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const variants: Record<Variant, string> = {
  primary: "bg-accent text-accent-ink hover:bg-accent-hover shadow-sm",
  secondary: "bg-surface text-ink border border-line-strong hover:bg-surface-2",
  ghost: "text-ink-2 hover:text-ink hover:bg-surface-2",
  danger: "bg-surface text-critical-ink border border-line-strong hover:bg-critical-soft",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-sm gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
  lg: "h-12 px-6 text-base gap-2",
};

function buttonClass(variant: Variant, size: Size, className?: string) {
  return cx(
    "inline-flex items-center justify-center rounded-lg font-medium transition-colors whitespace-nowrap",
    "disabled:opacity-50 disabled:pointer-events-none",
    variants[variant],
    sizes[size],
    className,
  );
}

export function Button({
  variant = "primary",
  size = "md",
  loading,
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; loading?: boolean }) {
  return (
    <button className={buttonClass(variant, size, className)} disabled={loading || props.disabled} {...props}>
      {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function ButtonLink({
  variant = "primary",
  size = "md",
  className,
  ...props
}: LinkProps & { variant?: Variant; size?: Size }) {
  return <Link className={buttonClass(variant, size, className)} {...props} />;
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cx("rounded-2xl border border-line bg-surface shadow-card", className)}>{children}</div>
  );
}

export function SectionTitle({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return (
    <div className="mb-6">
      {eyebrow && <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-accent">{eyebrow}</p>}
      <h2 className="text-xl font-semibold tracking-tight text-ink">{title}</h2>
      {children && <p className="mt-1.5 max-w-2xl text-sm text-ink-2">{children}</p>}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-3xl">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2 no-print">{actions}</div>}
    </div>
  );
}

export type Tone = "good" | "warning" | "critical" | "neutral" | "accent";

const tones: Record<Tone, string> = {
  good: "bg-good-soft text-good-ink",
  warning: "bg-warning-soft text-warning-ink",
  critical: "bg-critical-soft text-critical-ink",
  neutral: "bg-surface-2 text-ink-2",
  accent: "bg-accent-soft text-accent",
};

export function Badge({ tone = "neutral", className, children }: { tone?: Tone; className?: string; children: ReactNode }) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

// One name/value group for a <dl>. HTML allows a single <div> around each group, so
// layout classes go on this div (className) rather than on an extra wrapper.
export function Stat({
  label,
  value,
  hint,
  wrap,
  className,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  wrap?: boolean;
  className?: string;
}) {
  return (
    <div className={cx("min-w-0", className)}>
      <dt className="text-xs font-medium uppercase tracking-wide text-ink-3">{label}</dt>
      <dd className={cx("mt-1 text-sm font-medium text-ink tabular", wrap ? "break-words" : "truncate")}>{value}</dd>
      {hint && <dd className="mt-0.5 text-xs text-ink-3">{hint}</dd>}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  children,
  action,
  heading: Heading = "h3",
}: {
  icon: ReactNode;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  /** "h1" when the empty state is the whole page (e.g. 404), so the page still has a top-level heading */
  heading?: "h1" | "h2" | "h3";
}) {
  return (
    <Card className="flex flex-col items-center px-6 py-16 text-center">
      <div className="mb-4 grid size-12 place-items-center rounded-xl bg-surface-2 text-ink-3">{icon}</div>
      <Heading className="font-semibold text-ink">{title}</Heading>
      {children && <p className="mt-1 max-w-sm text-sm text-ink-2">{children}</p>}
      {action && <div className="mt-6">{action}</div>}
    </Card>
  );
}
