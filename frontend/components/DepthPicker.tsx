"use client";

import { DEPTH_ICON, DEPTH_TIME, type DepthId, type DepthOption, modelName } from "@/lib/depth";

/** Quick / Standard / Deep cards. Shows credit prices when credits apply and marks tiers that are free right now. */
export default function DepthPicker({
  options,
  value,
  onChange,
  showCredits,
  remaining,
  freeDepths = [],
}: {
  options: DepthOption[];
  value: DepthId;
  onChange: (d: DepthId) => void;
  showCredits: boolean;
  remaining?: number;
  freeDepths?: DepthId[];
}) {
  return (
    <div role="radiogroup" aria-label="Analysis depth" className="grid gap-2 sm:grid-cols-3">
      {options.map((o) => {
        const selected = o.id === value;
        const free = freeDepths.includes(o.id);
        const affordable = !showCredits || free || remaining === undefined || remaining >= o.credits;
        return (
          <button
            key={o.id}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={!affordable}
            onClick={() => onChange(o.id)}
            className={`relative flex flex-col rounded-xl border p-4 text-left transition ${
              selected ? "border-brand-400/70 bg-brand-500/10 ring-4 ring-brand-500/15" : "border-white/10 bg-white/[0.02] hover:border-white/25"
            } ${affordable ? "" : "cursor-not-allowed opacity-40"}`}
          >
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 font-semibold">
                <span aria-hidden>{DEPTH_ICON[o.id]}</span>
                {o.label}
              </span>
              {free ? (
                <span className="rounded-full bg-emerald-400/15 px-2 py-0.5 text-[11px] font-medium text-emerald-300">free now</span>
              ) : (
                showCredits && (
                  <span className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-zinc-300">
                    {o.credits} {o.credits === 1 ? "credit" : "credits"}
                  </span>
                )
              )}
            </div>
            <p className="mt-2 text-xs text-zinc-400">{o.blurb}</p>
            <p className="mt-auto pt-3 text-[11px] text-zinc-500">
              {DEPTH_TIME[o.id]}
              {o.analyst_model && o.debate_model && (
                <>
                  {" "}
                  · {modelName(o.analyst_model) === modelName(o.debate_model) ? modelName(o.analyst_model) : `${modelName(o.analyst_model)} + ${modelName(o.debate_model)}`}
                </>
              )}
            </p>
            {!affordable && <p className="mt-1 text-[11px] text-rose-300">Not enough credits</p>}
          </button>
        );
      })}
    </div>
  );
}
