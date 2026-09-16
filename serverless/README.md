# Bouton « Régénérer le brief » (serverless, 0 €)

Ce dossier contient un mini-service qui régénère « Le Brief » à la demande, en un
clic depuis l'e-mail. Il déclenche le workflow GitHub `brief.yml` (qui refabrique
le brief **et** le renvoie par e-mail).

## Pourquoi un service externe ?

Le bouton ne peut pas appeler GitHub directement : cela exposerait le jeton
d'accès (PAT) dans l'e-mail, donc à quiconque le reçoit. Le service serverless
garde le jeton **chez lui** ; l'e-mail ne contient qu'une **URL secrète** sans
aucun secret GitHub.

```
E-mail (bouton) ──GET──▶ service serverless ──API GitHub──▶ workflow brief.yml
                          (détient le PAT)                    (régénère + envoie)
```

## Ce dont tu as besoin

1. **Un jeton GitHub fine-grained** (gratuit) :
   - GitHub → Settings → Developer settings → *Fine-grained tokens* → *Generate new token*.
   - *Repository access* : seulement `sgiraud70-creator/daily-brief-public`.
   - *Permissions* → *Actions* : **Read and write**. (Rien d'autre.)
   - Copie le jeton (`github_pat_…`). ⚠️ Tu ne le reverras plus : garde-le le temps
     de le coller dans le service ci-dessous, ne le mets JAMAIS dans le dépôt ni
     dans le mail.
   - Tu peux réutiliser le même jeton que cron-job.org, ou en créer un dédié
     (recommandé : révocable séparément).
2. **Un secret d'URL** : une longue chaîne aléatoire, p. ex. générée par
   `openssl rand -hex 24` (ou n'importe quel générateur de mot de passe). On
   l'appelle `REGEN_SECRET`.

## Déploiement A — Cloudflare Workers (recommandé)

Gratuit (100 000 requêtes/jour), durable, sans carte bancaire.

1. Crée un compte sur <https://dash.cloudflare.com> (gratuit).
2. *Workers & Pages* → *Create* → *Create Worker* → donne un nom
   (p. ex. `brief-regenerate`) → *Deploy*.
3. *Edit code* : colle tout le contenu de [`regenerate.js`](regenerate.js) puis
   *Deploy*.
4. *Settings* → *Variables and Secrets* → ajoute **deux** secrets (type *Secret*,
   pas *Text*) :
   - `GH_PAT` = ton jeton GitHub.
   - `REGEN_SECRET` = ta chaîne aléatoire.
   Puis *Deploy* à nouveau.
5. Ton URL est `https://brief-regenerate.<ton-sous-domaine>.workers.dev`.
   L'**URL complète du bouton** est :
   ```
   https://brief-regenerate.<ton-sous-domaine>.workers.dev/?t=<REGEN_SECRET>
   ```

## Déploiement B — Val.town (alternative)

1. Compte gratuit sur <https://val.town>.
2. *New* → *HTTP val*. Colle `regenerate.js` mais remplace la dernière ligne
   `export default { fetch: handle };` par le bloc Val.town indiqué en commentaire
   en bas du fichier.
3. *Environment Variables* : ajoute `GH_PAT` et `REGEN_SECRET`.
4. Copie l'URL du val ; l'URL du bouton est `…?t=<REGEN_SECRET>`.

## Dernière étape — activer le bouton dans le mail

Ajoute l'URL complète (avec `?t=…`) comme **secret GitHub** du dépôt :

- GitHub → dépôt → *Settings* → *Secrets and variables* → *Actions* → *New
  repository secret*.
- Nom : `REGEN_URL`
- Valeur : `https://…workers.dev/?t=<REGEN_SECRET>`

À la prochaine génération, l'e-mail affichera le bouton **« Régénérer le brief »**.
Tant que `REGEN_URL` n'est pas défini, le bouton n'apparaît pas (aucune erreur).

## Test

Ouvre l'URL complète dans un navigateur : tu dois voir une page de confirmation.
Clique « Régénérer mon brief » → le workflow `brief.yml` démarre (onglet *Actions*)
et l'e-mail arrive quelques minutes plus tard.

## Sécurité

- Le PAT ne quitte jamais le service serverless.
- L'action n'est déclenchée que par un **POST** (le clic sur le bouton de la page
  de confirmation) : les aperçus/scanners de liens des messageries font des GET,
  ils ne peuvent donc pas déclencher un envoi par accident.
- Si l'URL secrète fuite, révoque-la en changeant `REGEN_SECRET` (service) **et**
  `REGEN_URL` (secret GitHub). Le PAT, lui, reste protégé.
