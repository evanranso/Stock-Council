"use client";

import { usePathname } from "next/navigation";
import TickerSearch from "./TickerSearch";

// Compact search in the header on every page except home (which has the big one).
export default function HeaderSearch() {
  const path = usePathname();
  if (path === "/") return <div className="flex-1" />;
  return (
    <div className="max-w-sm flex-1">
      <TickerSearch size="sm" />
    </div>
  );
}
