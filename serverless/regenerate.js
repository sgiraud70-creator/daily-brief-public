/**
 * « Le Brief » — régénération à la demande (fonctionnalité #1, option B).
 *
 * Petit service serverless qui déclenche le workflow GitHub `brief.yml`
 * (régénère puis renvoie le brief par e-mail). Le bouton du mail ouvre l'URL
 * secrète de ce service ; le jeton GitHub (PAT) reste UNIQUEMENT ici, jamais
 * dans le mail ni dans le dépôt.
 *
 * Déploiement : Cloudflare Workers (gratuit). Variante Val.town en bas.
 * Voir serverless/README.md pour les étapes détaillées.
 *
 * Variables d'environnement à définir sur la plateforme (jamais dans le code) :
 *   GH_PAT        jeton GitHub « fine-grained », permission Actions: Read and write,
 *                 limité au dépôt daily-brief-public.
 *   REGEN_SECRET  chaîne secrète arbitraire (≥ 24 caractères aléatoires). Doit être
 *                 identique au paramètre `?t=` de l'URL mise dans le mail.
 *
 * Sécurité :
 *   - L'action réelle (déclenchement) n'est faite que sur requête POST : les
 *     scanners de liens des messageries font des GET, ils ne peuvent donc pas
 *     déclencher un envoi par accident. Le clic sur le bouton ouvre d'abord une
 *     page de confirmation (GET) qui, elle, poste le formulaire.
 *   - Sans jeton correct → 403, aucune fuite d'information.
 */

const OWNER = "sgiraud70-creator";
const REPO = "daily-brief-public";
const WORKFLOW = "brief.yml";
const REF = "main";

// Comparaison à durée constante (évite de distinguer un jeton par le temps de réponse)
function safeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function page(status, title, message, formToken) {
  const bouton = formToken
    ? `<form method="POST" action="?t=${encodeURIComponent(formToken)}" style="margin-top:28px;">
         <button type="submit"
           style="background:#c9a24b;color:#141418;border:0;border-radius:8px;
                  padding:14px 26px;font-size:16px;font-weight:600;cursor:pointer;
                  font-family:Arial,Helvetica,sans-serif;">Régénérer mon brief</button>
       </form>`
    : "";
  const body = `<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title} · Le Brief</title></head>
<body style="margin:0;background:#141418;color:#eae7df;
  font-family:Arial,Helvetica,sans-serif;display:flex;min-height:100vh;
  align-items:center;justify-content:center;text-align:center;">
  <div style="max-width:460px;padding:40px 28px;">
    <div style="font-family:Georgia,'Times New Roman',serif;font-style:italic;
      font-size:30px;color:#c9a24b;">Le Brief</div>
    <h1 style="font-size:22px;margin:22px 0 10px;font-weight:600;">${title}</h1>
    <p style="font-size:16px;line-height:1.5;color:#b8b4ab;margin:0;">${message}</p>
    ${bouton}
  </div>
</body></html>`;
  return new Response(body, {
    status,
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}

async function handle(request, env) {
  const url = new URL(request.url);
  const token = url.searchParams.get("t") || "";

  if (!env.REGEN_SECRET || !safeEqual(token, env.REGEN_SECRET)) {
    return page(403, "Accès refusé", "Ce lien est invalide ou a expiré.");
  }

  // GET → page de confirmation (sûre : n'exécute rien)
  if (request.method !== "POST") {
    return page(200, "Régénérer ton brief ?",
      "Cela relance la fabrication du brief du jour et te le renvoie par e-mail dans quelques minutes.",
      token);
  }

  // POST → déclenche le workflow GitHub
  const resp = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.GH_PAT}`,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "le-brief-regenerate",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: REF }),
    }
  );

  if (resp.status === 204) {
    return page(200, "C'est parti !",
      "Ton brief est en cours de régénération. Tu le recevras par e-mail dans quelques minutes.");
  }
  const detail = (await resp.text()).slice(0, 200);
  return page(502, "Échec du déclenchement",
    `GitHub a répondu ${resp.status}. Réessaie plus tard.<br><small>${detail}</small>`);
}

// --- Cloudflare Workers ------------------------------------------------------
export default { fetch: handle };

// --- Val.town (alternative) --------------------------------------------------
// Sur Val.town, remplace la ligne ci-dessus par :
//   export default async (req) => handle(req, {
//     GH_PAT: Deno.env.get("GH_PAT"),
//     REGEN_SECRET: Deno.env.get("REGEN_SECRET"),
//   });
