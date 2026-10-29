import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Menu, Moon, ShieldCheck, Sun, X } from "lucide-react";
import { useHealth } from "../hooks/useHealth";
import { useTheme } from "../hooks/useTheme";
import { cx } from "./ui";

const NAV = [
  { to: "/analyze", label: "Analyze" },
  { to: "/batch", label: "Batch" },
  { to: "/history", label: "History" },
  { to: "/status", label: "System" },
  { to: "/docs", label: "API" },
  { to: "/about", label: "How it works" },
];

export function StatusPill({ compact }: { compact?: boolean }) {
  const { health } = useHealth();
  const [dot, label] =
    health.state === "loading"
      ? ["bg-ink-3", "Connecting"]
      : health.state === "offline"
        ? ["bg-critical", "Backend offline"]
        : health.data.status === "ok"
          ? ["bg-good", `Online · ${health.data.device.toUpperCase()}`]
          : ["bg-warning", "Degraded"];

  return (
    <Link
      to="/status"
      className="inline-flex items-center gap-2 rounded-full border border-line px-3 py-1 text-xs font-medium text-ink-2 hover:bg-surface-2"
      title="System status"
    >
      <span className={cx("size-2 rounded-full", dot, health.state === "loading" && "animate-pulse")} aria-hidden />
      {compact ? <span className="sr-only">{label}</span> : label}
    </Link>
  );
}

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight text-ink">
      <span className="grid size-8 place-items-center rounded-lg bg-accent text-accent-ink">
        <ShieldCheck className="size-4.5" aria-hidden />
      </span>
      ForgeGuard
    </Link>
  );
}

export default function Layout() {
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setOpen(false);
    window.scrollTo(0, 0);
  }, [location.pathname]);

  const navClass = ({ isActive }: { isActive: boolean }) =>
    cx(
      "rounded-lg px-3 py-2 text-sm font-medium transition-colors",
      isActive ? "bg-surface-2 text-ink" : "text-ink-2 hover:text-ink",
    );

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2"
      >
        Skip to content
      </a>

      <header className="sticky top-0 z-40 border-b border-line bg-bg/85 backdrop-blur-md no-print">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-6">
          <Logo />
          <nav className="hidden flex-1 items-center gap-1 md:flex" aria-label="Main">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} className={navClass}>
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2 md:ml-0">
            <span className="hidden sm:inline-flex">
              <StatusPill />
            </span>
            <span className="sm:hidden">
              <StatusPill compact />
            </span>
            <button
              onClick={toggle}
              className="grid size-9 place-items-center rounded-lg text-ink-2 hover:bg-surface-2 hover:text-ink"
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            >
              {theme === "dark" ? <Sun className="size-4.5" /> : <Moon className="size-4.5" />}
            </button>
            <button
              onClick={() => setOpen((o) => !o)}
              className="grid size-9 place-items-center rounded-lg text-ink-2 hover:bg-surface-2 md:hidden"
              aria-label="Menu"
              aria-expanded={open}
            >
              {open ? <X className="size-5" /> : <Menu className="size-5" />}
            </button>
          </div>
        </div>
        {open && (
          <nav className="border-t border-line px-4 py-3 md:hidden" aria-label="Mobile">
            <div className="flex flex-col gap-1">
              {NAV.map((n) => (
                <NavLink key={n.to} to={n.to} className={navClass}>
                  {n.label}
                </NavLink>
              ))}
            </div>
          </nav>
        )}
      </header>

      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-12">
        <Outlet />
      </main>

      <footer className="border-t border-line no-print">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-8 text-sm text-ink-3 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>ForgeGuard · AI media forensics. Results are probabilistic and should support, not replace, expert review.</p>
          <div className="flex gap-4">
            <Link to="/docs" className="hover:text-ink">API</Link>
            <Link to="/status" className="hover:text-ink">Status</Link>
            <a href="/legacy/" className="hover:text-ink">Classic UI</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
