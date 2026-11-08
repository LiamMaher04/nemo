import { Logo } from "@/components/Logo";
import { navLinks, site } from "@/content/site";

export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="on-navy">
      <div className="container-page">
        <div className="rule grid gap-10 py-12 md:grid-cols-12">
          <div className="md:col-span-6">
            <p className="font-heading text-xl font-medium">{site.tagline}</p>
            <p className="mt-2">{site.promise}</p>
          </div>
          <nav aria-label="Footer" className="md:col-span-5 md:col-start-8">
            <ul className="grid grid-cols-2 gap-x-8">
              {[...navLinks, { href: "#waitlist", label: "Join the waitlist" }].map((l) => (
                <li key={l.href}>
                  <a href={l.href} className="inline-flex min-h-11 items-center underline-offset-[6px] hover:underline">
                    {l.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </div>

        {/* Big closing wordmark */}
        <a href="#top" className="block rounded-lg py-6" aria-label="Nemo, back to top">
          <Logo className="h-auto w-full max-w-[56rem]" tone="cream" decorative />
        </a>

        <div className="rule flex flex-col gap-2 py-7 sm:flex-row sm:justify-between">
          <p>Built at HackUTD 2026. A student project.</p>
          <p>&copy; {year} The Nemo team</p>
        </div>
      </div>
    </footer>
  );
}
