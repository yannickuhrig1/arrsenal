# Feuille de route

Où en est arrsenal, ce qui vient ensuite, et pourquoi. Tenue à jour à chaque
séance de travail.

**Dernière mise à jour : 3 septembre 2026** — version publiée : **0.1.11**

---

## Ce qui marche aujourd'hui

Douze services installés et **câblés** en une passe, vérifiés contre des
instances réelles à chaque livraison.

| | |
|---|---|
| **Téléchargement** | Transmission, qBittorrent |
| **Bibliothèque** | Sonarr, Radarr, Lidarr |
| **Indexeurs** | Prowlarr |
| **Média** | Jellyfin, Silo *(expérimental)* |
| **Automatisation** | autobrr, Recyclarr |
| **Interfaces** | Flood, qui |
| **Réseau** | Gluetun *(VPN optionnel)* |

L'assistant couvre **toutes** les options de la ligne de commande : un test
compare la signature d'`install` à ce que l'assistant sait poser, et échoue si
un écart apparaît.

La langue des interfaces se demande une fois et s'applique à toutes les
applications qui en acceptent une.

La page d'administration (`arrsenal serve`) donne l'état des services, les
démarre, les arrête, les redémarre, signale les mises à jour et les applique,
affiche les identifiants, **renouvelle un mot de passe ou une clé API en
recâblant tout ce qui en dépend**, et **installe un service absent de
l'installation initiale**.

---

## Prochaine étape

**Mise à jour du pack.** Aujourd'hui arrsenal sait dire qu'une image a une
version plus récente et l'appliquer. Il ne sait pas mettre à jour **sa propre
installation** quand c'est arrsenal qui change.

Le trou est concret et vérifiable : `stack.yml` porte un champ `version: 1`, et
**rien ne le lit** — aucune occurrence dans le code. Cette semaine seule, quatre
champs y sont apparus (`admin_password_hash`, `language`, `secret_key`,
`extra_ports`). Les valeurs par défaut de pydantic absorbent l'écart en silence,
ce qui marche tant qu'un champ ne fait qu'apparaître. Le jour où l'un change de
sens, une installation faite en 0.1.7 se relira sans erreur et sera fausse.

| | |
|---|---|
| Migrations de `stack.yml`, indexées sur son numéro de version | à faire |
| Appliquer les digests épinglés d'un nouveau catalogue à une installation ancienne | à faire |
| Rejouer les étapes de câblage qui ont changé depuis la version installée | à faire |

**Pas de fichier de secrets chiffré**, et la raison est mécanique plutôt que
philosophique : c'est **Docker Compose** qui lit le `.env`, pas arrsenal.
`POSTGRES_PASSWORD`, `SILO_SECRET_KEY` et les identifiants VPN doivent être en
clair sur le disque au moment du `up`, sinon la stack ne démarre pas. Chiffrer
`stack.yml` pendant que `.env` est en clair à côté serait décoratif. Un vrai
chiffrement suppose une phrase de passe tapée à chaque démarrage, ce qui
supprime le démarrage automatique livré en 0.1.9. Ce qui protège aujourd'hui :
`chmod 600`, `.gitignore` généré, et masquage des secrets dans le journal.

---

## Livré récemment

| | État | Note |
|---|---|---|
| **Rotation des mots de passe** | ✅ livré en 0.1.7 | qBittorrent, Transmission et les *arr. Vérifié sur une stack de onze services : 25 liaisons sur 25 réalignées. |
| **Rotation des clés API** | ✅ livré en 0.1.8 | Sur les *arr. Piège vérifié contre Sonarr 4.0.19 : `PUT config/host` répond **202 Accepted** et ne change rien — la clé relue vaut toujours l'ancienne une minute plus tard. Seule la réécriture de `config.xml` suivie d'un redémarrage fonctionne. |
| **Ajouter un service après coup** | ✅ livré en 0.1.8 | Section « Ajouter un service » sur la page d'administration. Vérifié en vrai : stack Sonarr seul, puis ajout de Prowlarr — 4 liaisons câblées, clé et mot de passe de Sonarr intacts. |
| **Silo** | ✅ livré en 0.1.11 | Serveur média compatible API Jellyfin, **marqué expérimental**. Trois conteneurs — `pgvector/pgvector:pg18`, `redis:alpine` et `silo-server`, épinglés au digest ; Meilisearch est optionnel et n'est pas installé. Compte, **profil** et trois bibliothèques posés et relus. Deux pièges mesurés, pas supposés : sa base doit vivre dans un **volume Docker** (montage vers l'hôte : migrations en **2935 s** contre **5 s**), et son mot de passe de base doit être alphanumérique — un `?` dans une `postgres://` et le conteneur redémarre en boucle. |
| **Langue des interfaces** | ✅ livré en 0.1.11 | Demandée une fois dans l'assistant, appliquée partout. Chaque application exprime la même idée autrement : Sonarr et Radarr veulent un entier, **Prowlarr veut le code** (`fr`), Jellyfin une culture et un pays, Silo un code **par bibliothèque**. La table des 29 langues des *arr n'est publiée nulle part : relevée valeur par valeur contre un Sonarr 4.0.19. Au passage, une incohérence corrigée — arrsenal imposait le français à Jellyfin, en dur, et laissait tout le reste en anglais. |
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
| **0.1.11** | La base de Silo passait par un montage vers le disque Windows : ses migrations de premier démarrage prenaient **49 minutes** au lieu de 5 secondes, et l'installation abandonnait au bout de 300 s alors que PostgreSQL fonctionnait très bien. Un volume Docker règle les deux. Au passage, `config/silo-redis` restait vide à côté du `config/silo/redis` que Docker fabriquait lui-même. |
| **0.1.10** | **0.1.8 et 0.1.9 etaient ininstallables** : le fichier des pays VPN n'entrait ni dans l'exécutable ni dans le paquet, et l'assistant mourait sur l'écran VPN. Un test compare désormais les fichiers non-Python réels aux deux déclarations d'empaquetage, et le contrôle de l'exe parcourt l'assistant au lieu de l'ouvrir. |
| **0.1.9** | La console démarre toute seule, sur l'hôte, et se protège par un mot de passe. Un cookie contenant un caractère accentué tuait la requête sans authentification. |
| **0.1.8** | Rotation des clés API, ajout d'un service depuis la page d'administration, et filtre géographique du VPN en liste cliquable. Un même défaut trouvé trois fois : un service qui garde l'ancien secret sans que rien ne le dise — autobrr, puis l'entrée Application de Prowlarr. |
| **0.1.7** | Recyclarr ne posait plus aucun profil, silencieusement, dès qu'un service se retrouvait avec deux fichiers de configuration. Renouvellement d'un mot de passe depuis la page d'administration. autobrr gardait l'ancien mot de passe d'un client de téléchargement. |
| **0.1.6** | Trois plantages de l'assistant : deuxième indexeur sélectionné (`DuplicateIds`), message d'erreur d'un indexeur contenant un crochet ouvert, et champs devenus inaccessibles sur une fenêtre courte. La clé d'un indexeur ne fuit plus à l'écran ni au journal. |
| **0.1.5** | Le VPN et l'adresse de la machine entrent dans l'assistant. Jellyfin gardait un index vide : rien ne lançait d'analyse après la création des bibliothèques. Une étape qui plante n'emporte plus tout le câblage. |
| **0.1.4** | Identifiant au choix, page d'administration accessible. |
| **0.1.3** | Choix explicite sur une configuration existante, page d'accès ouverte automatiquement. |

Le détail complet est dans les [notes de version](https://github.com/yannickuhrig1/arrsenal/releases).
