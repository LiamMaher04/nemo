/** Site-wide settings and shared copy. */

export const site = {
  name: "Nemo",
  tagline: "Nemo remembers, so you don't have to.",
  promise: "You'll always know where it is.",
  ask: "Just ask Nemo.",
  description:
    "Nemo is a small device you wear that notices where you put everyday things like keys, glasses and the remote. Hold its one button, ask out loud, and Nemo tells you where it last saw them.",
  // TODO: set NEXT_PUBLIC_SITE_URL in Vercel to your real domain.
  url:
    process.env.NEXT_PUBLIC_SITE_URL ??
    (process.env.VERCEL_PROJECT_PRODUCTION_URL
      ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
      : "http://localhost:3000"),
  // TODO: replace with the team's real inbox.
  contactEmail: process.env.NEXT_PUBLIC_CONTACT_EMAIL ?? "hello@nemo.example.com",
  hackathon: "HackUTD 2026 (Zero Day)",
};

export const navLinks = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#why-nemo", label: "Why Nemo" },
  { href: "#privacy", label: "Privacy" },
  { href: "#team", label: "Team" },
  { href: "#faq", label: "FAQ" },
] as const;
