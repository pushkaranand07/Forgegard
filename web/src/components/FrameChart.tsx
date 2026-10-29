import { useEffect, useRef, useState } from "react";
import { formatPct } from "../lib/format";

interface Props {
  /** Per-face fake probability, 0–1, in sampling order */
  values: number[];
  threshold?: number;
}

const HEIGHT = 200;
const PAD = { top: 12, right: 8, bottom: 26, left: 40 };

function barPath(x: number, y: number, w: number, h: number) {
  const r = Math.min(4, w / 2, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

export default function FrameChart({ values, threshold = 0.5 }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [hover, setHover] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(280, e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const n = values.length;
  const plotW = width - PAD.left - PAD.right;
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const step = plotW / n;
  const gap = n > 1 ? Math.min(2, step * 0.25) : 0;
  const barW = Math.max(1, step - gap);
  const y = (v: number) => PAD.top + plotH * (1 - v);
  const thresholdY = y(threshold);
  const labelEvery = Math.ceil(n / Math.max(1, Math.floor(plotW / 36)));

  const flagged = values.filter((v) => v > threshold).length;
  const mean = values.reduce((s, v) => s + v, 0) / n;
  const max = Math.max(...values);

  const tip = hover !== null ? values[hover] : null;
  const tipX = hover !== null ? PAD.left + hover * step + step / 2 : 0;

  return (
    <div>
      <dl className="mb-4 grid grid-cols-3 gap-4 text-sm">
        <div>
          <dt className="text-xs text-ink-3">Mean fake probability</dt>
          <dd className="font-semibold text-ink tabular">{formatPct(mean)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-3">Highest</dt>
          <dd className="font-semibold text-ink tabular">{formatPct(max)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-3">Above threshold</dt>
          <dd className="font-semibold text-ink tabular">
            {flagged} / {n}
          </dd>
        </div>
      </dl>

      <div ref={wrap} className="relative">
        <svg
          width={width}
          height={HEIGHT}
          role="img"
          aria-label={`Fake probability for ${n} face crops. ${flagged} of ${n} are above the ${formatPct(threshold, 0)} threshold.`}
          className="block max-w-full"
          onMouseLeave={() => setHover(null)}
        >
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} stroke="var(--chart-grid)" strokeWidth={1} />
              <text x={PAD.left - 8} y={y(t)} dy="0.32em" textAnchor="end" fontSize={11} fill="var(--text-3)" className="tabular">
                {t * 100}%
              </text>
            </g>
          ))}

          {values.map((v, i) => {
            const h = Math.max(1.5, plotH * v);
            const x = PAD.left + i * step + gap / 2;
            return (
              <path
                key={i}
                d={barPath(x, PAD.top + plotH - h, barW, h)}
                fill="var(--chart-series)"
                opacity={hover === null || hover === i ? 1 : 0.4}
              />
            );
          })}

          {/* Threshold drawn above bars so it stays legible */}
          <line
            x1={PAD.left}
            x2={width - PAD.right}
            y1={thresholdY}
            y2={thresholdY}
            stroke="var(--text-2)"
            strokeWidth={1.5}
            strokeDasharray="4 4"
          />
          <text x={width - PAD.right} y={thresholdY - 6} textAnchor="end" fontSize={11} fill="var(--text-2)" fontWeight={500}>
            Decision threshold
          </text>

          {values.map((_, i) =>
            i % labelEvery === 0 ? (
              <text
                key={i}
                x={PAD.left + i * step + step / 2}
                y={HEIGHT - 8}
                textAnchor="middle"
                fontSize={11}
                fill="var(--text-3)"
                className="tabular"
              >
                {i + 1}
              </text>
            ) : null,
          )}

          {/* Full-height hit targets, wider than the marks */}
          {values.map((_, i) => (
            <rect
              key={i}
              x={PAD.left + i * step}
              y={PAD.top}
              width={step}
              height={plotH}
              fill="transparent"
              onMouseEnter={() => setHover(i)}
            />
          ))}
        </svg>

        {tip !== null && hover !== null && (
          <div
            className="pointer-events-none absolute z-10 -translate-x-1/2 rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-card"
            style={{
              left: Math.min(Math.max(tipX, 70), width - 70),
              top: Math.max(0, y(tip) - 58),
            }}
          >
            <p className="text-ink-3">Face crop {hover + 1}</p>
            <p className="font-semibold text-ink tabular">{formatPct(tip)} fake</p>
          </div>
        )}
      </div>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-ink-3">
        <span>Each bar is one face crop from the sampled frames, in time order.</span>
        <button className="font-medium text-accent hover:underline no-print" onClick={() => setShowTable((s) => !s)}>
          {showTable ? "Hide table" : "Show as table"}
        </button>
      </div>

      {showTable && (
        <div className="mt-3 max-h-64 overflow-auto rounded-lg border border-line">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-surface-2 text-left text-xs text-ink-3">
              <tr>
                <th className="px-3 py-2 font-medium">Face crop</th>
                <th className="px-3 py-2 text-right font-medium">Fake probability</th>
                <th className="px-3 py-2 text-right font-medium">Assessment</th>
              </tr>
            </thead>
            <tbody className="tabular">
              {values.map((v, i) => (
                <tr key={i} className="border-t border-line">
                  <td className="px-3 py-1.5 text-ink-2">{i + 1}</td>
                  <td className="px-3 py-1.5 text-right text-ink">{formatPct(v, 2)}</td>
                  <td className="px-3 py-1.5 text-right text-ink-2">{v > threshold ? "Fake" : "Real"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
