"use client";

import { useEffect, useRef, useState } from "react";
import { Menu, X } from "lucide-react";
import { Logo } from "./Logo";
import { navLinks } from "@/content/site";

export function Header() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Close the mobile menu with Escape and return focus to the toggle.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        toggleRef.current?.focus();
      }
    };
    const onResize = () => window.innerWidth >= 1024 && setOpen(false);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", onResize);
    return () => {
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onResize);
    };
  }, [open]);

  return (
    <header
      className={`sticky top-0 z-50 transition-[background-color,box-shadow] duration-300 ${
        scrolled || open ? "border-b border-navy/15 bg-cream/95 backdrop-blur" : "border-b border-transparent bg-cream"
      }`}
    >
      <div className="container-page flex h-20 items-center justify-between gap-6">
        <a href="#top" className="inline-flex min-h-11 items-center rounded-lg" aria-label="Nemo, back to top">
          <Logo className="h-7 w-auto" decorative />
        </a>

        <nav aria-label="Main" className="hidden lg:block">
          <ul className="flex items-center gap-1">
            {navLinks.map((l) => (
              <li key={l.href}>
                <a
                  href={l.href}
                  className="inline-flex min-h-11 items-center px-4 font-medium text-navy underline-offset-[6px] hover:underline"
                >
                  {l.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="flex items-center gap-3">
          <a href="#waitlist" className="btn-primary hidden !min-h-11 !px-6 sm:inline-flex">
            Join the waitlist
          </a>
          <button
            ref={toggleRef}
            type="button"
            className="inline-flex h-12 w-12 items-center justify-center rounded-full text-navy hover:bg-navy/5 lg:hidden"
            aria-expanded={open}
            aria-controls="mobile-menu"
            onClick={() => setOpen((o) => !o)}
          >
            <span className="sr-only">{open ? "Close menu" : "Open menu"}</span>
            {open ? <X size={28} aria-hidden="true" /> : <Menu size={28} aria-hidden="true" />}
          </button>
        </div>
      </div>

      <nav
        id="mobile-menu"
        aria-label="Main mobile"
        hidden={!open}
        className="border-t border-navy/10 bg-cream lg:hidden"
      >
        <ul className="container-page flex flex-col py-4">
          {navLinks.map((l) => (
            <li key={l.href}>
              <a
                href={l.href}
                onClick={() => setOpen(false)}
                className="rule flex min-h-14 items-center font-heading text-xl font-medium text-navy"
              >
                {l.label}
              </a>
            </li>
          ))}
          <li className="pt-3">
            <a href="#waitlist" onClick={() => setOpen(false)} className="btn-primary w-full">
              Join the waitlist
            </a>
          </li>
        </ul>
      </nav>
    </header>
  );
}
