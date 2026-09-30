"use client";

import RecentList from "@/components/RecentList";
import { useAuth } from "@/lib/auth";

export default function HistoryPage() {
  const { session } = useAuth();
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">History</h1>
        <p className="mt-1 text-sm text-zinc-400">
          {session
            ? "Every analysis you've run or opened, saved to your account. Open one to see the full report exactly as it was."
            : "Every analysis you've run, saved in this browser. Log in to keep them in your account instead."}
        </p>
      </div>
      <RecentList manage />
    </div>
  );
}
