# CompteperSo

Application locale de suivi budgétaire personnel/familial multi-banques : comptes virtuels, opérations récurrentes (créanciers), rapprochement bancaire par copier-coller, rapports mensuels et par tag.

Aucune API bancaire, aucune donnée envoyée nulle part : tout tourne en local dans une base SQLite sur ta machine.

## ⚠️ Limitation majeure : macOS uniquement pour l'instant

Ce projet n'a été **développé et testé que sur macOS**. Le lancement (`.app` / `.command`) est spécifique à macOS. Le cœur de l'app (FastAPI + SQLite) est en théorie portable, mais **Windows et Linux ne sont ni testés ni packagés à ce jour**.

Le portage est suivi dans deux issues dédiées — contributions bienvenues :
- Portage & test Windows
- Portage & test Linux

## Fonctionnalités

### Banques et comptes virtuels
Chaque banque réelle (ex: Boursorama, HelloBank, La Banque Postale) peut contenir un ou plusieurs **comptes virtuels** — pratique quand une seule banque sert de support à plusieurs enveloppes budgétaires (Économie, Maison, Vacances, Impôts...). Les comptes virtuels sont réordonnables par glisser-déposer dans la barre latérale.

### Transactions
Chaque compte virtuel a son propre historique de transactions : date, libellé, montant, tags libres. On peut ajouter une ligne à la main, dupliquer une ligne existante, cliquer sur une ligne pour la modifier, et pointer une opération via une case à cocher. Les totaux **Pointé / À venir / Solde** sont affichés en permanence.

### Créanciers (opérations programmées/récurrentes)
Un créancier décrit une opération qui se répète (loyer, salaire, virement mensuel...) : montant, compte source, compte destination (optionnel — vide = destination externe), récurrence (mensuelle/hebdomadaire/personnalisée/ponctuelle), date de fin optionnelle. À chaque lancement de l'app, les échéances dues sont générées automatiquement en transactions (non pointées), avec rattrapage si l'app est restée fermée plusieurs mois.

- **Destination interne** (un autre compte virtuel) : génère deux lignes liées (débit côté source, crédit côté destination), chacune pointée séparément selon sa date réelle sur son relevé.
- **Destination externe** (vide) : une seule ligne, dont le **signe du montant fait foi** — négatif = l'argent sort du compte (ex: prélèvement EDF), positif = l'argent rentre depuis l'extérieur (ex: virement CAF).

Un tableau de **flux** (par banque et par compte virtuel) montre le total des créanciers actifs par trajet source→destination, ex: "HelloBank → LBP : 1050,00".

### Rapprochement bancaire
Pour chaque banque : colle le texte copié depuis le site de la banque, calibre une fois le mapping de colonnes (aperçu en tableau, un menu déroulant par colonne pour choisir Date/Libellé/Montant/Ne pas utiliser), puis les lignes suivantes sont automatiquement parsées avec ce calibrage. Un écran de contrôle affiche les lignes détectées avant écriture définitive, avec détection de doublons (verrouillables/déverrouillables) et suggestion de tags apprise des pointages précédents. En fin de session, on saisit le total affiché par la banque pour comparer à l'écart calculé.

### Rapports
- **Rapport mensuel** : par compte virtuel, reliquat du début de mois, total récurrent prévu/pointé, reste à passer, total non récurrent pointé.
- **Dépenses par tag** : agrégation des dépenses par tag sur une période, avec graphique.

### Réglages
Configuration du dossier où la base est sauvegardée (copie horodatée) à la fermeture de l'application.

## Installation (macOS)

Prérequis : Python 3.11+.

```bash
git clone <url-du-repo>
cd compteperso

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Lancer les tests

```bash
pytest
```

### Lancer l'application

Deux méthodes équivalentes :

**Via script `.command`** (ouvre un Terminal visible) :
```bash
./scripts/ComptesApp.command
```

**Via bundle `.app`** (recommandé — pas de Terminal qui s'affiche) :
```bash
./scripts/build_app.sh
cp -R scripts/ComptesApp.app /Applications/
```
Puis lance "Comptes" depuis Spotlight, Launchpad ou `/Applications`.

La base de données est stockée dans `~/Library/Application Support/ComptesApp/comptes.db`, en dehors du dossier synchronisé (pas de risque de corruption par écriture concurrente). Le dossier de backup se configure depuis l'écran Réglages de l'application.

## Licence

MIT — voir [LICENSE](LICENSE).
