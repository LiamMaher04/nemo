import { ClipVisual } from "@/components/ClipVisual";
import { Reveal } from "@/components/Reveal";
import { SectionLabel } from "@/components/SectionLabel";

const specs = [
  { term: "Size", detail: "About the size of a deck of cards, and light enough to forget." },
  { term: "Wear it", detail: "On a shirt, a pocket, a lanyard or a necklace." },
  { term: "Controls", detail: "One big button you can find without looking." },
  { term: "Answers", detail: "Out loud, in a clear voice. It can show you a photo, too." },
  { term: "Works", detail: "Around your home, over WiFi, with its paired device." },
  { term: "Charging", detail: "A standard USB-C cable." },
];

// Callout positions are percentages of the render's own box (see ClipVisual).
const callouts = [
  { label: "Tiny camera", top: "27%", side: "right" as const },
  { label: "The one button", top: "55%", side: "right" as const },
  { label: "Speaker", top: "76%", side: "right" as const },
  { label: "Clip on the back", top: "6%", side: "right" as const },
];

export function Product() {
  return (
    <section aria-labelledby="product-title" className="section" id="product">
      <div className="container-page">
        <SectionLabel index="06">The clip</SectionLabel>
        <Reveal>
          <h2 id="product-title" className="display mt-14 max-w-4xl">
            Small enough to wear all day. Simple enough to forget it&rsquo;s there.
          </h2>
        </Reveal>

        <div className="mt-16 grid items-center gap-14 lg:grid-cols-12">
          <Reveal className="lg:col-span-7">
            <div className="flex justify-center rounded-2xl bg-navy/[0.06] px-6 py-14 sm:py-16">
              <div className="relative h-[20rem] sm:h-[26rem] md:mr-56 lg:mr-48">
                <ClipVisual className="h-full w-auto" idPrefix="product" />
                {callouts.map((c) => (
                  <div
                    key={c.label}
                    aria-hidden="true"
                    className={`absolute hidden items-center gap-3 text-base font-medium text-navy md:flex ${
                      c.side === "right" ? "left-[64%] flex-row" : "right-[64%] flex-row-reverse"
                    }`}
                    style={{ top: c.top, transform: "translateY(-50%)" }}
                  >
                    <span className="h-2 w-2 shrink-0 rounded-full bg-navy" />
                    <span className="h-px w-20 bg-navy/50 lg:w-24" />
                    <span className="whitespace-nowrap">{c.label}</span>
                  </div>
                ))}
              </div>
            </div>
          </Reveal>

          <Reveal delay={0.1} className="lg:col-span-5">
            <dl>
              {specs.map((s) => (
                <div key={s.term} className="rule grid grid-cols-[7rem_1fr] gap-4 py-4 sm:grid-cols-[8rem_1fr]">
                  <dt className="font-heading font-semibold text-navy">{s.term}</dt>
                  <dd>{s.detail}</dd>
                </div>
              ))}
            </dl>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
