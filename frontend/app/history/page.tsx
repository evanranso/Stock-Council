import RecentList from "@/components/RecentList";

export default function HistoryPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">History</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Every analysis you&apos;ve run, saved in this browser. Open one to see the full report exactly as it was.
        </p>
      </div>
      <RecentList manage />
    </div>
  );
}
