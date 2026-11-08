import { Reveal } from "@/components/Reveal";
import { SectionLabel } from "@/components/SectionLabel";
import { colors } from "@/theme/tokens";

const line = { fill: "none", stroke: colors.cream, strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

const promises = [
  {
    title: "Things, not people",
    body: "Nemo pays attention to everyday objects like keys, glasses and the remote. It isn’t there to watch you or anyone you’re with.",
  },
  {
    title: "It stays at home",
    body: "The pictures and the remembering live on your own paired device at home. Not uploaded. Not posted anywhere.",
  },
  {
    title: "Help, not keeping tabs",
    body: "Nemo isn’t a way for anyone to check up on you. It answers one person’s questions: yours.",
  },
];

/** Where the pictures go: and where they don't. */
function FlowDiagram() {
  return (
    <figure className="rounded-2xl ring-1 ring-cream/20">
      <ol className="grid divide-y divide-cream/20 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        <li className="flex flex-col items-start gap-5 p-7">
          <svg viewBox="0 0 48 48" className="h-12 w-12" aria-hidden="true">
            <rect x="14" y="5" width="20" height="38" rx="7" {...line} />
            <circle cx="24" cy="15" r="3.5" {...line} />
            <circle cx="24" cy="29" r="5" fill={colors.coral} />
          </svg>
          <p>
            <span className="block font-heading text-lg font-semibold">Your clip</span>
            notices where things land
          </p>
        </li>
        <li className="flex flex-col items-start gap-5 p-7">
          <svg viewBox="0 0 48 48" className="h-12 w-12" aria-hidden="true">
            <path d="M6 22L24 7l18 15v19H6z" {...line} />
            <rect x="15" y="25" width="18" height="11" rx="1.5" {...line} />
            <path d="M12 36h24" {...line} />
          </svg>
          <p>
            <span className="block font-heading text-lg font-semibold">Your paired device</span>
            remembers, at home
          </p>
        </li>
        <li className="flex flex-col items-start gap-5 p-7">
          <svg viewBox="0 0 48 48" className="h-12 w-12" aria-hidden="true">
            <path d="M14 34h21a8 8 0 0 0 0-16 11 11 0 0 0-21-2A9 9 0 0 0 14 34z" {...line} strokeOpacity="0.55" />
            <path d="M8 42L40 8" stroke={colors.coral} strokeWidth="3" strokeLinecap="round" />
          </svg>
          <p>
            <span className="block font-heading text-lg font-semibold">The internet</span>
            never sees it
          </p>
        </li>
      </ol>
      <figcaption className="sr-only">
        Pictures go from your clip to your paired device at home, and are never sent to the internet.
      </figcaption>
    </figure>
  );
}

export function Privacy() {
  return (
    <section aria-labelledby="privacy-title" className="on-navy section" id="privacy">
      <div className="container-page">
        <SectionLabel index="05">Privacy</SectionLabel>
        <div className="mt-14 grid gap-10 lg:grid-cols-12">
          <Reveal className="lg:col-span-7">
            <h2 id="privacy-title" className="display">
              Nemo watches things, not&nbsp;people.
            </h2>
          </Reveal>
          <Reveal delay={0.08} className="lg:col-span-4 lg:col-start-9 lg:pt-3">
            <p className="text-xl">
              It&rsquo;s the first question families ask, and it should be. A camera you wear has to earn your trust. Here&rsquo;s
              how Nemo does.
            </p>
          </Reveal>
        </div>

        <Reveal delay={0.1} className="mt-16">
          <FlowDiagram />
        </Reveal>

        <ul className="mt-16 grid gap-10 md:grid-cols-3 md:gap-12">
          {promises.map((p, i) => (
            <Reveal as="li" key={p.title} delay={i * 0.06} className="rule pt-6">
              <h3 className="text-xl">{p.title}</h3>
              <p className="mt-3">{p.body}</p>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  );
}
