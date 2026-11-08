import { FaqAccordion } from "@/components/FaqAccordion";
import { Reveal } from "@/components/Reveal";
import { SectionLabel } from "@/components/SectionLabel";
import { faqs } from "@/content/faq";
import { site } from "@/content/site";

export function Faq() {
  return (
    <section aria-labelledby="faq-title" className="section pt-0 sm:pt-0" id="faq">
      <div className="container-page">
        <SectionLabel index="09">Questions</SectionLabel>
        <div className="mt-14 grid gap-12 lg:grid-cols-12 lg:gap-10">
          <Reveal className="lg:col-span-4">
            <h2 id="faq-title" className="text-4xl sm:text-5xl">
              You ask. I answer.
            </h2>
            <p className="mt-6 text-lg">
              Here&rsquo;s what people ask me most. Something else on your mind?{" "}
              <a href={`mailto:${site.contactEmail}`} className="text-link">
                Write to the team
              </a>
              .
            </p>
          </Reveal>
          <Reveal delay={0.08} className="lg:col-span-7 lg:col-start-6">
            <FaqAccordion items={faqs} />
          </Reveal>
        </div>
      </div>
    </section>
  );
}
