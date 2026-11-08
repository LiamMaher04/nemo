import { AskNemoDemo } from "@/components/AskNemoDemo";
import { Reveal } from "@/components/Reveal";
import { SectionLabel } from "@/components/SectionLabel";

export function Demo() {
  return (
    <section aria-labelledby="demo-title" className="section bg-navy/[0.05]" id="demo">
      <div className="container-page">
        <SectionLabel index="08">See it in action</SectionLabel>
        <div className="mt-14 grid gap-14 lg:grid-cols-12 lg:gap-10">
          <Reveal className="lg:col-span-5">
            <h2 id="demo-title" className="display">
              Where did I put&hellip;? Ask Nemo.
            </h2>
            <div className="mt-8 space-y-5 text-lg">
              <p>
                You know the moment. Coat on, hand on the door, and suddenly: <em>where are my keys?</em> Your heart jumps a
                little.
              </p>
              <p>Then a calm voice, right there with you:</p>
            </div>
            <blockquote className="mt-8 border-l-2 border-navy pl-6">
              <p className="font-heading text-2xl font-medium leading-snug text-navy sm:text-3xl">
                &ldquo;On the kitchen table, twenty minutes ago.&rdquo;
              </p>
            </blockquote>
            <p className="mt-8 text-lg">Panic over. Keys in hand. Out the door.</p>
          </Reveal>
          <Reveal delay={0.1} className="lg:col-span-6 lg:col-start-7">
            <AskNemoDemo />
          </Reveal>
        </div>
      </div>
    </section>
  );
}
