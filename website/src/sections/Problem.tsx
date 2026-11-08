import { Reveal } from "@/components/Reveal";
import { SectionLabel } from "@/components/SectionLabel";

export function Problem() {
  return (
    <section aria-labelledby="problem-title" className="on-navy section" id="problem">
      <div className="container-page">
        <SectionLabel index="01">Where did I put&hellip;?</SectionLabel>
        <Reveal>
          <h2 id="problem-title" className="mt-14 max-w-4xl text-4xl sm:text-5xl lg:text-6xl">
            It starts with the keys. It ends with the whole morning.
          </h2>
        </Reveal>
        <Reveal delay={0.1} className="mt-14 grid gap-8 text-lg md:grid-cols-2 md:gap-14 lg:ml-[33%] lg:max-w-3xl">
          <p>
            You were holding them a minute ago. Now you&rsquo;re checking the counter, the coat, the couch cushions. Again. The
            car is waiting. So is your day.
          </p>
          <p>
            It&rsquo;s a small thing that doesn&rsquo;t feel small. It costs time and chips at your confidence. Sometimes it
            means calling someone to help look for something that was right there all along.
          </p>
        </Reveal>
        <Reveal delay={0.15} className="mt-16 lg:ml-[33%]">
          <p className="max-w-2xl font-heading text-2xl font-medium leading-snug sm:text-3xl">
            You know your home. You run your life. You just need a little backup for the little things.
          </p>
        </Reveal>
      </div>
    </section>
  );
}
