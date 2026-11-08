import { Reveal } from "@/components/Reveal";
import { WaitlistForm } from "@/components/WaitlistForm";
import { site } from "@/content/site";

export function FinalCta() {
  return (
    <section aria-labelledby="waitlist-title" className="on-navy section" id="waitlist">
      <div className="container-page grid gap-14 lg:grid-cols-12 lg:gap-10">
        <Reveal className="lg:col-span-6">
          <h2 id="waitlist-title" className="text-5xl sm:text-6xl xl:text-7xl">
            {site.ask}
          </h2>
          <p className="mt-8 max-w-lg text-lg">
            Nemo is a working prototype today. Join the waitlist and we&rsquo;ll tell you when it&rsquo;s ready to clip on, for
            you, or for someone you love.
          </p>
        </Reveal>
        <Reveal delay={0.1} className="lg:col-span-5 lg:col-start-8 lg:pt-4">
          <WaitlistForm />
        </Reveal>
      </div>
    </section>
  );
}
