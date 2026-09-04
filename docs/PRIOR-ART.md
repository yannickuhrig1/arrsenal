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
| **PlugArr** | **oui** | **oui** | **oui** (délégués à Recyclarr) | **oui** |

La colonne qui compte est la deuxième. C'est celle où presque personne ne va.

## Projet par projet

### DockSTARTer

Le plus proche par l'intention : un menu qui laisse choisir des applications et génère
un `docker-compose.yml`. Très mature, très large — plus de cent applications.

**Ce qu'il ne fait pas** : une fois les conteneurs lancés, tout reste à faire. Aucune
clé API n'est échangée, aucun dossier racine n'est créé, aucun client de téléchargement
n'est rattaché. C'est exactement le travail de trois heures que PlugArr supprime.

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

**Ils ne se recoupent pas avec PlugArr** : ils supposent une stack déjà installée et
déjà câblée. Ils interviennent après.

C'est exactement pour cela que Recyclarr est désormais **intégré, pas remplacé**.
PlugArr lui demande de générer sa configuration à partir d'un template officiel, puis
n'y écrit que l'adresse et la clé API — les deux choses qu'il est seul à connaître, et
les deux seules lignes que l'utilisateur aurait dû aller chercher à la main. Le contenu
des profils reste celui du guide.

### TRaSH Guides et le wiki Servarr

La référence documentaire du domaine. C'est de là que vient le principe du montage
`/data` unique, et la raison pour laquelle PlugArr l'impose.

Rien à concurrencer : ce sont des guides. PlugArr cherche à en appliquer les
recommandations automatiquement, et les crédite.

## Où se situe PlugArr

Le trou est net : **déploiement et câblage complet, dans un seul outil, avec un
assistant**.

Trois choix découlent de cette analyse.

**Le câblage est la raison d'être, pas un bonus.** Générer un `docker-compose.yml` est
un moyen. Si PlugArr ne faisait que ça, il n'aurait aucune raison d'exister à côté
de DockSTARTer.

**Le câblage doit être vérifié, pas supposé.** C'est ce qui distingue un outil d'un
script. Chaque lien est validé par le bouton *Test* de l'application cible.

**Les profils de qualité viennent de Recyclarr.** Réimplémenter les TRaSH Guides serait
une duplication inutile et vite périmée. PlugArr fournit le câblage, TRaSH fournit
les profils.

## L'écosystème autobrr

Signalé en cours de route, et il change deux choses.

### dashbrr — la page d'administration n'est pas une idée neuve

[`autobrr/dashbrr`](https://github.com/autobrr/dashbrr) (227 étoiles, Go) est un tableau
de bord de surveillance et de gestion d'une stack média. C'est-à-dire, pour une bonne
part, ce que fait `plugarr serve`.

Autant le dire plutôt que de faire semblant. Ce qui reste à PlugArr : la page sort de
l'installation, sans conteneur supplémentaire ni configuration. dashbrr est plus riche et
plus abouti pour qui veut un tableau de bord permanent.

### autobrr et qui — deux ajouts, pas deux concurrents

[`autobrr`](https://github.com/autobrr/autobrr) (2 991 étoiles) écoute les canaux
d'annonce IRC des trackers au lieu d'attendre le prochain sondage RSS. Il se branche sur
les *arr **et** sur le client de téléchargement : c'est un nœud de câblage, exactement
ce que ce projet automatise. Ajouté au catalogue.

[`qui`](https://github.com/autobrr/qui) (4 430 étoiles) est une interface qBittorrent en
binaire unique — plus étoilée que Flood, et plus récente. Ajoutée en option, sans
remplacer Flood, qui couvre aussi Transmission.

Laissés de côté : `netronome` (test de débit réseau) et `mkbrr` (création de fichiers
torrent) sortent du périmètre d'une stack de consommation. `upbrr` prépare des envois
vers des trackers privés : c'est un outil légitime, mais son objet s'écarte de la
position de ce projet, qui ne fournit ni tracker ni facilitation.

## Ce qu'aucun ne fait, et que nous non plus (encore)

- **Vérifier que les hardlinks fonctionnent vraiment** avant l'installation. PlugArr
  le fait — c'est peut-être son ajout le plus utile après le câblage.
- **Un mode « diagnostic » d'une installation qu'on n'a pas faite soi-même.**
  `plugarr doctor` n'en fait qu'une partie.

## Méthode

Ce document est relu à chaque phase. Un projet qui se met à câbler les applications
entre elles change le positionnement de PlugArr, et il vaut mieux le savoir tôt que
de le découvrir dans un commentaire Reddit.

Dernière relecture : 2026-08-31.

*Depuis la première rédaction, `plugarr adopt` couvre la reprise d'une stack existante,
qui figurait ici comme un manque de tout l'écosystème.*
