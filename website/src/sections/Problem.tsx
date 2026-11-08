import { Reveal } from "@/components/Reveal";
import { SectionLabel } from "@/components/SectionLabel";

/**
 * Two columns on a 12-column grid: the headline on the left (cols 1–6),
 * and the story on the right (cols 7–12). Everything on the right shares one left edge,
 * one text size for the body, and lines up with the top of the headline.
 */
export function Problem() {
  return (
    <section aria-labelledby="problem-title" className="on-navy section" id="problem">
      <div className="container-page">
        <SectionLabel index="01">Where did I put&hellip;?</SectionLabel>

        <div className="mt-14 grid gap-10 lg:grid-cols-12 lg:gap-x-10">
          <Reveal className="lg:col-span-6">
            <h2 id="problem-title" className="display">
              It starts with the keys. It ends with the whole morning.
            </h2>
          </Reveal>

          <Reveal delay={0.1} className="lg:col-span-5 lg:col-start-8">
            <div className="space-y-6 text-xl leading-relaxed">
              <p>
                You were holding them a minute ago. Now you&rsquo;re checking the counter, the coat, the couch cushions.
                Again. The car is waiting. So is your day.
              </p>
              <p>
                It&rsquo;s a small thing that doesn&rsquo;t feel small. It costs time and chips at your confidence.
                Sometimes it means calling someone to help look for something that was right there all along.
              </p>
            </div>
            <p className="rule mt-10 pt-8 font-heading text-2xl font-medium leading-snug">
              You know your home. You run your life. You just need a little backup for the little things.
            </p>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
