import { Reveal } from "@/components/Reveal";
import { SectionLabel } from "@/components/SectionLabel";

const pillars = [
  {
    name: "Independence",
    title: "Your things, your way.",
    body: "Find what you need on your own, in seconds, without waiting for someone to help you look.",
  },
  {
    name: "Calm",
    title: "An answer instead of a scramble.",
    body: "No more turning the house upside down. One question, one clear reply, and on with your day.",
  },
  {
    name: "Effortless",
    title: "Nothing to remember. That’s the point.",
    body: "Clip it on and carry on. No stickers on your things and no apps to open. Just a button and your voice.",
  },
];

export function Pillars() {
  return (
    <section aria-labelledby="why-title" className="section pt-0 sm:pt-0" id="why-nemo">
      <div className="container-page">
        <SectionLabel index="03">Why Nemo</SectionLabel>
        <Reveal>
          <h2 id="why-title" className="display mt-14 max-w-3xl">
            Less searching. More living.
          </h2>
        </Reveal>
        <ul className="mt-16">
          {pillars.map((p, i) => (
            <Reveal as="li" key={p.name} delay={i * 0.06} className="rule grid gap-4 py-10 lg:grid-cols-12 lg:gap-10 lg:py-12">
              <p className="font-heading text-3xl font-semibold text-navy sm:text-4xl lg:col-span-5">{p.name}</p>
              <div className="lg:col-span-6 lg:col-start-7">
                <h3 className="text-xl">{p.title}</h3>
                <p className="mt-2 text-lg">{p.body}</p>
              </div>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  );
}
