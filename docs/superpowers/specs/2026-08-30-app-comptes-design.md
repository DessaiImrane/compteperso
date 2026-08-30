# App Comptes — Design

Date : 2026-08-30

## Contexte

Suivi actuel réparti sur 3 outils : BankPerfect (`.bp`, format propriétaire chiffré, non exploitable directement), un fichier Excel (`Compte.xlsx`, un onglet par mois depuis 2021, ~170 onglets), et une saisie manuelle ligne par ligne pour 3 banques (Boursorama = compte perso, HelloBank = budget mensuel famille, La Banque Postale = compte réel subdivisé virtuellement en plusieurs enveloppes : Économie, Maison, Vacances, Enfant1, Enfant2, Impôt, Zakaate...).

Le processus hebdo/mensuel actuel : se connecter à chaque banque, pointer/saisir chaque opération dans le bon outil, comparer le total pointé au total affiché par la banque pour détecter les écarts, reporter certains totaux dans l'Excel à la main. Chronophage et redondant.

## Décision de périmètre

Nouvelle application unique qui **remplace** BankPerfect et l'Excel. Pas de migration/import de l'historique existant — démarrage à blanc, l'utilisateur ressaisit ses comptes/données de départ via l'interface. Pas d'API bancaire (contrainte volontaire) : les opérations arrivent par copier-coller du texte affiché sur le site de chaque banque.

## Stack & packaging

- Backend : FastAPI + HTMX (rendu serveur, pas de framework JS lourd). SQLAlchemy + SQLite.
- Graphiques : Chart.js via CDN, alimenté par les données JSON d'un endpoint dédié.
- Lancement : script (`.command` ou `.app` via Platypus) déposé dans `/Applications`, qui démarre uvicorn en local puis ouvre une fenêtre **pywebview** pointée sur `http://127.0.0.1:<port>` (pas de barre d'adresse, look natif, pas de dépendance à un navigateur installé).
- Fermeture : la fermeture de la fenêtre pywebview déclenche l'arrêt propre du serveur uvicorn (pas de process résiduel).
- Backup : après arrêt du serveur (DB non verrouillée), copie du fichier SQLite vers un dossier de backup configurable (chemin en base ou config, ex. un dossier Google Drive), nommée avec timestamp pour garder plusieurs versions.
- Stockage DB : `~/Library/Application Support/ComptesApp/` — hors dossier synchronisé (Google Drive) pour éviter toute corruption par écriture concurrente pendant que l'app tourne. Le backup post-fermeture est la seule écriture vers un dossier synchronisé.

## Modèle de données

- **Banque** : id, nom. Entité banque réelle (Boursorama / HelloBank / La Banque Postale). Sert de racine pour le rapprochement total banque vs total pointé.
- **CompteVirtuel** : id, banque_id (FK), nom, actif. Boursorama = 1 compte virtuel unique (compte réel). HelloBank = 1 compte (budget familial). La Poste = N comptes, librement créés/renommés/archivés depuis l'interface (pas de liste figée en dur).
- **Tag** : id, nom. Libre, créé à la volée en pointant une ligne (pas de configuration préalable).
- **Transaction** : id, date, compte_virtuel_id (FK), montant (signé : positif = argent reçu, négatif = argent dépensé), libellé, pointé (bool), tags (relation many-to-many), créancier_id (FK nullable — renseigné si la ligne a été générée automatiquement par un créancier), transfer_link_id (nullable — lie les deux lignes d'un virement interne pour navigation croisée entre les deux comptes concernés).
- **Créancier** (opération programmée / récurrente) : id, nom, montant par défaut, tags par défaut, compte_source_id (FK), compte_destination_id (FK nullable — vide = destinataire externe), date_prochaine_echeance, récurrence (aucune / mensuelle / hebdomadaire / custom) avec fin (jamais / date de fin / nombre d'occurrences), actif.
- **RapprochementSession** (historique/audit) : id, banque_id, date, total_banque_pointe, total_banque_a_venir, total_pointe_calcule, écart.
- **MappingParsing** (calibrage par banque) : banque_id, définition des colonnes (position/regex → date / libellé / montant) pour interpréter le texte collé, réutilisée à chaque session.
- **TagLearning** : association apprise libellé → tag(s), alimentée à chaque validation manuelle, utilisée pour pré-suggérer les tags lors des prochains collages.

Duplication rapide : un bouton "dupliquer" sur une ligne Transaction ou sur un Créancier pré-remplit un nouveau formulaire avec les mêmes champs (compte, montant, tags) — date remise à aujourd'hui et pointé=false pour une transaction dupliquée.

## Workflow de rapprochement (hebdo/mensuel, par banque)

1. Écran "Rapprochement" → sélection de la banque.
2. Collage du texte copié depuis le site de la banque dans une zone de texte.
3. Parsing via le `MappingParsing` calibré pour cette banque (au tout premier usage, l'utilisateur indique quelle colonne correspond à quoi ; le mapping est mémorisé et réutilisé ensuite, ajustable si le site change).
4. **Écran de contrôle (staging)** : les lignes parsées sont affichées et éditables avant toute écriture réelle.
   - Dédup automatique : une ligne déjà présente en base (même date + montant + libellé sur le compte) est **verrouillée** (grisée, exclue de la validation), avec un bouton pour la **déverrouiller** si ce n'est pas réellement un doublon.
   - Tags pré-suggérés via `TagLearning` (association apprise sur les libellés similaires déjà validés) ; sinon saisie manuelle, ce qui alimente l'apprentissage pour la prochaine fois.
   - Compte virtuel à assigner par ligne (pré-rempli automatiquement si la banque n'a qu'un seul compte virtuel).
5. Bouton "Valider" → écriture réelle des lignes non verrouillées en tant que Transactions pointées. Les lignes verrouillées (dédup) sont ignorées.
6. **Ajout manuel indépendant** : bouton "Ajouter une ligne" disponible sur l'écran d'un compte, sans passer par le copier-coller — écriture directe (pas de staging).
7. Saisie du (des) total(aux) affiché(s) par la banque (pointé, à venir) → comparaison au total pointé calculé (par compte virtuel, puis somme globale pour une banque à plusieurs comptes comme La Poste) → écart affiché (vert si ça matche au centime, rouge sinon).
8. Chaque session de rapprochement est conservée dans `RapprochementSession` pour audit/historique.

## Moteur créanciers (opérations programmées)

- CRUD créancier avec les champs du modèle ci-dessus.
- **Génération automatique à l'ouverture de l'app** : pour chaque créancier actif, boucle `while date_prochaine_echeance <= aujourd'hui :` générer l'échéance puis avancer `date_prochaine_echeance` selon la récurrence. La boucle (pas un simple `if`) garantit le rattrapage de plusieurs échéances manquées si l'app est restée fermée un moment — pas besoin de stocker une date de dernier lancement séparée, `date_prochaine_echeance` est la seule source de vérité.
- Génération d'une échéance :
  - destination interne → 2 Transactions liées par `transfer_link_id` (débit sur le compte source, crédit sur le compte destination), chacune pointée indépendamment à sa date réelle (elles peuvent apparaître à des dates différentes sur chaque relevé bancaire).
  - destination externe (compte_destination_id vide) → 1 Transaction (débit sur le compte source).
  - Montant pré-rempli = montant par défaut du créancier, modifiable avant pointage (couvre les créanciers à montant variable comme l'électricité).
- Ces transactions générées apparaissent ensuite comme des lignes normales sur le compte concerné, à pointer via le rapprochement copier-coller (si elles matchent une ligne bancaire réelle) ou manuellement.
- Désactivation (`actif = false`) : arrête la génération future sans toucher à l'historique déjà généré.

Exemple (loyer) : deux créanciers distincts — "Virement Hello→Poste/Maison" (interne, mensuel) et "Prélèvement loyer" (source = Poste/Maison, externe, mensuel). Chacun génère ses échéances, pointées séparément à leur date réelle sur chaque banque.

## Reporting / Dashboards

- **Vue banque → compte virtuel (drill-down)** : par banque, total pointé/à venir global, décomposé par compte virtuel rattaché.
- **Vue mensuelle créanciers** : pour un mois donné, total récurrent prévu vs pointé (reste à passer) et total non-récurrent (transactions manuelles hors créancier) pointé sur le mois — remplace le suivi "2 colonnes" de l'Excel, sans étape de report explicite (le solde continue naturellement d'un mois à l'autre).
- **Vue par tag** : dépenses groupées par tag sur une période (mois ou plage libre), toutes banques/comptes confondus ou filtrées — répond au besoin de savoir où part l'argent (resto, etc.). Inclut un graphique (barres, Chart.js) en plus du tableau chiffré dès la V1.

## Tests

Pytest ciblé sur la logique sensible :
- boucle de rattrapage de génération des créanciers (plusieurs échéances manquées),
- dédup du rapprochement (staging),
- calcul des totaux pointé / à venir,
- calcul de l'écart total banque vs total pointé calculé.

Pas de suite e2e pour la V1.
