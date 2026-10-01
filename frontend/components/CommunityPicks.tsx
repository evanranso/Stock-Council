"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { type CommunityItem, fetchCommunity } from "@/lib/community";
import { useHorizon } from "@/lib/horizon";
import CommunityCard from "./CommunityCard";

/** Home page: the newest analyses from everyone, with a way into the full library. */
export default function CommunityPicks() {
  const [horizon] = useHorizon();
  const [items, setItems] = useState<CommunityItem[] | null>(null);
  useEffect(() => {
    fetchCommunity({ days: "7", rating: "all", horizon, depth: "all", sort: "newest", q: "" }, 0, 6).then((r) => setItems(r?.items ?? []));
  }, [horizon]);
  if (items !== null && !items.length) return null;

  return (
    <section>
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">What the community is analyzing</h2>
          <p className="text-sm text-zinc-500">The latest analyses from everyone on Stock Council. Opening one is free.</p>
        </div>
        <Link href="/community" className="rounded-lg border border-white/10 px-3 py-1.5 text-sm text-brand-200 hover:border-brand-400/50 hover:text-white">
          Browse all analyses →
        </Link>
      </div>
      {items === null ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="card h-20 animate-pulse" />
          ))}
        </div>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((it) => (
            <li key={it.id}>
              <CommunityCard item={it} horizon={horizon} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
