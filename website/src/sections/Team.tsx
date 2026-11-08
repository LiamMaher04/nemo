import { Reveal } from "@/components/Reveal";
import { SectionLabel } from "@/components/SectionLabel";
import { team } from "@/content/team";

export function Team() {
  return (
    <section aria-labelledby="team-title" className="section" id="team">
      <div className="container-page">
        <SectionLabel index="09">The team</SectionLabel>
        <div className="mt-14 grid gap-14 lg:grid-cols-12 lg:gap-10">
          <Reveal className="lg:col-span-6">
            <h2 id="team-title" className="text-4xl sm:text-5xl">
              Four students. One weekend. A lot of lost keys.
            </h2>
            <p className="mt-8 max-w-xl text-lg">
              We built Nemo at HackUTD 2026 (Zero Day), from a 3D-printed case to a device that answers out loud. We&rsquo;ve all
              watched someone we love lose ten minutes to a pair of glasses, and we wanted to give that time back. We&rsquo;re proud
              of what we made in a weekend, and we&rsquo;re just getting started.
            </p>
          </Reveal>
          <Reveal delay={0.1} className="lg:col-span-5 lg:col-start-8">
            <ul className="border-b border-navy/15">
              {team.map((m) => (
                <li key={m.name} className="rule flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 py-6">
                  <h3 className="text-2xl sm:text-3xl">{m.name}</h3>
                  {m.role && <p>{m.role}</p>}
                </li>
              ))}
            </ul>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
