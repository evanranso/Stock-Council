import type { Metadata } from "next";
import Link from "next/link";
import HeaderSearch from "@/components/HeaderSearch";
import "./globals.css";

export const metadata: Metadata = {
  title: "Stock Council",
  description: "Twelve independent AI analysts, one debate, one verdict.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="sticky top-0 z-30 border-b border-white/10 bg-[#07080d]/80 backdrop-blur-md">
          <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
            <Link href="/" className="flex shrink-0 items-center gap-2 font-semibold tracking-tight">
              <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-brand-500 to-accent-500 text-sm shadow-lg shadow-brand-500/30">
                ⚖️
              </span>
              <span className="hidden sm:inline">Stock Council</span>
            </Link>
            <HeaderSearch />
            <nav className="ml-auto flex items-center gap-1 text-sm">
              <Link href="/" className="rounded-lg px-3 py-1.5 text-zinc-300 hover:bg-white/5 hover:text-white">
                Analyze
              </Link>
              <Link href="/history" className="rounded-lg px-3 py-1.5 text-zinc-300 hover:bg-white/5 hover:text-white">
                History
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 pb-10 text-xs text-zinc-600">
          AI-generated research from public data. Not investment advice. Data can be delayed or incomplete.
        </footer>
      </body>
    </html>
  );
}
