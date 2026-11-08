import { NextResponse } from "next/server";

/**
 * Placeholder waitlist handler.
 *
 * TODO: connect to a real service before launch (e.g. Resend audience, Airtable,
 * Google Sheets, Formspree, or a database). Right now it only validates the
 * input and logs it to the server console: sign-ups are NOT stored.
 */
export async function POST(request: Request) {
  let body: { name?: unknown; email?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid JSON" }, { status: 400 });
  }

  const name = typeof body.name === "string" ? body.name.trim().slice(0, 200) : "";
  const email = typeof body.email === "string" ? body.email.trim().slice(0, 320) : "";
  if (!name || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return NextResponse.json({ ok: false, error: "Name and a valid email are required" }, { status: 422 });
  }

  // TODO: replace this log with a real write.
  console.log("[waitlist] new sign-up:", { name, email });

  return NextResponse.json({ ok: true });
}
