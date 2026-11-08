"use client";

import { useRef, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { site } from "@/content/site";

type Status = "idle" | "sending" | "done" | "error";

// TODO: set NEXT_PUBLIC_WAITLIST_ENDPOINT to a real service (Formspree, Resend, Airtable…).
// Without it, the form posts to the placeholder handler in src/app/api/waitlist/route.ts.
const ENDPOINT = process.env.NEXT_PUBLIC_WAITLIST_ENDPOINT || "/api/waitlist";

export function WaitlistForm() {
  const [status, setStatus] = useState<Status>("idle");
  const [firstName, setFirstName] = useState("");
  const [errors, setErrors] = useState<{ name?: string; email?: string }>({});
  const successRef = useRef<HTMLDivElement>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    const name = String(data.get("name") ?? "").trim();
    const email = String(data.get("email") ?? "").trim();

    const next: typeof errors = {};
    if (!name) next.name = "Please tell us your name.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) next.email = "Please enter an email address like name@example.com.";
    setErrors(next);
    if (next.name || next.email) {
      (form.elements.namedItem(next.name ? "name" : "email") as HTMLInputElement | null)?.focus();
      return;
    }

    setStatus("sending");
    try {
      const res = await fetch(ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ name, email }),
      });
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      setFirstName(name.split(" ")[0]);
      setStatus("done");
      requestAnimationFrame(() => successRef.current?.focus());
    } catch {
      setStatus("error");
    }
  }

  if (status === "done") {
    return (
      <div ref={successRef} tabIndex={-1} role="status" className="rule pt-8">
        <CheckCircle2 size={36} className="text-cream" aria-hidden="true" />
        <p className="mt-4 font-heading text-2xl font-semibold text-cream">Thank you, {firstName}. You&rsquo;re on the list.</p>
        <p className="mt-3 text-lg">
          We&rsquo;ll write when Nemo is ready for you. Just the news that matters, nothing more. Until then, may your keys be
          exactly where you left them.
        </p>
      </div>
    );
  }

  const mailto = `mailto:${site.contactEmail}?subject=${encodeURIComponent("Nemo waitlist")}`;

  return (
    <form onSubmit={onSubmit} noValidate aria-describedby="waitlist-note">
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="wl-name" className="block font-heading font-semibold text-cream">
            Your name
          </label>
          <input
            id="wl-name"
            name="name"
            type="text"
            autoComplete="name"
            required
            aria-invalid={!!errors.name}
            aria-describedby={errors.name ? "wl-name-error" : undefined}
            className="mt-2 block min-h-[3.25rem] w-full rounded-lg border-0 bg-cream px-4 text-lg text-charcoal"
          />
          {errors.name && (
            <p id="wl-name-error" className="mt-2 font-semibold text-cream">
              {errors.name}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="wl-email" className="block font-heading font-semibold text-cream">
            Email address
          </label>
          <input
            id="wl-email"
            name="email"
            type="email"
            inputMode="email"
            autoComplete="email"
            required
            aria-invalid={!!errors.email}
            aria-describedby={errors.email ? "wl-email-error" : undefined}
            className="mt-2 block min-h-[3.25rem] w-full rounded-lg border-0 bg-cream px-4 text-lg text-charcoal"
          />
          {errors.email && (
            <p id="wl-email-error" className="mt-2 font-semibold text-cream">
              {errors.email}
            </p>
          )}
        </div>
      </div>

      <button type="submit" className="btn-primary mt-6 w-full sm:w-auto" disabled={status === "sending"}>
        {status === "sending" ? "Adding you…" : "Join the waitlist"}
      </button>

      {status === "error" && (
        <p role="alert" className="mt-5 text-lg">
          Sorry, that didn&rsquo;t go through. You can{" "}
          <a href={mailto} className="text-link">
            email us instead
          </a>{" "}
          and we&rsquo;ll add you by hand.
        </p>
      )}

      <p id="waitlist-note" className="mt-5 text-base">
        We&rsquo;ll only use your email to tell you about Nemo. No spam, ever.
      </p>
    </form>
  );
}
