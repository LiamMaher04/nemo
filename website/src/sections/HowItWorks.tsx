import { Reveal } from "@/components/Reveal";
import { SectionLabel } from "@/components/SectionLabel";
import { colors } from "@/theme/tokens";

const stroke = { fill: "none", stroke: colors.navy, strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

/** Small bespoke drawings for each step. Decorative. */
const art = [
  // 1: keys set down on a table, quietly noticed
  <svg key="1" viewBox="0 0 120 80" className="h-20 w-auto" aria-hidden="true">
    <path d="M8 62h104" {...stroke} />
    <circle cx="48" cy="50" r="7" {...stroke} />
    <path d="M54 54l16 6M64 58l2-5" {...stroke} />
    <circle cx="56" cy="52" r="24" fill="none" stroke={colors.aqua} strokeWidth="2" strokeDasharray="4 6" />
  </svg>,
  // 2: one button, a question out loud
  <svg key="2" viewBox="0 0 120 80" className="h-20 w-auto" aria-hidden="true">
    <rect x="30" y="8" width="44" height="66" rx="14" {...stroke} />
    <circle cx="52" cy="46" r="11" fill={colors.navy} />
    <path d="M86 34c5 4 5 12 0 16M95 27c9 8 9 22 0 30" fill="none" stroke={colors.aqua} strokeWidth="2" strokeLinecap="round" />
  </svg>,
  // 3: the answer, with a photo of the spot
  <svg key="3" viewBox="0 0 120 80" className="h-20 w-auto" aria-hidden="true">
    <rect x="18" y="12" width="70" height="50" rx="6" {...stroke} />
    <path d="M18 48h70" {...stroke} />
    <circle cx="52" cy="40" r="5" {...stroke} />
    <circle cx="52" cy="40" r="15" fill="none" stroke={colors.coral} strokeWidth="2.5" strokeDasharray="4 5" />
    <path d="M94 22h16M94 32h12" fill="none" stroke={colors.aqua} strokeWidth="2" strokeLinecap="round" />
  </svg>,
];

const steps = [
  {
    title: "Nemo quietly notices",
    body: "Wear the clip as you go about your day. Nemo notices where everyday things get put down. Nothing to tag, nothing to set up on each item.",
  },
  {
    title: "You press and ask",
    body: "Can’t find something? Press the one button and ask the way you’d ask a friend: “Where are my glasses?”",
  },
  {
    title: "Nemo tells you where",
    body: "Nemo answers out loud, “I last saw your glasses on the bookshelf,” and can show you a photo of the spot.",
  },
];

export function HowItWorks() {
  return (
    <section aria-labelledby="how-title" className="section" id="how-it-works">
      <div className="container-page">
        <SectionLabel index="02">How it works</SectionLabel>
        <div className="mt-14 grid gap-6 lg:grid-cols-12">
          <Reveal className="lg:col-span-6">
            <h2 id="how-title" className="display">
              Finding, found.
            </h2>
          </Reveal>
          <Reveal delay={0.08} className="lg:col-span-5 lg:col-start-8 lg:pt-3">
            <p className="text-xl">Three steps and one button. No menus to learn and no screen to read.</p>
          </Reveal>
        </div>

        <ol className="mt-20 grid md:grid-cols-3">
          {steps.map((s, i) => (
            <Reveal
              as="li"
              key={s.title}
              delay={i * 0.1}
              className={`border-navy/15 py-10 md:py-0 ${i > 0 ? "border-t md:border-l md:border-t-0 md:pl-10" : ""} ${i < 2 ? "md:pr-10" : ""}`}
            >
              <div className="flex items-start justify-between">
                <span className="font-heading text-6xl font-semibold leading-none text-navy" aria-hidden="true">
                  {i + 1}
                </span>
                {art[i]}
              </div>
              <h3 className="mt-10 text-2xl">
                <span className="sr-only">Step {i + 1}: </span>
                {s.title}
              </h3>
              <p className="mt-3">{s.body}</p>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  );
}
