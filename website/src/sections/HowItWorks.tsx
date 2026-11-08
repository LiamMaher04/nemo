import { Reveal } from "@/components/Reveal";
import { SectionLabel } from "@/components/SectionLabel";
import Image from "next/image";

const steps = [
  {
    art: "notice",
    title: "Nemo quietly notices",
    body: "Wear Nemo as you go about your day. Nemo notices where everyday things get put down. Nothing to tag, nothing to set up on each item.",
  },
  {
    art: "ask",
    title: "You hold the button and ask",
    body: "Can’t find something? Hold the one button and ask the way you’d ask a friend: “Where are my glasses?”",
  },
  {
    art: "tell",
    title: "Nemo tells you where",
    body: "Nemo answers out loud with the place and the time: “Your glasses are on the bookshelf in the living room. I saw them there about 20 minutes ago.”",
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
            <p className="text-xl">Three steps and one button. No menus to learn, nothing to set up each day.</p>
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
              <Image src={`/illustrations/${s.art}.svg`} alt="" width={480} height={360} unoptimized className="h-auto w-full" />
              <div className="mt-8 flex items-baseline gap-4">
                <span className="font-heading text-5xl font-semibold leading-none text-navy" aria-hidden="true">
                  {i + 1}
                </span>
                <h3 className="text-2xl">
                  <span className="sr-only">Step {i + 1}: </span>
                  {s.title}
                </h3>
              </div>
              <p className="mt-3">{s.body}</p>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  );
}
