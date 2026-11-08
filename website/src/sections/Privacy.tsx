import { Reveal } from "@/components/Reveal";
import { SectionLabel } from "@/components/SectionLabel";
import { colors } from "@/theme/tokens";

const line = { fill: "none", stroke: colors.cream, strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

/** The three privacy rules Nemo is built around (see the repo's CLAUDE.md). */
const rules = [
  {
    title: "No video kept",
    body: "Nemo takes quick looks, not recordings. It keeps only small snapshots of your things.",
    icon: (
      <svg viewBox="0 0 48 48" className="h-12 w-12" aria-hidden="true">
        <rect x="5" y="13" width="26" height="22" rx="4" {...line} />
        <path d="M31 21l11-6v18l-11-6" {...line} />
        <path d="M6 42L42 6" stroke={colors.coral} strokeWidth="3" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    title: "Faces blurred",
    body: "Faces are blurred before anything is saved, and Nemo doesn’t recognise people.",
    icon: (
      <svg viewBox="0 0 48 48" className="h-12 w-12" aria-hidden="true">
        <circle cx="24" cy="24" r="17" {...line} />
        <path d="M14 20h20M12 26h24M14 32h20" {...line} strokeOpacity="0.55" strokeDasharray="2 4" />
      </svg>
    ),
  },
  {
    title: "Listens only when asked",
    body: "The microphone turns on only when you press the button.",
    icon: (
      <svg viewBox="0 0 48 48" className="h-12 w-12" aria-hidden="true">
        <rect x="18" y="6" width="12" height="22" rx="6" {...line} />
        <path d="M11 22a13 13 0 0 0 26 0M24 35v7M17 42h14" {...line} />
      </svg>
    ),
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
                {r.icon}
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
              services, and it only ever sends those small snapshots of your things. Never video.
            </p>
          </Reveal>
          <Reveal delay={0.06} className="rule pt-6">
            <h3 className="text-xl">What it&rsquo;s for</h3>
            <p className="mt-3">
              Finding your keys, your glasses, the remote. Nemo is there to help you with your things. That&rsquo;s the whole job.
            </p>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
