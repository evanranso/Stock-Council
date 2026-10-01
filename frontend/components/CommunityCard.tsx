import Link from "next/link";
import { type CommunityItem, communityHref } from "@/lib/community";
import { DEPTH_ICON } from "@/lib/depth";
import { RATING_LABEL, RATING_STYLE, signed, timeAgo } from "@/lib/format";
import { HORIZON_TAB, type Horizon } from "@/lib/horizon";

/** One analysis from the community library. */
export default function CommunityCard({ item, horizon, wide = false }: { item: CommunityItem; horizon: Horizon; wide?: boolean }) {
  return (
    <Link href={communityHref(item)} className="card flex items-center gap-4 p-4 transition hover:border-brand-400/40 hover:bg-white/[0.05]">
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-lg font-bold">{item.ticker}</span>
          <span className="truncate text-sm text-zinc-400">{item.name}</span>
        </div>
        {wide && item.bottom_line && <p className="mt-1 line-clamp-1 text-sm text-zinc-300">{item.bottom_line}</p>}
        <p className="mt-1 text-xs text-zinc-500">
          {timeAgo(new Date(item.created * 1000).toISOString())}
          {item.depth && (
            <>
              {" "}
              · {DEPTH_ICON[item.depth]} {item.depth}
            </>
          )}
          {item.confidence !== null && <> · confidence {item.confidence}</>}
        </p>
      </div>
      <div className="shrink-0 text-right">
        <span className={`rounded-lg px-2.5 py-1 text-xs font-bold ${RATING_STYLE[item.rating]}`}>{RATING_LABEL[item.rating]}</span>
        <div className="mt-1 text-xs tabular-nums text-zinc-500">
          {HORIZON_TAB[horizon].toLowerCase()} {signed(item.score)}
        </div>
      </div>
    </Link>
  );
}
