import { formatProb } from "../lib/format";

interface Props {
  authentic: number;
  manipulated: number;
  authenticLabel: string;
  manipulatedLabel: string;
}

/** Two-class probability split. Labels are text-coloured; the swatches carry identity. */
export default function ProbabilityBar({ authentic, manipulated, authenticLabel, manipulatedLabel }: Props) {
  const total = authentic + manipulated || 1;
  const a = authentic / total;
  const m = manipulated / total;

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between gap-4 text-sm">
        <span className="flex items-center gap-2 text-ink-2">
          <span className="size-2.5 rounded-sm bg-good" aria-hidden />
          {authenticLabel}
          <span className="font-semibold text-ink tabular">{formatProb(a)}</span>
        </span>
        <span className="flex items-center gap-2 text-ink-2">
          <span className="font-semibold text-ink tabular">{formatProb(m)}</span>
          {manipulatedLabel}
          <span className="size-2.5 rounded-sm bg-critical" aria-hidden />
        </span>
      </div>
      <div
        className="flex h-3 gap-0.5 overflow-hidden rounded-full bg-surface-2"
        role="img"
        aria-label={`${authenticLabel} ${formatProb(a)}, ${manipulatedLabel} ${formatProb(m)}`}
      >
        {a > 0 && <div className="h-full rounded-l-full bg-good" style={{ width: `${a * 100}%`, minWidth: 4 }} />}
        {m > 0 && <div className="h-full rounded-r-full bg-critical" style={{ width: `${m * 100}%`, minWidth: 4 }} />}
      </div>
    </div>
  );
}
