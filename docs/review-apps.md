# Scalingo Review Apps

Une review app éphémère est déployée à la demande sur Scalingo pour une PR ouverte, côté back-end **et** côté front-end, avec crosslink automatique des URLs.

## Prérequis

### Côté Scalingo

Rien à faire : les deux apps parents `mobilic-staging` et `mobilic-api-staging` ont déjà l'intégration GitHub, la feature Review Apps est disponible dès lors. L'auto-création à l'ouverture de PR doit rester désactivée (état par défaut, à vérifier avec `scalingo --app <parent> integration-link` : `Automatic deployment of review apps: ✘`) : `.scripts/review-app.sh` pilote la création manuellement.

Le déploiement continu de `master` vers staging passe par CircleCI (voir `.circleci/config.yml`), indépendant de l'intégration Scalingo — donc pas impacté.

### Côté GitHub (une fois)

- Ajouter le secret `SCALINGO_API_TOKEN` dans les secrets de chaque repo (`Settings > Secrets and variables > Actions`). Recommandé : générer ce token depuis un **compte de service Scalingo dédié**, ajouté comme `Collaborator` (pas `Owner`) sur les 2 apps parents uniquement. Scalingo ne propose pas de scoping au niveau du token : c'est le compte qui borne les droits.
- Créer le label `needs-review-app` dans les 2 repos.

### Pour un usage local du script

- [`gh`](https://cli.github.com/) installée et authentifiée (`gh auth login` ou `GH_TOKEN`).
- [`scalingo`](https://cli.scalingo.com/) installée et authentifiée (`scalingo login --api-token ...`).
- Le repo `mobilic` (front-end) checkouté sur la branche à tester : le script vit dans `.scripts/review-app.sh` côté front-end.

### Pour une PR liée (recommandé)

- Utiliser le **même nom de branche** dans les 2 repos si la feature touche back-end et front-end. Sinon le matching automatique ne se fait pas et la partie manquante retombe sur staging.

## Déclenchement

**Opt-in via label GitHub** : ajouter le label `needs-review-app` sur une PR (mobilic ou mobilic-api) déclenche le workflow `.github/workflows/scalingo-review-app.yml`.

Alternatives :
- **Manuel via UI GitHub** : `Actions > Scalingo review app > Run workflow` (input : numéro de PR).
- **Local** : `bash .scripts/review-app.sh` (repo front, `gh` + `scalingo` CLIs authentifiés).

Cleanup : Scalingo détruit la review app à la fermeture / merge de la PR (natif). Le workflow n'a rien à faire.

## Cas back-only ou front-only

Le script cherche la PR sibling dans l'autre repo par **nom de branche exact**. Si absente, la partie manquante pointe vers l'app parent staging :

| PR front | PR back | Front review app | Back review app | Bindings                                       |
| -------- | ------- | ---------------- | --------------- | ---------------------------------------------- |
| oui      | oui     | oui              | oui             | crosslink complet                              |
| oui      | non     | oui              | non             | front → `mobilic-api-staging`                  |
| non      | oui     | non              | oui             | back `FRONTEND_URL` = `mobilic-staging`        |

## Configuration de la review app

- **Données** : la DB de la review app démarre vide puis est peuplée par `flask seed` au premier déploiement (mêmes scénarios qu'en local). Compte admin par défaut : `busy.admin@test.com` (voir `app/seed/helpers.py` pour le mot de passe). Aucune donnée prod n'est copiée.
- **Emails et Brevo désactivés par défaut** (`DISABLE_EMAIL=1`, `BREVO_API_KEY=""`, `MAILJET_API_KEY=""`). Pour tester un envoi de mail ou la sync Brevo, écraser à chaud via `scalingo --app <review-app> env-set DISABLE_EMAIL=0 BREVO_API_KEY=xxx` (ou depuis le dashboard). Les variables sont lues au runtime, Scalingo redéploie automatiquement.

## Limitations connues

- **OAuth FranceConnect / AgentConnect** : les flows OAuth ne fonctionnent pas sur une review app car les redirect URIs doivent être whitelistées côté provider et ne peuvent pas l'être pour une URL éphémère. Tester ces parcours en local ou sur staging.
