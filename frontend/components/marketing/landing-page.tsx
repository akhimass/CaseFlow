import Link from 'next/link';
import { BackedBy } from '@/components/marketing/backed-by';
import { ClientIntakePreview, FirmDashboardPreview } from '@/components/marketing/landing-previews';
import { MarketingLayout } from '@/components/marketing/marketing-layout';
import { Button } from '@/components/ui/button';
import { CONSUMER_TAGLINE, START_CASE_CTA } from '@/lib/consumer-copy';
import { CTA_NOTE, FEATURES, STATS } from '@/lib/marketing';

export function LandingPage() {
  return (
    <MarketingLayout>
      <section className="mx-auto max-w-7xl px-6 pt-8 pb-6 md:pt-10">
        <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] lg:gap-8 xl:grid-cols-[minmax(0,26rem)_minmax(0,1fr)] xl:gap-10">
          <div className="text-center lg:text-left">
            <div className="border-border bg-muted/50 text-muted-foreground mb-4 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm">
              <span className="size-2 rounded-full bg-emerald-500" />
              Spanish + English · Free video case review
            </div>
            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl lg:text-6xl">
              Start your case today.
            </h1>
            <p className="text-muted-foreground mt-4 text-lg md:text-xl">{CONSUMER_TAGLINE}</p>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3 lg:justify-start">
              <Button asChild size="lg">
                <Link href="/intake/consent">{START_CASE_CTA}</Link>
              </Button>
              <Button asChild variant="outline" size="lg">
                <Link href="/firm/login">For Law Firms</Link>
              </Button>
            </div>

            <BackedBy align="start" className="border-border mt-8 border-t pt-8 lg:mt-10" />
          </div>

          <div className="flex w-full min-w-0 flex-col gap-5">
            <ClientIntakePreview />
            <FirmDashboardPreview />
          </div>
        </div>
      </section>

      <section className="border-border bg-muted/20 border-y">
        <div className="mx-auto grid max-w-6xl gap-6 px-6 py-8 sm:grid-cols-2 lg:grid-cols-4">
          {STATS.map(({ value, label }) => (
            <div key={label}>
              <div className="text-3xl font-bold tracking-tight md:text-4xl">{value}</div>
              <p className="text-muted-foreground mt-2 text-sm">{label}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-12">
        <div>
          <p className="text-primary text-sm font-semibold tracking-widest uppercase">Features</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight md:text-4xl">
            Built for people hurt in accidents — not voicemail.
          </h2>
        </div>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.slice(0, 3).map(({ icon: Icon, title, body }) => (
            <div key={title} className="border-border bg-card rounded-xl border p-6">
              <div className="bg-primary text-primary-foreground mb-4 inline-flex size-10 items-center justify-center rounded-lg">
                <Icon className="size-5" strokeWidth={2} />
              </div>
              <h3 className="text-lg font-semibold">{title}</h3>
              <p className="text-muted-foreground mt-2 text-sm leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-border bg-muted/20 border-y px-6 py-10">
        <blockquote className="mx-auto max-w-3xl text-center">
          <p className="text-xl leading-relaxed font-medium md:text-2xl">
            &ldquo;Caseflow caught the fault discrepancy live — in Spanish — parsed Maria&rsquo;s
            police report and ER discharge, and matched her to Martinez &amp; Associates before she
            hung up.&rdquo;
          </p>
          <footer className="text-muted-foreground mt-6 text-sm">
            <strong className="text-foreground">Maria Delgado demo</strong> · Orange County rear-end
            · YC Conversational AI Hackathon
          </footer>
        </blockquote>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-12">
        <div className="border-border bg-card rounded-2xl border px-6 py-10 text-center shadow-sm md:px-12">
          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
            Stop losing PI cases to voicemail.
          </h2>
          <p className="text-muted-foreground mx-auto mt-4 max-w-xl">{CTA_NOTE}</p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Button asChild size="lg">
              <Link href="/intake/consent">{START_CASE_CTA}</Link>
            </Button>
            <Button asChild variant="outline" size="lg">
              <Link href="/firm/login">For Law Firms</Link>
            </Button>
          </div>
        </div>
      </section>
    </MarketingLayout>
  );
}
