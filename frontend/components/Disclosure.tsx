"use client";

import { useState } from "react";

// "Show the full breakdown" toggle: summary stays visible, detail expands below.
export default function Disclosure({
  label = "Full breakdown",
  openLabel = "Hide breakdown",
  children,
  defaultOpen = false,
}: {
  label?: string;
  openLabel?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs font-medium text-zinc-300 hover:border-white/20 hover:text-white"
      >
        <svg aria-hidden viewBox="0 0 20 20" className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} fill="currentColor">
          <path fillRule="evenodd" d="M5.2 7.2a.75.75 0 0 1 1.06 0L10 10.94l3.74-3.74a.75.75 0 1 1 1.06 1.06l-4.27 4.27a.75.75 0 0 1-1.06 0L5.2 8.26a.75.75 0 0 1 0-1.06Z" />
        </svg>
        {open ? openLabel : label}
      </button>
      {open && <div className="fade-up mt-3">{children}</div>}
    </div>
  );
}
