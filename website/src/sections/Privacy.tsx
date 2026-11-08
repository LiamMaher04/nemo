import { Reveal } from "@/components/Reveal";
import { SectionLabel } from "@/components/SectionLabel";
import Image from "next/image";

/** The three privacy rules Nemo is built around (see the repo's CLAUDE.md). */
const rules = [
  {
    title: "No video kept",
    body: "Nemo takes quick looks, not recordings. It keeps only small snapshots of your things.",
    art: "snapshots",
  },
  {
    title: "Faces blurred",
    body: "Faces are blurred before anything is saved, and Nemo doesn’t recognise people.",
    art: "face",
  },
  {
    title: "Listens only when asked",
    body: "The microphone is on only while you hold the button.",
    art: "listen",
  },
];

export function Privacy() {
  return (
    <section aria-labelledby="privacy-title" className="on-navy section" id="privacy">
      <div className="container-page">
        <SectionLabel index="06">Privacy</SectionLabel>
        <div className="mt-14 grid gap-10 lg:grid-cols-12">
          <Reveal className="lg:col-span-7">
            <h2 id="privacy-title" className="display">
              Nemo watches things, not&nbsp;people.
            </h2>
          </Reveal>
          <Reveal delay={0.08} className="lg:col-span-4 lg:col-start-9 lg:pt-3">
            <p className="text-xl">
              It&rsquo;s the first question families ask, and it should be. Here&rsquo;s exactly what Nemo keeps, and what it
              doesn&rsquo;t.
            </p>
          </Reveal>
        </div>

        <Reveal delay={0.1} className="mt-16">
          <ul className="grid divide-y divide-cream/20 rounded-2xl ring-1 ring-cream/20 md:grid-cols-3 md:divide-x md:divide-y-0">
            {rules.map((r) => (
              <li key={r.title} className="flex flex-col items-start gap-5 p-7">
                <Image src={`/illustrations/${r.art}.svg`} alt="" width={480} height={300} unoptimized className="h-auto w-full" />
                <div>
                  <h3 className="text-xl">{r.title}</h3>
                  <p className="mt-2">{r.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </Reveal>

        <div className="mt-16 grid gap-10 md:grid-cols-2 md:gap-12">
          <Reveal className="rule pt-6">
            <h3 className="text-xl">What goes online</h3>
            <p className="mt-3">
              A laptop at home does the looking. To remember where things are and to put answers into words, Nemo uses online
              services. It sends only small snapshots of your things and the words of your question. Never video.
            </p>
          </Reveal>
          <Reveal delay={0.06} className="rule pt-6">
            <h3 className="text-xl">What it&rsquo;s for</h3>
            <p className="mt-3">
              Finding your keys, your glasses, the remote, indoors at home. Its eyes are open whenever it&rsquo;s on, so you can
              always tell. Nemo is there to help you with your things.
            </p>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
