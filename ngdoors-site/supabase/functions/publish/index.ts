// "Публикувай промените": rebuild and redeploy the public site from what she saved.
//
// Only an admin can trigger it. The function holds the one secret the browser must
// never see (a Cloudflare Pages deploy hook URL), checks the caller is in public.admins,
// throttles to one publish a minute, and calls the hook. Vercel then pulls the repo,
// runs build.py + check.py and deploys. A failed build leaves the old site up.
//
// Secrets (supabase secrets set ...):
//   DEPLOY_HOOK  Cloudflare Pages deploy hook URL for the production branch
//   SITE_ORIGINS comma list of origins allowed to call this, e.g. https://ngdoors.pages.dev
import { createClient } from "npm:@supabase/supabase-js@2.117.2";

const env = (k: string) => Deno.env.get(k) ?? "";
const ORIGINS = env("SITE_ORIGINS").split(",").map((s) => s.trim()).filter(Boolean);

function cors(req: Request): Record<string, string> {
  const o = req.headers.get("Origin") ?? "";
  return {
    "Access-Control-Allow-Origin": ORIGINS.includes(o) ? o : ORIGINS[0] ?? "",
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Vary": "Origin",
  };
}

function reply(req: Request, status: number, body: Record<string, unknown>) {
  return new Response(JSON.stringify(body), {
    status, headers: { ...cors(req), "Content-Type": "application/json" },
  });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: cors(req) });
  if (req.method !== "POST") return reply(req, 405, { error: "Само POST." });
  const origin = req.headers.get("Origin");
  if (origin && !ORIGINS.includes(origin)) return reply(req, 403, { error: "Непозволен адрес." });

  const auth = req.headers.get("Authorization") ?? "";
  if (!auth.startsWith("Bearer ")) return reply(req, 401, { error: "Влезте отново." });

  // Acts AS the caller, so row-level security applies to every query below.
  const sb = createClient(env("SUPABASE_URL"), env("SUPABASE_ANON_KEY"), {
    global: { headers: { Authorization: auth } },
    auth: { persistSession: false },
  });
  const { data: u, error: ue } = await sb.auth.getUser(auth.slice(7));
  if (ue || !u?.user) return reply(req, 401, { error: "Сесията е изтекла. Влезте отново." });
  const { data: isAdmin, error: ae } = await sb.rpc("is_admin");
  if (ae || isAdmin !== true) return reply(req, 403, { error: "Нямате права за публикуване." });

  const { data: last } = await sb.from("publish_log").select("requested_at")
    .order("requested_at", { ascending: false }).limit(1);
  if (last?.[0] && Date.now() - Date.parse(last[0].requested_at) < 60_000) {
    return reply(req, 429, { error: "Току-що публикувахте. Изчакайте минута." });
  }

  if (!env("DEPLOY_HOOK")) return reply(req, 500, { error: "Публикуването не е настроено (DEPLOY_HOOK)." });
  let ok = false, detail = "";
  try {
    const r = await fetch(env("DEPLOY_HOOK"), { method: "POST" });
    ok = r.status >= 200 && r.status < 300;
    detail = ok ? "started" : `deploy hook ${r.status}: ${(await r.text()).slice(0, 300)}`;
  } catch (e) {
    detail = "deploy hook unreachable: " + String(e).slice(0, 300);
  }
  await sb.from("publish_log").insert({ ok, detail });
  return ok
    ? reply(req, 200, { ok: true })
    : reply(req, 502, { error: "Сървърът за публикуване не отговори. Опитайте след малко." });
});
