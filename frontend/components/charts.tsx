"use client";

// Small, dependency-free SVG charts. Each single-series chart is named by its
// title (no legend box); every value is reachable by hover and by the text beside it.
import { useId, useState } from "react";
import { formatValue, signed } from "@/lib/format";
import type { Series } from "@/lib/types";

const W = 600;
const H = 180;
const PAD = { l: 8, r: 8, t: 12, b: 22 };

function shortDate(t: string): string {
  const d = new Date(`${t.slice(0, 10)}T00:00:00`);
  return Number.isNaN(d.getTime()) ? t : d.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
}

/** Area/line chart with a crosshair tooltip (e.g. weekly closing price). */
export function LineChart({ series, height = H }: { series: Series; height?: number }) {
  const gid = useId();
  const [hover, setHover] = useState<number | null>(null);
  const pts = series.points;
  const vals = pts.map((p) => p.v);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const x = (i: number) => PAD.l + (i / (pts.length - 1)) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - (v - min) / span) * (height - PAD.t - PAD.b);
  const line = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join("");
  const area = `${line}L${x(pts.length - 1)},${height - PAD.b}L${x(0)},${height - PAD.b}Z`;
  const change = vals[vals.length - 1] / vals[0] - 1;
  const h = hover !== null ? pts[hover] : null;

  function onMove(e: React.PointerEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const rel = ((e.clientX - rect.left) / rect.width) * W;
    const i = Math.round(((rel - PAD.l) / (W - PAD.l - PAD.r)) * (pts.length - 1));
    setHover(Math.max(0, Math.min(pts.length - 1, i)));
  }

  return (
    <figure>
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <figcaption className="text-xs font-medium uppercase tracking-wider text-zinc-500">{series.label}</figcaption>
        <div className="text-right text-sm">
          <span className="font-semibold text-zinc-100">{formatValue(h ? h.v : vals[vals.length - 1], series.format)}</span>{" "}
          <span className="text-xs text-zinc-500">{h ? shortDate(h.t) : `${change >= 0 ? "+" : ""}${(change * 100).toFixed(1)}% over period`}</span>
        </div>
      </div>
      <svg
        viewBox={`0 0 ${W} ${height}`}
        className="w-full touch-none select-none"
        role="img"
        aria-label={`${series.label}: from ${formatValue(vals[0], series.format)} to ${formatValue(vals[vals.length - 1], series.format)}`}
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id={gid} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--color-series-1)" stopOpacity="0.35" />
            <stop offset="100%" stopColor="var(--color-series-1)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <line x1={PAD.l} x2={W - PAD.r} y1={height - PAD.b} y2={height - PAD.b} stroke="rgb(255 255 255 / 0.08)" />
        <path d={area} fill={`url(#${gid})`} />
        <path d={line} fill="none" stroke="var(--color-series-1)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        <text x={PAD.l} y={height - 6} className="fill-zinc-500" fontSize="11">
          {shortDate(pts[0].t)}
        </text>
        <text x={W - PAD.r} y={height - 6} textAnchor="end" className="fill-zinc-500" fontSize="11">
          {shortDate(pts[pts.length - 1].t)}
        </text>
        {hover !== null && h && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={PAD.t} y2={height - PAD.b} stroke="rgb(255 255 255 / 0.3)" strokeDasharray="3 3" />
            <circle cx={x(hover)} cy={y(h.v)} r="5" fill="var(--color-series-1)" stroke="#07080d" strokeWidth="2" />
          </g>
        )}
      </svg>
    </figure>
  );
}

/** Vertical bars with a per-bar tooltip (e.g. quarterly revenue or EPS). */
export function BarChart({ series, height = 150, width = W }: { series: Series; height?: number; width?: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const pts = series.points;
  const max = Math.max(...pts.map((p) => Math.abs(p.v))) || 1;
  const gap = 6;
  const bw = Math.min(64, (width - PAD.l - PAD.r - gap * (pts.length - 1)) / pts.length);
  const offset = (width - PAD.l - PAD.r - (bw * pts.length + gap * (pts.length - 1))) / 2;
  const base = height - PAD.b;
  const h = hover !== null ? pts[hover] : pts[pts.length - 1];

  return (
    <figure>
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <figcaption className="text-xs font-medium uppercase tracking-wider text-zinc-500">{series.label}</figcaption>
        <div className="text-sm">
          <span className="font-semibold">{formatValue(h.v, series.format)}</span>{" "}
          <span className="text-xs text-zinc-500">{shortDate(h.t)}</span>
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label={series.label} onPointerLeave={() => setHover(null)}>
        <line x1={PAD.l} x2={width - PAD.r} y1={base} y2={base} stroke="rgb(255 255 255 / 0.12)" />
        {pts.map((p, i) => {
          const bh = Math.max(2, (Math.abs(p.v) / max) * (base - PAD.t));
          const bx = PAD.l + offset + i * (bw + gap);
          const neg = p.v < 0;
          return (
            <g key={p.t} onPointerEnter={() => setHover(i)}>
              <rect x={bx - gap / 2} y={PAD.t} width={bw + gap} height={base - PAD.t} fill="transparent" />
              <rect
                x={bx}
                y={neg ? base : base - bh}
                width={bw}
                height={bh}
                rx="4"
                fill={neg ? "#fb7185" : "var(--color-series-1)"}
                opacity={hover === null || hover === i ? 1 : 0.45}
              />
            </g>
          );
        })}
        {pts.map((p, i) => (
          <text key={p.t} x={PAD.l + offset + i * (bw + gap) + bw / 2} y={height - 6} textAnchor="middle" className="fill-zinc-500" fontSize="11">
            {shortDate(p.t)}
          </text>
        ))}
      </svg>
    </figure>
  );
}

/** How the 12 analysts split: bullish / neutral / bearish / no data, direct-labeled. */
export function VoteBar({ bull, neutral, bear, missing }: { bull: number; neutral: number; bear: number; missing: number }) {
  const total = bull + neutral + bear + missing || 1;
  const parts = [
    { label: "Bullish", n: bull, cls: "bg-emerald-400", dot: "bg-emerald-400" },
    { label: "Neutral", n: neutral, cls: "bg-zinc-400", dot: "bg-zinc-400" },
    { label: "Bearish", n: bear, cls: "bg-rose-400", dot: "bg-rose-400" },
    { label: "No data", n: missing, cls: "bg-zinc-700", dot: "bg-zinc-700" },
  ];
  return (
    <div>
      <div className="flex h-3 w-full gap-0.5 overflow-hidden rounded-full" role="img" aria-label={parts.map((p) => `${p.n} ${p.label}`).join(", ")}>
        {parts.filter((p) => p.n > 0).map((p) => (
          <div key={p.label} className={`${p.cls} first:rounded-l-full last:rounded-r-full`} style={{ width: `${(p.n / total) * 100}%` }} title={`${p.label}: ${p.n}`} />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-400">
        {parts.map((p) => (
          <span key={p.label} className="inline-flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${p.dot}`} />
            <span className="font-semibold text-zinc-200">{p.n}</span> {p.label}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Semicircle gauge for a -100..+100 score. */
export function ScoreGauge({ score, size = 160 }: { score: number; size?: number }) {
  const r = 70;
  const cx = 90;
  const cy = 86;
  const clamped = Math.max(-100, Math.min(100, score));
  const angle = Math.PI * (1 - (clamped + 100) / 200); // 180° (left, -100) .. 0° (right, +100)
  const point = (a: number) => [cx + r * Math.cos(a), cy - r * Math.sin(a)];
  const [ex, ey] = point(angle);
  const [mx, my] = point(Math.PI / 2);
  const color = clamped >= 20 ? "#34d399" : clamped <= -20 ? "#fb7185" : "#fcd34d";
  const sweep = clamped >= 0 ? 1 : 0;
  return (
    <svg viewBox="0 0 180 100" width={size} role="img" aria-label={`Council score ${signed(score)} out of ±100`}>
      <path d={`M${cx - r},${cy} A${r},${r} 0 0 1 ${cx + r},${cy}`} fill="none" stroke="rgb(255 255 255 / 0.1)" strokeWidth="12" strokeLinecap="round" />
      {Math.abs(clamped) > 0.5 && (
        <path d={`M${mx},${my} A${r},${r} 0 0 ${sweep} ${ex},${ey}`} fill="none" stroke={color} strokeWidth="12" strokeLinecap="round" />
      )}
      <line x1={cx} x2={cx} y1={cy - r - 8} y2={cy - r + 8} stroke="rgb(255 255 255 / 0.35)" strokeWidth="2" />
      <text x={cx} y={cy - 12} textAnchor="middle" fontSize="30" fontWeight="700" className="fill-zinc-50">
        {signed(score)}
      </text>
      <text x={cx - r} y={cy + 13} textAnchor="middle" fontSize="10" className="fill-zinc-500">
        −100
      </text>
      <text x={cx + r} y={cy + 13} textAnchor="middle" fontSize="10" className="fill-zinc-500">
        +100
      </text>
    </svg>
  );
}

/** Thin 0-100 meter (conviction, confidence). */
export function Meter({ value, tone = "brand" }: { value: number; tone?: "brand" | "bull" | "bear" | "neutral" }) {
  const cls = { brand: "bg-brand-400", bull: "bg-emerald-400", bear: "bg-rose-400", neutral: "bg-zinc-400" }[tone];
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10" role="meter" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
      <div className={`h-full rounded-full ${cls}`} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}
