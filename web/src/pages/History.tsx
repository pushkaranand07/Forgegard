import { useMemo, useState } from "react";
import { FileSpreadsheet, History as HistoryIcon, Search, Trash2 } from "lucide-react";
import HistoryRow from "../components/HistoryRow";
import { Button, ButtonLink, Card, EmptyState, PageHeader, cx } from "../components/ui";
import { downloadCsv } from "../lib/download";
import { history, useHistory } from "../lib/history";
import type { Verdict } from "../lib/types";

const FILTERS: { value: Verdict | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "manipulated", label: "Manipulated" },
  { value: "authentic", label: "Authentic" },
  { value: "inconclusive", label: "Inconclusive" },
];

export default function History() {
  const items = useHistory();
  const [query, setQuery] = useState("");
  const [verdict, setVerdict] = useState<Verdict | "all">("all");
  const [type, setType] = useState<"all" | "image" | "video">("all");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter(
      (a) =>
        (verdict === "all" || a.verdict === verdict) &&
        (type === "all" || a.mediaType === type) &&
        (!q || a.fileName.toLowerCase().includes(q)),
    );
  }, [items, query, verdict, type]);

  return (
    <>
      <PageHeader
        title="History"
        description="Analyses you've run in this browser. History is stored locally and is not shared with anyone."
        actions={
          items.length > 0 && (
            <>
              <Button variant="secondary" onClick={() => downloadCsv(filtered)}>
                <FileSpreadsheet className="size-4" /> Export CSV
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  if (confirm(`Delete all ${items.length} saved analyses? This cannot be undone.`)) history.clear();
                }}
              >
                <Trash2 className="size-4" /> Clear all
              </Button>
            </>
          )
        }
      />

      {items.length === 0 ? (
        <EmptyState
          icon={<HistoryIcon className="size-6" />}
          title="No analyses yet"
          action={<ButtonLink to="/analyze">Analyze a file</ButtonLink>}
        >
          Every image and video you analyze is saved here so you can reopen or print its report later.
        </EmptyState>
      ) : (
        <>
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            <label className="relative flex-1">
              <span className="sr-only">Search by file name</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-3" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by file name"
                className="h-10 w-full rounded-lg border border-line-strong bg-surface pl-9 pr-3 text-sm text-ink placeholder:text-ink-3 focus:border-accent focus:outline-none"
              />
            </label>
            <div className="flex gap-1 overflow-x-auto rounded-lg border border-line bg-surface p-1" role="group" aria-label="Filter by verdict">
              {FILTERS.map((f) => (
                <button
                  key={f.value}
                  onClick={() => setVerdict(f.value)}
                  aria-pressed={verdict === f.value}
                  className={cx(
                    "whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium",
                    verdict === f.value ? "bg-surface-2 text-ink" : "text-ink-2 hover:text-ink",
                  )}
                >
                  {f.label}
                </button>
              ))}
            </div>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as typeof type)}
              aria-label="Filter by media type"
              className="h-10 rounded-lg border border-line-strong bg-surface px-3 text-sm text-ink"
            >
              <option value="all">All media</option>
              <option value="image">Images</option>
              <option value="video">Videos</option>
            </select>
          </div>

          {filtered.length === 0 ? (
            <Card className="p-10 text-center text-sm text-ink-2">No analyses match these filters.</Card>
          ) : (
            <Card className="divide-y divide-line">
              {filtered.map((a) => (
                <HistoryRow
                  key={a.id}
                  analysis={a}
                  trailing={
                    <button
                      onClick={() => history.remove(a.id)}
                      className="grid size-8 shrink-0 place-items-center rounded-md text-ink-3 hover:bg-critical-soft hover:text-critical-ink"
                      aria-label={`Delete ${a.fileName}`}
                    >
                      <Trash2 className="size-4" />
                    </button>
                  }
                />
              ))}
            </Card>
          )}
          <p className="mt-3 text-xs text-ink-3">
            Showing {filtered.length} of {items.length}. The most recent 60 analyses are kept.
          </p>
        </>
      )}
    </>
  );
}
