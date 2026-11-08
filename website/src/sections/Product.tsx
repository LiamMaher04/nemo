import { DeviceModel } from "@/components/DeviceModel";
import { Reveal } from "@/components/Reveal";
import { SectionLabel } from "@/components/SectionLabel";

const specs = [
  { term: "Size", detail: "About the size of a deck of cards, and light enough to forget." },
  { term: "Wear it", detail: "Clipped to your shirt at chest height, or on a lanyard, so it sees what you see." },
  { term: "Controls", detail: "One button on the side, easy to find by feel. Hold it and talk." },
  { term: "Answers", detail: "Out loud, in a clear voice, with the place and how long ago." },
  { term: "Screen", detail: "Just a pair of eyes: open while Nemo is on, closed when it’s off." },
  { term: "Works", detail: "Indoors at home, over WiFi, with a small hub (for now, a laptop)." },
  { term: "Power", detail: "USB-C, from a small power bank in your pocket." },
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
