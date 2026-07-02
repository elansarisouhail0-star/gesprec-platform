# Gesprec Backend

Backend FastAPI pour mettre en exploitation la plateforme "Gestion Precurseurs - EMIC/TMLC".

Il couvre:

- authentification JWT
- roles authentifies: hse, chef_technicentre_tmlc, chef_etablissement, coordination, traitement
- declaration publique sans compte declarant
- creation des declarations
- workflow complet: nouvelle -> analyse -> affecte -> planifie -> realisee -> cloture
- notifications par audience
- historique/audit par declaration
- upload de photos
- statistiques dashboard
- PostgreSQL avec Docker, SQLite possible en local

## Demarrage local rapide

```powershell
cd outputs\gesprec-backend
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Si le serveur affiche une erreur `password cannot be longer than 72 bytes` au demarrage, force la version compatible de bcrypt:

```powershell
.\.venv\Scripts\python.exe -m pip install bcrypt==4.2.1 --force-reinstall
python -m uvicorn app.main:app --reload
```

API: `http://localhost:8000`

Documentation interactive: `http://localhost:8000/docs`

Interface frontend: `http://localhost:8000`

## Demarrage avec Docker

```powershell
cd outputs\gesprec-backend
copy .env.example .env
docker compose up --build
```

## Comptes demo crees au premier lancement

| Role | Email | Mot de passe |
| --- | --- | --- |
| Responsable HSE | hse@gesprec.local | Hse12345! |
| Chef de technicentre TMLC | chef@gesprec.local | Chef12345! |
| Chef d'etablissement | etablissement@gesprec.local | Etab12345! |
| Coordination | coordination@gesprec.local | Coord12345! |
| Traitement principal | traitement@gesprec.local | Trait12345! |
| Traitement 1 | traitement1@gesprec.local | Trait112345! |
| Traitement 2 | traitement2@gesprec.local | Trait212345! |
| Traitement 3 | traitement3@gesprec.local | Trait312345! |

Change ces comptes avant tout deploiement reel. Aucun compte declarant n'est cree: le declarant depose une declaration sans authentification.

## Endpoints principaux

| Methode | Route | Role |
| --- | --- | --- |
| POST | `/auth/login` | public |
| GET | `/auth/users` | HSE |
| POST | `/auth/users` | HSE |
| PATCH | `/auth/users/{id}` | HSE |
| POST | `/auth/change-password` | connecte |
| POST | `/declarations` | public, sans authentification declarant |
| GET | `/declarations` | HSE, chef technicentre TMLC, coordination, traitement |
| GET | `/declarations/{id}` | HSE, chef technicentre TMLC, coordination, traitement |
| POST | `/declarations/{id}/photos` | public apres creation d'une declaration |
| POST | `/declarations/{id}/analyse` | HSE, chef technicentre TMLC, coordination |
| POST | `/declarations/{id}/affectation` | HSE, chef technicentre TMLC, coordination |
| POST | `/declarations/{id}/planification` | traitement |
| POST | `/declarations/{id}/intervention` | traitement |
| POST | `/declarations/{id}/verification` | HSE, chef technicentre TMLC, coordination |
| GET | `/notifications` | connecte |
| POST | `/notifications/{id}/read` | connecte |
| GET | `/dashboard/stats` | HSE, chef technicentre TMLC, coordination, traitement, chef d'etablissement |
| GET | `/qr/ateliers` | public |
| GET | `/qr/atelier.svg?name=Atelier%20HITACHI` | public |
| GET | `/system/email-status` | HSE |
| POST | `/system/email-test` | HSE |

Le Chef d'etablissement est volontairement limite au dashboard. Il ne peut pas lister, ouvrir, modifier ou traiter les declarations.

## Exemple login

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=hse@gesprec.local&password=Hse12345!"
```

## Exemple creation declaration

```bash
curl -X POST http://localhost:8000/declarations \
  -H "Content-Type: application/json" \
  -d '{
    "atelier": "Atelier HITACHI",
    "category": "Securite",
    "description": "Protection absente sur une zone mobile",
    "gravity": "important",
    "anonymous": false,
    "reporter_name": "Ali Exemple",
    "reporter_service": "Production",
    "location": "Presse 3"
  }'
```

## Brancher le HTML actuel

Dans ton fichier HTML, ajoute un petit client API et remplace les fonctions qui modifient `state.declarations`.

```javascript
const API_BASE = "http://localhost:8000";
let token = localStorage.getItem("gesprec_token");

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (!(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(API_BASE + path, {...options, headers});
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function login(email, password) {
  const body = new URLSearchParams({username: email, password});
  const data = await api("/auth/login", {
    method: "POST",
    headers: {"Content-Type": "application/x-www-form-urlencoded"},
    body
  });
  token = data.access_token;
  localStorage.setItem("gesprec_token", token);
  return data.user;
}
```

Ensuite:

- `submitDeclaration()` appelle `POST /declarations`
- `loadData()` appelle `GET /declarations`, `GET /notifications`, `GET /dashboard/stats`
- `doAnalyse()` appelle `POST /declarations/{id}/analyse`
- `doAffectation()` appelle `POST /declarations/{id}/affectation`
- `doPlanification()` appelle `POST /declarations/{id}/planification`
- `doIntervention()` appelle `POST /declarations/{id}/intervention`
- `doVerification()` appelle `POST /declarations/{id}/verification`

## Production checklist

- Changer `JWT_SECRET`.
- Changer tous les mots de passe demo.
- Mettre `SEED_DEFAULT_USERS=false` apres creation des vrais comptes.
- Utiliser HTTPS derriere Nginx/Caddy/Traefik.
- Sauvegarder PostgreSQL et le dossier uploads.
- Ajouter Alembic avant la premiere evolution de schema.
- Ajouter un service email pour les deadlines SLA.

## QR codes ateliers

Page imprimable:

```text
http://localhost:8000/qr/ateliers
```

Chaque QR ouvre le formulaire declarant avec l'atelier deja selectionne.

## Emails SMTP

L'envoi email est fonctionnel uniquement si ces variables sont configurees:

```text
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_TLS=true
```

Sans SMTP, l'application conserve l'affectation mais indique dans l'historique que l'email n'a pas ete envoye.

## Deploiement GitHub + Railway

Le guide complet est ici: [DEPLOYMENT_GITHUB_RAILWAY.md](DEPLOYMENT_GITHUB_RAILWAY.md)
