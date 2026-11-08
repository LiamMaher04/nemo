import { Reveal } from "@/components/Reveal";
import { RoomMap } from "@/components/RoomMap";
import { SectionLabel } from "@/components/SectionLabel";

const steps = [
  {
    title: "Clip it on",
    body: "Straight out of the box, clip Nemo to your shirt or hang it from a lanyard.",
  },
  {
    title: "Walk through each room",
    body: "Go room by room at your own pace, the way you’d show a guest around. Nemo maps out your home as you go.",
  },
  {
    title: "Say the room’s name",
    body: "In each room, hold the button and say what it is: “Kitchen.” “Living room.” “Bedroom.”",
  },
];

/** One-time setup: walk Nemo around the home and name each room. */
export function Setup() {
  return (
    <section aria-labelledby="setup-title" className="section pt-0 sm:pt-0" id="setup">
      <div className="container-page">
        <SectionLabel index="03">Getting started</SectionLabel>

        <div className="mt-14 grid gap-6 lg:grid-cols-12">
          <Reveal className="lg:col-span-6">
            <h2 id="setup-title" className="display">
              Show it around once. Then just wear it.
            </h2>
          </Reveal>
          <Reveal delay={0.08} className="lg:col-span-5 lg:col-start-8 lg:pt-3">
            <p className="text-xl">
              The first day, you give Nemo a quick tour of your home. That&rsquo;s how it can tell you &ldquo;in the
              kitchen&rdquo; instead of just &ldquo;on a table.&rdquo;
            </p>
          </Reveal>
        </div>

        <div className="mt-16 grid items-center gap-12 lg:grid-cols-12">
          <Reveal className="lg:col-span-5">
            <ol>
              {steps.map((s, i) => (
                <li key={s.title} className="rule grid grid-cols-[3rem_1fr] gap-4 py-6">
                  <span className="font-heading text-3xl font-semibold leading-none text-navy" aria-hidden="true">
                    {i + 1}
                  </span>
                  <div>
                    <h3 className="text-2xl">
                      <span className="sr-only">Step {i + 1}: </span>
                      {s.title}
                    </h3>
                    <p className="mt-2">{s.body}</p>
                  </div>
                </li>
              ))}
            </ol>
            <p className="rule pt-6 font-heading text-2xl font-medium leading-snug text-navy">
              You only do this once. After that, just wear Nemo and ask.
            </p>
          </Reveal>

          <Reveal delay={0.1} className="lg:col-span-6 lg:col-start-7">
            <figure>
              <RoomMap className="h-auto w-full" />
              <figcaption className="sr-only">
                A floor plan of a home with a dotted path from the front door through the bedroom, kitchen, living room and
                bathroom, with each room&rsquo;s name said out loud along the way.
              </figcaption>
            </figure>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
