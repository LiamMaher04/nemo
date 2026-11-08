import { DeviceModel } from "@/components/DeviceModel";
import { Reveal } from "@/components/Reveal";
import { SectionLabel } from "@/components/SectionLabel";

const specs = [
  { term: "Size", detail: "About the size of a deck of cards, and light enough to forget." },
  { term: "Wear it", detail: "On a shirt, a pocket, a lanyard or a necklace." },
  { term: "Controls", detail: "One button, easy to find by feel." },
  { term: "Answers", detail: "Out loud, in a clear voice, with a snapshot on its small screen." },
  { term: "Works", detail: "Around your home, over WiFi, with its paired device." },
  { term: "Charging", detail: "A standard USB-C cable." },
];

export function Product() {
  return (
    <section aria-labelledby="product-title" className="section" id="product">
      <div className="container-page">
        <SectionLabel index="07">The device</SectionLabel>
        <Reveal>
          <h2 id="product-title" className="display mt-14 max-w-4xl">
            Small enough to wear all day. Simple enough to forget it&rsquo;s there.
          </h2>
        </Reveal>

        <div className="mt-16 grid items-center gap-14 lg:grid-cols-12">
          <Reveal className="lg:col-span-7">
            <div>
              <DeviceModel className="h-[24rem] sm:h-[32rem]" hint />
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
