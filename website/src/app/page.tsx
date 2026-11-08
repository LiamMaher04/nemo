import { Header } from "@/components/Header";
import { Demo } from "@/sections/Demo";
import { Faq } from "@/sections/Faq";
import { FinalCta } from "@/sections/FinalCta";
import { Footer } from "@/sections/Footer";
import { Hero } from "@/sections/Hero";
import { HowItWorks } from "@/sections/HowItWorks";
import { Pillars } from "@/sections/Pillars";
import { Privacy } from "@/sections/Privacy";
import { Problem } from "@/sections/Problem";
import { Product } from "@/sections/Product";
import { Setup } from "@/sections/Setup";
import { Team } from "@/sections/Team";
import { WhoFor } from "@/sections/WhoFor";

export default function HomePage() {
  return (
    <>
      <Header />
      <main id="main" tabIndex={-1} className="focus:outline-none">
        <Hero />
        <Problem />
        <HowItWorks />
        <Setup />
        <Pillars />
        <WhoFor />
        <Privacy />
        <Product />
        <Demo />
        <Team />
        <Faq />
        <FinalCta />
      </main>
      <Footer />
    </>
  );
}
