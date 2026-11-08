import { Reveal } from "@/components/Reveal";
import { SectionLabel } from "@/components/SectionLabel";

const audiences = [
  {
    label: "If it’s for you",
    title: "For staying independent",
    body: "You don’t need anyone hovering. You just need to find your glasses before the kettle boils.",
    points: ["Find your own things, in seconds", "A friendly reminder when it’s time for your pills", "Works the way you already talk"],
  },
  {
    label: "If it’s for your mom or dad",
    title: "For peace of mind",
    body: "You want them to feel capable at home, and you’d like to worry a little less between visits.",
    points: ["Fewer “have you seen my…?” calls", "A text if something seems off, so you know to check in", "More independence for the people you love"],
  },
];

export function WhoFor() {
  return (
    <section aria-labelledby="who-title" className="section bg-navy/[0.05]" id="who-its-for">
      <div className="container-page">
        <SectionLabel index="05">Who it&rsquo;s for</SectionLabel>
        <Reveal>
          <h2 id="who-title" className="display mt-14 max-w-4xl">
            Made for the person wearing it. Loved by the people who care.
          </h2>
        </Reveal>
        <div className="mt-16 grid lg:grid-cols-2 lg:grid-rows-[auto_auto_auto_1fr]">
          {audiences.map((a, i) => (
            <Reveal
              key={a.title}
              delay={i * 0.1}
              className={`border-navy/15 py-10 lg:row-span-4 lg:grid lg:grid-rows-subgrid lg:py-2 ${i === 0 ? "lg:pr-14" : "border-t lg:border-l lg:border-t-0 lg:pl-14"}`}
            >
              <p className="font-medium text-navy">{a.label}</p>
              <h3 className="mt-4 text-3xl sm:text-4xl">{a.title}</h3>
              <p className="mt-5 max-w-md text-lg">{a.body}</p>
              <ul className="mt-8 max-w-md">
                {a.points.map((pt) => (
                  <li key={pt} className="rule flex gap-4 py-3.5">
                    <span aria-hidden="true" className="mt-[0.7rem] h-1.5 w-1.5 shrink-0 rounded-full bg-navy" />
                    <span>{pt}</span>
                  </li>
                ))}
              </ul>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
