import { DeviceModel } from "@/components/DeviceModel";
import { Reveal } from "@/components/Reveal";
import { ThingIcon } from "@/components/ThingIcons";

const things = [
  { label: "Keys", Icon: ThingIcon.keys },
  { label: "Glasses", Icon: ThingIcon.glasses },
  { label: "TV remote", Icon: ThingIcon.remote },
  { label: "Pill box", Icon: ThingIcon.pillbox },
];

export function Hero() {
  return (
    <section aria-labelledby="hero-title" id="top">
      <div className="container-page grid items-center gap-12 pb-16 pt-8 sm:pt-12 lg:grid-cols-12 lg:gap-10 lg:pb-24 lg:pt-16">
        <Reveal className="lg:col-span-7">
          <h1 id="hero-title" className="text-4xl font-semibold min-[400px]:text-5xl sm:text-6xl xl:text-7xl">
            Nemo remembers,
            <br />
            so you don&rsquo;t have&nbsp;to.
          </h1>
          <p className="mt-7 max-w-xl text-xl text-charcoal">
            A small device you wear that remembers where you put things and tells you when you ask.
          </p>
          <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center">
            <a href="#waitlist" className="btn-primary">
              Join the waitlist
            </a>
            <a href="#how-it-works" className="btn-ghost">
              See how it works
            </a>
          </div>
        </Reveal>

        <Reveal delay={0.12} className="lg:col-span-5">
          <figure>
            <DeviceModel className="h-72 sm:h-96" />
            {/* What it sounds like */}
            <figcaption className="rounded-xl p-5 ring-1 ring-inset ring-navy/15">
              <p className="text-base text-charcoal">
                <span className="font-semibold text-navy">You:</span> &ldquo;Where are my keys?&rdquo;
              </p>
              <p className="mt-1.5 text-base text-charcoal">
                <span className="font-semibold text-navy">Nemo:</span> &ldquo;I last saw them on the kitchen table.&rdquo;
              </p>
            </figcaption>
          </figure>
        </Reveal>
      </div>

      {/* The everyday things Nemo keeps track of */}
      <div className="container-page">
        <div className="rule flex flex-col gap-5 py-7 sm:flex-row sm:items-center sm:justify-between">
          <p className="font-medium text-navy">Keeps track of the things that wander off</p>
          <ul className="flex flex-wrap gap-x-7 gap-y-3 text-navy">
            {things.map(({ label, Icon }) => (
              <li key={label} className="flex items-center gap-2.5">
                <Icon />
                <span>{label}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
