# Nemo: marketing site

> Nemo remembers, so you don't have to.

The marketing site for **Nemo**, a wearable clip that notices where everyday things get put down and tells you out loud where it last saw them. Built at HackUTD 2026 (Zero Day).

Next.js (App Router) · TypeScript · Tailwind CSS · Framer Motion. Statically prerendered and ready for Vercel.

## Run it locally

You need Node.js 18.18 or newer (20+ recommended).

```bash
npm install
npm run dev
```

Then open http://localhost:3000.

Stop `npm run dev` before running `npm run build`. Building while the dev server runs breaks its cache; if that happens, delete `.next` and start the dev server again.

Other scripts:

```bash
npm run build           # production build
npm run start           # serve the production build
npm run lint            # ESLint
npm run check:contrast  # checks WCAG contrast for the brand colour pairs
```

## Deploy to Vercel

One command, from this folder:

```bash
npx vercel --prod
```

The first run asks you to log in and link a project. Vercel detects Next.js on its own, so no extra config is needed. You can also push the folder to GitHub and import it at vercel.com/new. If the repo holds more than this site, set **Root Directory** to `website`.

Optional environment variables (Vercel → Project → Settings → Environment Variables). See `.env.example`:

| Variable | What it does |
| --- | --- |
| `NEXT_PUBLIC_SITE_URL` | Your real domain, used for canonical and Open Graph URLs. Without it, the site falls back to the Vercel production URL. |
| `NEXT_PUBLIC_WAITLIST_ENDPOINT` | Where the waitlist form POSTs `{ name, email }` as JSON. Without it, the form uses the placeholder `/api/waitlist`. |
| `NEXT_PUBLIC_CONTACT_EMAIL` | The inbox used for the "email us instead" fallback and the FAQ link. |

## Where things live

```
src/
  theme/tokens.ts        ← colours, fonts, type scale, radii, shadows (edit here)
  content/site.ts        ← tagline, nav links, contact email, site URL
  content/faq.ts         ← FAQ questions and answers (in Nemo's voice)
  content/team.ts        ← team names (roles optional, TODO)
  app/
    layout.tsx           ← fonts (next/font), metadata, SEO, skip link
    page.tsx             ← puts the sections in order
    globals.css          ← base styles, buttons, hairlines, focus rings, reduced motion
    icon.svg             ← favicon
    apple-icon.tsx       ← generated iOS home-screen icon
    opengraph-image.tsx  ← generated 1200×630 social image (twitter-image reuses it)
    api/waitlist/route.ts← placeholder waitlist handler (TODO)
  components/            ← Logo, Header, DeviceModel (3D), AskNemoDemo, FaqAccordion, WaitlistForm, Reveal…
  sections/              ← one file per page section, top to bottom
scripts/check-contrast.mjs
```

Sections, in page order: Header · Hero · The problem · How it works · Why Nemo (Independence, Calm, Effortless) · Who it's for · Privacy · The product · Demo · Team · FAQ · Final CTA / waitlist · Footer.

## Brand rules in the code

- **Colours** live only in `src/theme/tokens.ts`. Tailwind's palette is *replaced* with them, so off-brand colours can't slip in.
- **Coral is a fill, never text on cream.** Coral on cream is 2.32:1, which fails WCAG. It's used for the primary button (navy label, 4.54:1), the logo's "o", and soft highlight underlines.
- **Aqua** is used for icon tiles with white icons (3.14:1, which meets the 3:1 rule for graphics), not for text.
- Navy on cream is 10.53:1 and charcoal on cream is 12.80:1. Run `npm run check:contrast` to see every pair.
- Body text is 18px minimum with 1.7 line height. Tap targets are 44px or larger.
- Copy avoids "seniors", "memory loss", "cognitive", "patients", "suffering", and jargon like "AI" or "database".

## Accessibility

- Semantic landmarks (`header`, `nav`, `main`, `footer`), one `h1`, and an `h2` → `h3` hierarchy. Every section is labelled by its heading.
- A skip link, a thick visible focus ring on everything (it turns cream on navy sections), and full keyboard support. The mobile menu closes with Escape and returns focus.
- The FAQ is a button-based accordion with `aria-expanded` and `aria-controls`. The demo reply is announced through `aria-live`.
- Form fields have visible labels and inline errors linked with `aria-describedby`. Focus moves to the first invalid field, then to the confirmation message.
- `prefers-reduced-motion` turns off scroll reveals, smooth scrolling, and transitions (both in CSS and in Framer Motion's `MotionConfig`).

## TODO before launch

Search the code for `TODO` to find each one:

- [ ] **Team roles**: names are in; add roles (optional) in `src/content/team.ts`. A role only shows when it's filled in.
- [ ] **Pricing**: the "What does it cost?" answer in `src/content/faq.ts` is a placeholder.
- [ ] **Waitlist backend**: connect `src/app/api/waitlist/route.ts` to a real service, or set `NEXT_PUBLIC_WAITLIST_ENDPOINT`. Right now sign-ups are only logged, **not stored**.
- [ ] **Contact email**: set `NEXT_PUBLIC_CONTACT_EMAIL` (the default `hello@nemo.example.com` is a placeholder).
- [ ] **Domain**: set `NEXT_PUBLIC_SITE_URL`.
- [ ] **Images**: the device is a 3D render (`src/components/DeviceModel.tsx`). Still to replace: the demo snapshots (`src/components/Scenes.tsx`) and the OG image, with real photos when you have them.
- [ ] **Privacy and paired device**: confirm the privacy promises and the FAQ answer about the paired device match the final product.

This is a student project: there are no testimonials, press logos, or company claims on the site, so please keep it that way.

## The 3D device

`src/components/DeviceModel.tsx` draws Nemo in 3D with three.js, built in code to the measurements of the team's CAD enclosure (`nemo.glb`): a 61 x 113 x 32 mm box with a 3 mm front plate, an 11 mm camera opening, a 30 x 15 mm screen window, a mic pinhole, two small eyelets and one coral button on the right side. It's turned so the screen sits above the camera, like the real device, with cleaner edges and a finished look (a muted slate blue body, lighter front plate, a metal trim around the camera, a dark display).

- Sizes and feature positions are at the top of `buildDevice()` at the bottom of the file. If the enclosure changes, update the numbers there.
- What the screen shows is drawn in `drawScreen()` (currently the answer to "Where are my keys?").
- Colours are the constants at the top of the file (`BODY`, `PLATE`, `SEAM`, `LENS_GLASS`, `DISPLAY_BG`).

It sways slowly on its own, stays still under reduced motion, and can be dragged sideways to turn it. Vertical swipes still scroll the page on phones.
