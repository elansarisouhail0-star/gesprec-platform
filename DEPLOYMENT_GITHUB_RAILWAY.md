# Deploiement GitHub + Railway

Ce projet est prepare pour etre deploye comme un seul service Railway:

- `/` sert le frontend HTML
- les routes API FastAPI restent sur le meme domaine
- PostgreSQL Railway stocke les donnees
- le dossier `/app/uploads` stocke les photos

## 1. Tester en local

```powershell
cd C:\Users\PC\Documents\Codex\2026-07-02\do\outputs\gesprec-backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Ouvrir:

```text
http://localhost:8000
http://localhost:8000/docs
```

## 2. Creer le depot GitHub

Important: ne lance pas les commandes depuis `C:\Users\PC`. Ta capture montre que ce dossier contient deja un ancien depot Git lie a `maintenance-4.0-app`. Il faut d'abord entrer dans le dossier de cette plateforme.

Dans PowerShell:

```powershell
cd "C:\Users\PC\Documents\Codex\2026-07-02\do\outputs\gesprec-backend"
git init
git rev-parse --show-toplevel
```

La commande doit afficher:

```text
C:/Users/PC/Documents/Codex/2026-07-02/do/outputs/gesprec-backend
```

Ensuite, cree un nouveau depot GitHub vide, sans README, sans `.gitignore`, sans licence. Exemple de nom: `gesprec-platform`.

Puis:

```powershell
git add .
git commit -m "Initial Gesprec platform"
git branch -M main
git remote add origin https://github.com/VOTRE_COMPTE/gesprec-platform.git
git push -u origin main
```

Le fichier `.gitignore` exclut deja `.env`, `.venv`, la base SQLite locale et les uploads.

Si Git repond `remote origin already exists`, tu n'es probablement pas dans le bon dossier ou tu as reutilise un depot existant. Verifie avec:

```powershell
git rev-parse --show-toplevel
git remote -v
```

Si le depot GitHub contient deja un README ou des commits, le push peut etre rejete avec `fetch first`. Le plus simple pour ce projet est d'utiliser un depot GitHub vide.

## 3. Creer le projet Railway

1. Aller sur Railway.
2. Creer un nouveau projet.
3. Choisir `Deploy from GitHub repo`.
4. Selectionner le depot `gesprec-platform`.
5. Railway detectera le `Dockerfile`.
6. Ajouter un service PostgreSQL dans le meme projet.

## 4. Variables Railway

Dans le service web Railway, ajouter:

```text
ENV=production
APP_NAME=Gesprec API
JWT_SECRET=remplacer_par_un_secret_long_et_unique
JWT_EXPIRES_MINUTES=480
SEED_DEFAULT_USERS=true
UPLOAD_DIR=/app/uploads
MAX_UPLOAD_MB=8
WHATSAPP_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_TLS=true
```

Pour `DATABASE_URL`, utiliser la variable fournie par le PostgreSQL Railway. Le backend accepte les formats Railway `postgres://...` et `postgresql://...`.

Comme le frontend et l'API sont servis par le meme domaine Railway, `CORS_ORIGINS` n'est pas indispensable. Si tu separes plus tard frontend et backend, ajoute le domaine frontend dans `CORS_ORIGINS`.

## 5. Domaine public

Dans Railway:

1. Ouvrir le service web.
2. Aller dans `Settings` puis `Networking`.
3. Generer un domaine Railway.

Tu obtiendras une URL du type:

```text
https://gesprec-platform-production.up.railway.app
```

Cette URL donnera acces a la plateforme depuis plusieurs appareils.

## 6. Photos et fichiers

Pour que les photos restent apres redeploiement, ajouter un volume Railway monte sur:

```text
/app/uploads
```

Sans volume, les photos peuvent etre perdues lors d'un redeploiement. Pour une exploitation plus robuste, utiliser ensuite un stockage externe comme S3, Cloudinary ou Azure Blob.

## 7. Comptes de depart

Au premier lancement, le backend cree:

```text
hse@gesprec.local              Hse12345!
chef@gesprec.local             Chef12345!
etablissement@gesprec.local    Etab12345!
coordination@gesprec.local     Coord12345!
traitement@gesprec.local       Trait12345!
```

Apres creation des vrais comptes, mettre:

```text
SEED_DEFAULT_USERS=false
```

Puis redeployer.

## 7 bis. QR code et WhatsApp

Le QR code unique est disponible ici:

```text
https://VOTRE_DOMAINE_RAILWAY/qr/ateliers
```

Le declarant scanne ce QR code, arrive directement sur le formulaire, puis choisit l'atelier cible.

Pour l'envoi automatique des messages WhatsApp, il faut renseigner les identifiants WhatsApp Cloud API:

```text
WHATSAPP_TOKEN=votre_token_meta
WHATSAPP_PHONE_NUMBER_ID=votre_phone_number_id
```

Sans ces variables, Gesprec conserve les traces et genere des liens `wa.me` dans l'historique, mais l'envoi automatique ne part pas.

Configuration rapide:

1. Dans Meta for Developers, ouvrir l'application WhatsApp Cloud API.
2. Copier le `Phone number ID` du numero emetteur WhatsApp.
3. Generer ou copier un token d'acces WhatsApp valide.
4. Dans Railway, ouvrir le service web `gesprec-platform`, puis l'onglet `Variables`.
5. Ajouter `WHATSAPP_TOKEN` avec le token Meta.
6. Ajouter `WHATSAPP_PHONE_NUMBER_ID` avec le Phone number ID Meta.
7. Cliquer sur `Deploy` ou attendre le redeploiement automatique.
8. Dans Gesprec, se connecter en Responsable QSSE, ouvrir `Utilisateurs`, saisir un numero de test au format `+212...`, puis cliquer sur `Envoyer test WhatsApp`.

Les numeros des responsables doivent etre saisis dans `Utilisateurs` au format international:

```text
+212600000000
```

Pour l'envoi d'emails de secours, il faut un vrai compte SMTP. Par exemple le SMTP de votre entreprise, Gmail avec mot de passe d'application, Brevo, Mailgun ou SendGrid.

Variables a renseigner:

```text
SMTP_HOST=smtp.votre-fournisseur.com
SMTP_PORT=587
SMTP_USERNAME=votre_login
SMTP_PASSWORD=votre_mot_de_passe_smtp
SMTP_FROM=gesprec@votre-domaine.com
SMTP_TLS=true
```

Le QSSE peut tester l'envoi email et declencher les rappels WhatsApp J-1 depuis l'onglet `Utilisateurs`.

## 8. Verification apres deploiement

Tester:

```text
https://VOTRE_DOMAINE_RAILWAY/health
https://VOTRE_DOMAINE_RAILWAY/docs
https://VOTRE_DOMAINE_RAILWAY/
```

Le declarant utilise `/` sans authentification.

Les profils internes utilisent leur email et mot de passe.
