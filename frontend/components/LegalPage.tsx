import Link from "next/link";
import { CONTACT_EMAIL, LEGAL_UPDATED } from "@/lib/site";

/** Shared layout for the Terms and Privacy pages: readable width, numbered sections, contact line. */
export function LegalPage({ title, intro, children }: { title: string; intro: React.ReactNode; children: React.ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl space-y-8 pb-8 pt-4 leading-relaxed text-zinc-300">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight text-white">{title}</h1>
        <p className="text-sm text-zinc-500">Last updated {LEGAL_UPDATED}</p>
        <div className="text-zinc-300">{intro}</div>
      </header>
      {children}
      <footer className="border-t border-white/10 pt-6 text-sm text-zinc-500">
        Questions? <Contact />. See also the{" "}
        <Link href="/terms" className="text-brand-300 hover:underline">
          Terms of Service
        </Link>{" "}
        and{" "}
        <Link href="/privacy" className="text-brand-300 hover:underline">
          Privacy Policy
        </Link>
        .
      </footer>
    </article>
  );
}

export function Section({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold text-white">
        {n}. {title}
      </h2>
      {children}
    </section>
  );
}

export function List({ children }: { children: React.ReactNode }) {
  return <ul className="list-disc space-y-1.5 pl-5">{children}</ul>;
}

/** "Email us at x" when a contact address is configured; otherwise the in-app route. */
export function Contact() {
  return CONTACT_EMAIL ? (
    <>
      Email us at{" "}
      <a href={`mailto:${CONTACT_EMAIL}`} className="text-brand-300 hover:underline">
        {CONTACT_EMAIL}
      </a>
    </>
  ) : (
    <>Reply to any email you've received from Stock Council, or reach us through the support link on your Stripe receipt</>
  );
}
