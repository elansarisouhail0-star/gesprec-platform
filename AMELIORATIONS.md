# Ameliorations recommandees pour la plateforme Gesprec

## Priorite 1 - Mise en exploitation reelle

1. Remplacer le stockage local par une base centralisee.
   Le prototype garde les declarations cote navigateur. En production, il faut une base PostgreSQL avec sauvegardes, historique et audit.

2. Remplacer le changement de role manuel par une vraie authentification pour les profils internes.
   Le declarant reste sans compte: il accede uniquement au formulaire public de declaration.

3. Verrouiller le workflow par role.
   Public: creer une declaration. HSE/Chef de technicentre TMLC/Coordination: analyser, affecter, verifier. Traitement: planifier et realiser. Chef d'etablissement: consulter uniquement le tableau de bord.

4. Gerer les pieces jointes proprement.
   Les photos ne doivent pas etre stockees en base64 dans le navigateur. Elles doivent etre uploadees, controlees, stockees, puis liees a la declaration.

5. Ajouter un journal d'audit non modifiable.
   Chaque action importante doit garder date, acteur, ancien statut, nouveau statut et commentaire.

## Priorite 2 - Qualite operationnelle

1. Notifications email et rappels SLA.
   Envoyer automatiquement un email au responsable affecte et relancer avant/apres deadline.

2. Recherche et filtres avances.
   Filtres par atelier, gravite, statut, periode, responsable, retard, categorie.

3. Export fiable.
   Generer les exports PDF/Excel cote serveur pour garantir le meme rendu et conserver les preuves.

4. Indicateurs de performance.
   Temps moyen de cloture, taux de non-conformite, declarations critiques, retards SLA, top zones a risque.

5. Mode QR par atelier.
   Un QR code signe peut preselectionner l'atelier et eviter les erreurs de saisie.

## Priorite 3 - Securite et maintenance

1. HTTPS obligatoire, secrets hors code, rotation des mots de passe.
2. Sauvegarde quotidienne de PostgreSQL et des fichiers uploades.
3. Migration de schema avec Alembic avant les changements de base.
4. Tests automatises sur le workflow complet.
5. Journalisation des erreurs et monitoring serveur.

## Evolution frontend conseillee

Le HTML actuel peut rester comme premiere interface, mais il faut progressivement remplacer:

- `state.declarations` par `GET /declarations`
- `submitDeclaration()` par `POST /declarations`
- les actions `doAnalyse`, `doAffectation`, `doPlanification`, `doIntervention`, `doVerification` par les endpoints workflow
- `state.notifications` par `GET /notifications`
- les stats dashboard par `GET /dashboard/stats`

Cela permet de garder le design existant tout en passant d'une maquette locale a une vraie application multi-utilisateurs.
