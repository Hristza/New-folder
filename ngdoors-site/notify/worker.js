import { EmailMessage } from "cloudflare:email";

// RFC 2047 so Cyrillic subjects survive every mail client.
const word = (s) => "=?UTF-8?B?" + b64(s) + "?=";
const b64 = (s) => btoa(String.fromCharCode(...new TextEncoder().encode(s)));

export function mime(from, to, r) {
  const body = [
    "Ново запитване от сайта ngdoors",
    "",
    "Име: " + r.name,
    "Контакт: " + r.contact,
    r.topic ? "Тема: " + r.topic : null,
    r.page ? "Страница: " + r.page : null,
    "",
    r.message || "(без съобщение)",
    "",
    "Всички запитвания: https://ngdoors.pages.dev/admin/",
  ].filter((l) => l !== null).join("\r\n");
  return [
    "From: " + word("NG Doors сайт") + " <" + from + ">",
    "To: " + to,
    "Subject: " + word("Ново запитване: " + String(r.name).slice(0, 60)),
    "Date: " + new Date().toUTCString(),
    "Message-ID: <" + crypto.randomUUID() + "@hristoforstudio.com>",
    "MIME-Version: 1.0",
    "Content-Type: text/plain; charset=UTF-8",
    "Content-Transfer-Encoding: base64",
    "",
    b64(body).replace(/.{76}/g, "$&\r\n"),
  ].join("\r\n");
}

export default {
  async fetch(req, env) {
    if (req.method !== "POST") return new Response("POST only", { status: 405 });
    if (!env.HOOK_SECRET || req.headers.get("x-hook-secret") !== env.HOOK_SECRET)
      return new Response("forbidden", { status: 403 });
    const { record: r } = await req.json().catch(() => ({}));
    if (!r?.name || !r?.contact) return new Response("no record", { status: 400 });
    const sent = [], failed = [];
    for (const to of env.TO.split(",").map((s) => s.trim()).filter(Boolean)) {
      // ponytail: an unverified destination throws; skip it so the others still get the mail
      try { await env.MAIL.send(new EmailMessage(env.FROM, to, mime(env.FROM, to, r))); sent.push(to); }
      catch (e) { failed.push(to + ": " + String(e).slice(0, 120)); }
    }
    return Response.json({ ok: sent.length > 0, sent, failed });
  },
};
