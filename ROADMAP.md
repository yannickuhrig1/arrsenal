# Feuille de route

Où en est arrsenal, ce qui vient ensuite, et pourquoi. Tenue à jour à chaque
séance de travail.

**Dernière mise à jour : 2 septembre 2026** — version publiée : **0.1.10**

---

## Ce qui marche aujourd'hui

Onze services installés et **câblés** en une passe, vérifiés contre des
instances réelles à chaque livraison.

| | |
|---|---|
| **Téléchargement** | Transmission, qBittorrent |
| **Bibliothèque** | Sonarr, Radarr, Lidarr |
| **Indexeurs** | Prowlarr |
| **Média** | Jellyfin |
| **Automatisation** | autobrr, Recyclarr |
| **Interfaces** | Flood, qui |
| **Réseau** | Gluetun *(VPN optionnel)* |

L'assistant couvre **toutes** les options de la ligne de commande : un test
compare la signature d'`install` à ce que l'assistant sait poser, et échoue si
un écart apparaît.

La page d'administration (`arrsenal serve`) donne l'état des services, les
démarre, les arrête, les redémarre, signale les mises à jour et les applique,
affiche les identifiants, **renouvelle un mot de passe ou une clé API en
recâblant tout ce qui en dépend**, et **installe un service absent de
l'installation initiale**.

---

## Prochaine étape

**Silo.** Deux socles sur trois sont posés.

| | État |
|---|---|
| Lire une référence d'image, digest compris | ✅ non publié |
| Un service = plusieurs conteneurs et plusieurs ports | ✅ non publié |
| Silo lui-même | à faire |

Ce que Silo demande réellement, mesuré et non supposé :

- **quatre conteneurs** — `pgvector/pgvector:pg18`, `redis:alpine`,
  `getmeili/meilisearch:latest` et `ghcr.io/silo-server/silo-server:latest` ;
- **aucune version publiée** : 488 tags sur son registre, tous des SHA de
  commit, plus `latest` et `nightly` ;
- **trois des quatre images ont un tag flottant**. Épingler Silo ne suffira pas ;
- **trois ports** : son interface, une API compatible Jellyfin sur 8096, une API
  compatible Audiobookshelf sur 13378 ;
- **`SECRET_KEY` obligatoire**, sans quoi il refuse de démarrer. Sa perte rend
  les secrets chiffrés irrécupérables : arrsenal devra le dire, pas seulement le
  générer.

Le conflit de port avec Jellyfin **n'en est pas un** : son compose prévoit
explicitement le décalage côté hôte (« PORT and JF_PORT in .env are host-side
published-port overrides »). Le conteneur garde 8096 en interne.

---

## Livré récemment

| | État | Note |
|---|---|---|
| **Rotation des mots de passe** | ✅ livré en 0.1.7 | qBittorrent, Transmission et les *arr. Vérifié sur une stack de onze services : 25 liaisons sur 25 réalignées. |
| **Rotation des clés API** | ✅ livré en 0.1.8 | Sur les *arr. Piège vérifié contre Sonarr 4.0.19 : `PUT config/host` répond **202 Accepted** et ne change rien — la clé relue vaut toujours l'ancienne une minute plus tard. Seule la réécriture de `config.xml` suivie d'un redémarrage fonctionne. |
| **Ajouter un service après coup** | ✅ livré en 0.1.8 | Section « Ajouter un service » sur la page d'administration. Vérifié en vrai : stack Sonarr seul, puis ajout de Prowlarr — 4 liaisons câblées, clé et mot de passe de Sonarr intacts. |
| **Liste des pays du VPN** | ✅ livré en 0.1.8 | Liste cliquable, extraite de l'image **épinglée**. Piège trouvé au passage : cinq fournisseurs n'exposent aucun pays — quatre classent par région, un par ville. `SERVER_COUNTRIES` ne filtrait rien chez eux. |

---

## Services à venir

Un service n'entre au catalogue que lorsqu'il est **câblé et vérifié** contre
une instance réelle. L'ordre ci-dessous est celui de l'étude.

| | Ce qu'il reste à faire |
|---|---|
| **Plex** | Second serveur média. Son jeton s'obtient par `plex.tv`, pas par l'API locale : c'est le point à vérifier avant de l'inscrire. |
| **Seerr** | Demandes de médias. Jellyseerr et Overseerr ont fusionné sous ce nom ; le câblage vise Sonarr, Radarr et le serveur média. |
| **Notifiarr** | Notifications centralisées. Chaque *arr s'y déclare par une clé API. |
| **Bazarr** | Sous-titres. Sa configuration passe par un fichier YAML et non par une API — rien n'est encore vérifié. |
| **SABnzbd** | Client Usenet, à côté des deux clients torrent. |
| **DroppedNeedle** | Musique, anciennement *MusicSeerr*. **Remplace Lidarr** plutôt que de le compléter. Un conteneur, `PUID`/`PGID` et un montage `/data` à parent commun : nos conventions exactes. Deux obstacles : il télécharge par slskd ou SABnzbd, aucun des deux au catalogue, et son premier compte administrateur se crée par l'interface web. |
| **Wizarr** | Invitations et gestion des comptes pour Jellyfin, Plex et Emby. Le plus autonome de la liste : un conteneur, et le câblage se réduit au serveur média et à sa clé. |
| **Tautulli** | Suivi et statistiques **Plex**. Ne peut pas précéder Plex. |
| **Jellystat** | Statistiques Jellyfin. Exige une base **PostgreSQL** dans un second conteneur, là où tout le catalogue tient en un seul. |
| **Tracearr** | Suivi des lectures et détection de partage de comptes. L'image `latest` réclame une base et un Redis externes ; le tag `supervised` réunit le tout en un conteneur. |
| **Silo** | Serveur média compatible API Jellyfin. Pile de quatre conteneurs, et aucune version publiée — seulement des SHA de commit. |
| Audiobookshelf, Shelfmark, Shelfarr | Livres et livres audio. |

**Readarr n'est pas au programme** : le projet est archivé depuis le 27 juin 2025.

---

## La console arrsenal

Le seul chantier qui ne soit pas un service de plus. Aujourd'hui l'assistant
installe puis s'efface ; `arrsenal serve` comble une partie du manque, mais
reste une commande à lancer.

| | État |
|---|---|
| État des services | ✅ |
| Démarrer, arrêter, redémarrer | ✅ |
| Voir et appliquer les mises à jour | ✅ |
| Renouveler un mot de passe, avec recâblage | ✅ |
| Renouveler une clé API, avec recâblage | ✅ |
| Ajouter un service absent de l'installation | ✅ |
| Démarrage automatique, sans lancer de commande | ✅ 0.1.9 |

**Pourquoi pas un conteneur.** La question a été tranchée en la mesurant. La
console doit créer, démarrer et recréer des conteneurs — soit
`POST /containers/create` puis `/start` dans l'API Docker. Or un conteneur qu'on
crée peut monter la racine de l'hôte et tourner en root : un proxy de socket qui
autorise ces deux appels n'enferme rien, et sans eux la console ne sert plus à
rien. L'y enfermer reviendrait donc à exposer sur le réseau un service aux
pleins pouvoirs, sans rien gagner.

Elle tourne donc sur l'hôte, sous le compte de l'utilisateur, sur `127.0.0.1`,
et démarre toute seule avec `arrsenal autostart`. Le confort recherché est le
même. Et parce qu'une console qui change des mots de passe doit s'authentifier
sérieusement, `arrsenal admin-password` pose un mot de passe : empreinte seule
dans `stack.yml`, sessions expirables, tentatives limitées.

---

## Ce qu'on ne fera pas

**Choisir plusieurs profils Recyclarr par service.** Recyclarr groupe ses
instances par `base_url` et **écarte tout groupe qui en compte plus d'une** —
c'est `SplitInstancesFilter`, lu dans son code source. Deux profils visant le
même Sonarr, et ce ne sont pas deux profils posés : c'est **zéro**. Les
templates racine sont autonomes et ne se composent pas ; la seule voie serait de
fusionner leur YAML nous-mêmes, exactement ce que le projet refuse — tout
l'intérêt est que le contenu vienne des TRaSH Guides et pas de nous.

arrsenal détecte désormais cette situation et n'en garde qu'un, en renommant les
autres plutôt qu'en les effaçant.

---

## Journal des corrections notables

| Version | |
|---|---|
| **0.1.10** | **0.1.8 et 0.1.9 etaient ininstallables** : le fichier des pays VPN n'entrait ni dans l'exécutable ni dans le paquet, et l'assistant mourait sur l'écran VPN. Un test compare désormais les fichiers non-Python réels aux deux déclarations d'empaquetage, et le contrôle de l'exe parcourt l'assistant au lieu de l'ouvrir. |
| **0.1.9** | La console démarre toute seule, sur l'hôte, et se protège par un mot de passe. Un cookie contenant un caractère accentué tuait la requête sans authentification. |
| **0.1.8** | Rotation des clés API, ajout d'un service depuis la page d'administration, et filtre géographique du VPN en liste cliquable. Un même défaut trouvé trois fois : un service qui garde l'ancien secret sans que rien ne le dise — autobrr, puis l'entrée Application de Prowlarr. |
| **0.1.7** | Recyclarr ne posait plus aucun profil, silencieusement, dès qu'un service se retrouvait avec deux fichiers de configuration. Renouvellement d'un mot de passe depuis la page d'administration. autobrr gardait l'ancien mot de passe d'un client de téléchargement. |
| **0.1.6** | Trois plantages de l'assistant : deuxième indexeur sélectionné (`DuplicateIds`), message d'erreur d'un indexeur contenant un crochet ouvert, et champs devenus inaccessibles sur une fenêtre courte. La clé d'un indexeur ne fuit plus à l'écran ni au journal. |
| **0.1.5** | Le VPN et l'adresse de la machine entrent dans l'assistant. Jellyfin gardait un index vide : rien ne lançait d'analyse après la création des bibliothèques. Une étape qui plante n'emporte plus tout le câblage. |
| **0.1.4** | Identifiant au choix, page d'administration accessible. |
| **0.1.3** | Choix explicite sur une configuration existante, page d'accès ouverte automatiquement. |

Le détail complet est dans les [notes de version](https://github.com/yannickuhrig1/arrsenal/releases).
