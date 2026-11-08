// Nemo notifier: sends carer texts through Photon Spectrum (iMessage). One way only.
//
// Run from this folder:  bun run start   (reads the repo-root .env)
// POST /alert {"type": "...", "message": "..."} -> texts CARER_PHONE -> {"ok": true} or {"ok": false, "error"}

import { Spectrum } from "spectrum-ts";
import { imessage } from "spectrum-ts/providers/imessage";

const PORT = Number(process.env.NOTIFIER_PORT || 8100);
const CARER_PHONE = (process.env.CARER_PHONE || "").trim();

for (const name of ["SPECTRUM_PROJECT_ID", "SPECTRUM_PROJECT_SECRET", "CARER_PHONE"]) {
  if (!process.env[name]?.trim()) {
    console.error(`Missing ${name} in the repo-root .env`);
    process.exit(1);
  }
}

// One Spectrum app for the life of the service; it renews its iMessage line tokens itself.
const app = await Spectrum({
  projectId: process.env.SPECTRUM_PROJECT_ID!.trim(),
  projectSecret: process.env.SPECTRUM_PROJECT_SECRET!.trim(),
  providers: [imessage.config()],
});
const im = imessage(app);

async function sendToCarer(text: string): Promise<void> {
  const carer = await im.user(CARER_PHONE);
  const dm = await im.space.create(carer);
  await dm.send(text);
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

const server = Bun.serve({
  port: PORT,
  async fetch(req) {
    const url = new URL(req.url);
    if (req.method !== "POST" || url.pathname !== "/alert") {
      return json({ ok: false, error: "not found" }, 404);
    }

    let type = "";
    let message = "";
    try {
      const body = (await req.json()) as { type?: unknown; message?: unknown };
      type = typeof body.type === "string" ? body.type : "";
      message = typeof body.message === "string" ? body.message.trim() : "";
    } catch {
      return json({ ok: false, error: "body must be JSON" }, 400);
    }
    if (!message) return json({ ok: false, error: "message is empty" }, 400);

    const started = performance.now();
    try {
      await sendToCarer(message);
      console.log(`sent ${type || "alert"} in ${Math.round(performance.now() - started)} ms`);
      return json({ ok: true });
    } catch (err) {
      const error = err instanceof Error ? err.message : String(err);
      console.error(`send ${type || "alert"} failed: ${error}`);
      return json({ ok: false, error }, 502);
    }
  },
});

console.log(`Nemo notifier listening on http://localhost:${server.port}`);

const shutdown = async () => {
  server.stop();
  await app.stop();
  process.exit(0);
};
process.once("SIGINT", shutdown);
process.once("SIGTERM", shutdown);
