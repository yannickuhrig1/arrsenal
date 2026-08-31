# Ce qui existe déjà

Écrit avant la première ligne de code, pour ne pas refaire ce qui est déjà fait — et
mis à jour depuis. Chaque projet a été lu, pas supposé.

## Le résumé

| Projet | Déploie | Câble les apps entre elles | Profils qualité | Assistant |
|---|---|---|---|---|
| [DockSTARTer](https://github.com/GhostWriters/DockSTARTer) | oui | non | non | menu `ncurses` |
| [Saltbox](https://github.com/saltyorg/Saltbox) | oui | partiel | non | non |
| [geekau/mediastack](https://github.com/geekau/mediastack) | oui (fichiers) | non | non | non |
| [Recyclarr](https://github.com/recyclarr/recyclarr) | non | non | **oui** | non |
| [Configarr](https://github.com/raydak-labs/configarr) | non | non | **oui** | non |
| [TRaSH Guides](https://trash-guides.info/) | non | non | manuel | non |
| **arrsenal** | **oui** | **oui** | phase 4 | **oui** |

La colonne qui compte est la deuxième. C'est celle où presque personne ne va.

## Projet par projet

### DockSTARTer

Le plus proche par l'intention : un menu qui laisse choisir des applications et génère
un `docker-compose.yml`. Très mature, très large — plus de cent applications.

**Ce qu'il ne fait pas** : une fois les conteneurs lancés, tout reste à faire. Aucune
clé API n'est échangée, aucun dossier racine n'est créé, aucun client de téléchargement
n'est rattaché. C'est exactement le travail de trois heures que `arrsenal` supprime.

### Saltbox (et Cloudbox avant lui)

Un déploiement Ansible très complet, jusqu'au reverse proxy et aux certificats. Câble
certaines choses entre elles.

**Le décalage** : c'est une distribution, pas un outil. Il attend un serveur dédié,
impose ses choix, et se destine à un usage sérieux et durable plutôt qu'à une
installation qu'on essaie un dimanche.

### geekau/mediastack

D'excellents fichiers Compose, très bien documentés, avec plusieurs variantes selon
qu'on veut un VPN ou non.

**La limite** : ce sont des fichiers. Le câblage reste manuel, et la documentation est
là pour vous guider à travers, pas pour le faire à votre place.

### Recyclarr et Configarr

Ils synchronisent les profils de qualité et les *custom formats* des TRaSH Guides vers
Sonarr et Radarr. Chacun fait très bien ce travail.

**Ils ne se recoupent pas avec `arrsenal`** : ils supposent une stack déjà installée et
déjà câblée. Ils interviennent après. La phase 4 vise l'intégration de Recyclarr, pas
son remplacement.

### TRaSH Guides et le wiki Servarr

La référence documentaire du domaine. C'est de là que vient le principe du montage
`/data` unique, et la raison pour laquelle `arrsenal` l'impose.

Rien à concurrencer : ce sont des guides. `arrsenal` cherche à en appliquer les
recommandations automatiquement, et les crédite.

## Où se situe arrsenal

Le trou est net : **déploiement et câblage complet, dans un seul outil, avec un
assistant**.

Trois choix découlent de cette analyse.

**Le câblage est la raison d'être, pas un bonus.** Générer un `docker-compose.yml` est
un moyen. Si `arrsenal` ne faisait que ça, il n'aurait aucune raison d'exister à côté
de DockSTARTer.

**Le câblage doit être vérifié, pas supposé.** C'est ce qui distingue un outil d'un
script. Chaque lien est validé par le bouton *Test* de l'application cible.

**Les profils de qualité viendront de Recyclarr.** Réimplémenter les TRaSH Guides
serait une duplication inutile et vite périmée.

## Ce qu'aucun ne fait, et que nous non plus (encore)

- **Vérifier que les hardlinks fonctionnent vraiment** avant l'installation. `arrsenal`
  le fait — c'est peut-être son ajout le plus utile après le câblage.
- **Détecter une stack existante et proposer de la reprendre** plutôt que d'en poser une
  seconde. Personne ne le fait. Ce serait un vrai sujet.
- **Un mode « diagnostic » d'une installation qu'on n'a pas faite soi-même.**
  `arrsenal doctor` n'en fait qu'une partie.

## Méthode

Ce document est relu à chaque phase. Un projet qui se met à câbler les applications
entre elles change le positionnement d'`arrsenal`, et il vaut mieux le savoir tôt que
de le découvrir dans un commentaire Reddit.

Dernière relecture : 2026-08-31.
