import type { Metadata } from "next";
import { Contact, LegalPage, List, Section } from "@/components/LegalPage";

export const metadata: Metadata = { title: "Privacy Policy · Stock Council" };

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy Policy"
      intro={
        <p>
          This policy explains what Stock Council collects, why, who helps us process it, and the choices you have. We collect only what we need
          to run the service. We don&apos;t sell your personal information, show ads, or use advertising or analytics trackers.
        </p>
      }
    >
      <Section n={1} title="What we collect">
        <List>
          <li>
            <span className="text-white">Account:</span> your email address and a password. Passwords are handled by our sign-in provider and
            stored only in hashed form; we never see them.
          </li>
          <li>
            <span className="text-white">Credits and activity:</span> your credit balance, the stocks you analyze, the depth you choose, when
            you run them, and the reports saved to your history.
          </li>
          <li>
            <span className="text-white">Payments:</span> your plan, its status and renewal date, your Stripe customer ID, and the amount, date,
            and credits of each purchase. Card details are collected and stored by Stripe, never by us.
          </li>
          <li>
            <span className="text-white">Technical:</span> your IP address is used briefly to limit abuse (for example, how many analyses can
            start per hour) and may appear in our hosting providers&apos; server logs. Sign-up and log-in include a bot check that processes
            basic device and browser signals.
          </li>
          <li>
            <span className="text-white">On your device:</span> your browser stores your sign-in session, your preferred analysis depth, and
            (if you aren&apos;t signed in) reports you&apos;ve viewed. These stay in your browser; reports stored there move into your account
            the first time you sign in.
          </li>
        </List>
      </Section>

      <Section n={2} title="How we use it">
        <List>
          <li>To create and secure your account, verify your email, and sign you in.</li>
          <li>To run analyses, keep track of credits, and save your reports.</li>
          <li>To process payments and subscriptions, and keep the records tax and accounting rules require.</li>
          <li>To prevent abuse, fraud, and runaway costs, and to fix problems.</li>
          <li>To send emails you need, such as verification and password resets. We don&apos;t send marketing emails without your consent.</li>
        </List>
      </Section>

      <Section n={3} title="Who processes it for us">
        <p>We use these service providers, each only for its part of running Stock Council:</p>
        <List>
          <li>
            <span className="text-white">Supabase</span>: sign-in, email verification, and our database (accounts, credits, saved reports).
          </li>
          <li>
            <span className="text-white">Stripe</span>: payments, subscriptions, invoices, and sales tax. Stripe may act as the seller of record
            for purchases; its own privacy policy covers the payment information it collects.
          </li>
          <li>
            <span className="text-white">Cloudflare</span>: hosting the website and the bot check on sign-up and log-in.
          </li>
          <li>
            <span className="text-white">Render</span>: hosting the server that runs analyses.
          </li>
          <li>
            <span className="text-white">Anthropic</span>: the AI models that write the analyses. They receive the stock ticker and public
            market data only, not your name, email, or account details.
          </li>
        </List>
        <p>
          These providers may store or process data outside your province or country, including in the United States, where it may be accessible
          to authorities under local law. We don&apos;t sell or rent personal information to anyone.
        </p>
      </Section>

      <Section n={4} title="What other users can see">
        <p>
          Reports are about public companies, not about you, and a report generated for a stock may be shown to other users who open that stock
          shortly afterward. Reports never show who ran them. Your account, email, credits, purchases, and history list are private.
        </p>
      </Section>

      <Section n={5} title="How long we keep it">
        <List>
          <li>Account data and saved reports: while your account is open. You can delete saved reports from your History at any time.</li>
          <li>
            Payment and purchase records: as long as tax and accounting laws require (in Canada, generally six years), even after an account is
            closed.
          </li>
          <li>Server logs: kept by our hosting providers for a limited time for security and troubleshooting.</li>
        </List>
      </Section>

      <Section n={6} title="Your choices and rights">
        <p>
          You can ask to see the personal information we hold about you, correct it, or delete your account. Deleting your account removes your
          email, credits, and saved history, except records we must keep by law. Cancel any subscription before deleting your account. You can
          also withdraw consent to optional processing at any time. If you&apos;re not satisfied with our response, you can complain to the privacy
          regulator where you live (in Canada, the Office of the Privacy Commissioner of Canada).
        </p>
        <p>
          To make a request: <Contact />. We&apos;ll respond within 30 days.
        </p>
      </Section>

      <Section n={7} title="Security">
        <p>
          We use encrypted connections, hashed passwords, verified sign-in tokens checked on every request, and access limited to what each part
          of the service needs. No system is perfectly secure; if a breach affecting your information creates a real risk of harm, we&apos;ll notify
          you and the relevant authorities as the law requires.
        </p>
      </Section>

      <Section n={8} title="Children">
        <p>Stock Council is not for anyone under 18, and we don&apos;t knowingly collect information from children.</p>
      </Section>

      <Section n={9} title="Changes to this policy">
        <p>If we change this policy in a meaningful way, we&apos;ll update the date above and, for significant changes, let account holders know.</p>
      </Section>
    </LegalPage>
  );
}
