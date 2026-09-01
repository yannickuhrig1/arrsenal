# Compatibilité

Tout ce qui figure ici a été **vérifié contre une instance réelle**, pas déduit de la
documentation. Les tags d'image sont épinglés dans `src/arrsenal/catalog.py`.

Dernière campagne de vérification : **2026-08-31**, Docker Engine 29.6.1,
Docker Compose v5.3.0, Docker Desktop sous Windows 11 (backend WSL2).

## Versions testées

| Service | Image | Tag | Version rapportée par l'API |
|---|---|---|---|
| Sonarr | `lscr.io/linuxserver/sonarr` | `4.0.19` | 4.0.19.2979 |
| Radarr | `lscr.io/linuxserver/radarr` | `6.3.0` | vérifié au démarrage |
| Prowlarr | `lscr.io/linuxserver/prowlarr` | `2.5.2` | vérifié au démarrage |
| Transmission | `lscr.io/linuxserver/transmission` | `4.1.3` | — |
| Jellyfin | `lscr.io/linuxserver/jellyfin` | `10.11.11` | 10.11.11 |
| Lidarr | `lscr.io/linuxserver/lidarr` | `3.1.0` | 3.1.0.4875 |
| qBittorrent | `lscr.io/linuxserver/qbittorrent` | `5.2.3` | v5.2.3 |
| Flood | `jesec/flood` | `4.16.1` | pas encore testé |

## Constats vérifiés expérimentalement

### Le pré-semis de `config.xml` fonctionne

Un `config.xml` écrit **avant** le premier démarrage est adopté par l'application.
Sonarr conserve nos champs et se contente d'ajouter les siens (`EnableSsl`).
Notre clé API répond immédiatement sur `/api/v3/system/status`.

Le premier démarrage prend **environ 110 s** (extraction de l'image + initialisation).
C'est ce qui fixe le délai d'attente par défaut à 300 s.

### `Forms` + `Enabled` est le bon réglage d'authentification

Trois comportements confirmés sur Sonarr 4.0.19.2979 :

| Requête | Résultat |
|---|---|
| `GET /` sans session | `302` vers `/login` — l'UI est protégée |
| `GET /api/v3/system/status` sans clé | `401` |
| `GET /api/v3/system/status` avec `X-Api-Key` | `200`, `"authentication": "forms"` |

L'alternative `External` + `DisabledForLocalAddresses` câble aussi bien mais laisse
les interfaces web ouvertes à tout le réseau local. **Rejetée.**

Bonus : l'application consomme `<Username>`/`<Password>` au premier démarrage, les
migre en base, puis les **efface du fichier**. Le mot de passe en clair ne survit pas
sur le disque.

### `Category` et `Directory` sont mutuellement exclusifs

Renseigner les deux fait échouer la création du client de téléchargement :

```
HTTP 400 — propertyName: "TvCategory", errorMessage: "Cannot use Category and Directory"
```

**Piège** : le gabarit renvoyé par `/schema` arrive avec une catégorie **par défaut
déjà remplie** (`tv-sonarr` pour Sonarr, `radarr` pour Radarr). Il ne suffit pas
d'omettre le champ, il faut le **vider explicitement**.

`arrsenal` retient `Directory`, qui pointe vers un chemin explicite sous
`/data/torrents` et garde les hardlinks possibles.

### La notification Jellyfin exige une clé API

L'implémentation `MediaBrowser` de Sonarr et Radarr refuse un `apiKey` vide :

```
HTTP 400 — propertyName: "ApiKey", errorMessage: "'Api Key' must not be empty."
```

`arrsenal` crée donc une clé Jellyfin via `POST /Auth/Keys?app=arrsenal` (répond `204`)
pendant l'étape d'assistant, puis la relit par `GET /Auth/Keys`, et l'injecte dans les
notifications. C'est ce qui impose l'ordre : Jellyfin avant les notifications.

### Assistant de démarrage Jellyfin 10.11.11

| Appel | Code |
|---|---|
| `POST /Startup/Configuration` | `204` |
| `GET /Startup/User` | `200` |
| `POST /Startup/User` | `204` |
| `POST /Startup/RemoteAccess` | `204` |
| `POST /Startup/Complete` | `204` |
| `POST /Users/AuthenticateByName` | `200` + `AccessToken` |
| `POST /Library/VirtualFolders` | `204` |

Après quoi `StartupWizardCompleted` passe à `true` et la bibliothèque apparaît avec le
bon `CollectionType` et le bon chemin.

Jellyfin démarre en **environ 25 s**, nettement plus vite que les *arr.

## Vérification finale du câblage

Chaque lien est validé par le bouton **Test** de l'application concernée, pas par le
code de retour du POST :

| Test | Résultat |
|---|---|
| `POST /api/v3/downloadclient/test` (Sonarr → Transmission) | `200` |
| `POST /api/v1/applications/test` (Prowlarr → Sonarr) | `200` |
| `POST /api/v3/notification/test` (Sonarr → Jellyfin) | `200` |
| `GET /api/v3/rootfolder` | `accessible: true` |

Installation propre depuis zéro : **10/10 liens établis**.

## Phase 2 — constats vérifiés

Campagne du **2026-08-31**, même environnement. Installation propre à 7 services
avec **les deux clients de téléchargement en parallèle** : **18/18 liens établis**.

### Le pré-semis du mot de passe qBittorrent fonctionne

Depuis la 4.6.1, qBittorrent génère au premier démarrage un mot de passe temporaire
aléatoire écrit sur sa sortie standard — impossible à câbler automatiquement.

Écrire `WebUI\Password_PBKDF2` dans `/config/qBittorrent/qBittorrent.conf` avant le
premier démarrage résout le problème. Format confirmé contre 5.2.3 :

```
@ByteArray(<sel base64>:<empreinte base64>)
PBKDF2-HMAC-SHA512, 100000 itérations, clé 64 octets, sel 16 octets
```

Résultat : `POST /api/v2/auth/login` répond `204` avec un cookie `QBT_SID`, et aucun
mot de passe temporaire n'apparaît dans les logs.

**Attention au code de retour** : qBittorrent 5.x renvoie `204` en cas de succès et
`200` avec le corps `Fails.` en cas d'échec. C'est donc la présence du cookie qui fait
foi, jamais le code HTTP seul.

### `HostHeaderValidation` doit être désactivé

Sonarr et Radarr appellent qBittorrent par son nom de conteneur
(`http://qbittorrent:8080`), pas par une adresse IP. Sans
`WebUI\HostHeaderValidation=false`, qBittorrent rejette ces requêtes.

### qBittorrent route par catégorie, Transmission par répertoire

Transmission n'a pas de vraies catégories : on lui passe un `Directory`.
qBittorrent a des catégories natives avec chemin de sauvegarde par catégorie : on lui
passe une `Category`, créée en amont via `POST /api/v2/torrents/createCategory`.

Ordre imposé : les catégories doivent exister **avant** que les *arr n'y pointent,
sinon qBittorrent les crée lui-même sans chemin de sauvegarde. Prowlarr fait de même
avec une catégorie `prowlarr` : elle est donc pré-créée aussi.

Vérifié après installation :

```
movies   -> /data/torrents/movies
music    -> /data/torrents/music
prowlarr -> /data/torrents
tv       -> /data/torrents/tv
```

### Lidarr n'est pas un Sonarr comme les autres

Trois différences qui cassent le code écrit pour Sonarr et Radarr :

1. **Son API est en `v1`**, pas `v3`.
2. **Son dossier racine exige plus de champs.** Là où Sonarr accepte `{"path": ...}`,
   Lidarr répond `400` :

   ```
   Name                     : 'Name' must not be empty.
   DefaultQualityProfileId  : must be greater than '0'.
   DefaultMetadataProfileId : must be greater than '0'.
   ```

   Il n'existe pas de `/schema` pour `rootfolder`. Les identifiants de profils ne sont
   pas stables entre versions : ils sont résolus **par nom** (`Standard`), avec repli
   sur le premier profil disponible.

3. Lidarr n'expose **pas** l'implémentation de notification `MediaBrowser` : aucun lien
   Lidarr vers Jellyfin n'est tenté.

## PUID / PGID par plateforme — vérifié

Le point de départ était un `TODO(verify)`. La vérification a montré que **la question
était mal posée** : ce ne sont pas les mêmes valeurs qu'il fallait trouver, mais deux
comportements différents.

| Profil | Comportement | Pourquoi |
|---|---|---|
| `generic-linux` | détection (`os.getuid`) | l'utilisateur courant est le bon |
| `unraid` | **constante 99:100** | Unraid fait tourner ses conteneurs en `nobody:users` à l'échelle de la plateforme, et son `appdata` appartient à 99:100 |
| `synology` | détection | **les UID DSM varient selon l'ordre de création des utilisateurs** : 1026 pour le premier, mais on rencontre couramment bien plus haut |

Coder `1026` en dur pour Synology était donc **faux par conception**, pas seulement non
vérifié. Une constante ne peut pas être juste quand la valeur dépend de l'installation.

Deux conséquences dans le code :

- `detect_ids()` renvoie `None` quand la plateforme n'expose pas `os.getuid` (Windows),
  au lieu d'inventer `1000:1000` en silence. Une valeur fabriquée sans le dire empêche
  d'avertir l'utilisateur.
- `StackConfig` porte `ids_source` et `ids_certain`. Le récapitulatif affiche d'où
  viennent les valeurs (« détecté », « constante Unraid », « repli »), et l'assistant
  avertit explicitement quand la détection a échoué.

Sources : [forums Unraid](https://forums.unraid.net/topic/117661-docker-user-puid-and-group-pgid-settings/)
· [Marius Hosting, UID/GID sur Synology](https://mariushosting.com/synology-how-to-find-uid-userid-and-gid-groupid/)

## Coexistence avec une stack existante — vérifié

Observation faite sur un Unraid réel faisant tourner 75 conteneurs, dont un
`sonarr` sur le port 8989 avec `/mnt/user/appdata/sonarr` en configuration :
**arrsenal codait `container_name` en dur**, donc il ne pouvait ni cohabiter avec une
stack existante, ni être déployé deux fois sur la même machine.

Les noms de conteneurs sont désormais préfixés par le nom de projet
(`arrsenal-sonarr`). Vérifié contre Docker Compose v5.3 que cela ne casse rien :

```
depuis le service "sonarr" :
  getent hosts prowlarr           -> 172.18.0.3  prowlarr
  getent hosts dnsprobe-prowlarr  -> 172.18.0.3  dnsprobe-prowlarr
```

Le **nom de service** résout indépendamment de `container_name`. Le câblage vise le
service (`http://sonarr:8989`), il n'est donc pas affecté.

Les collisions de **ports** restent possibles (8989 est un défaut très répandu) : le
préflight les détecte et refuse avant toute écriture.

## Linux natif — vérifié le 2026-08-31

Toutes les campagnes précédentes tournaient sous Docker Desktop / WSL2, où les
permissions sont plus permissives qu'un vrai serveur. Vérification faite sur un **LXC
Proxmox Debian 12.2** (PVE 9.2.6), ext4, Docker 29.7.2.

| | |
|---|---|
| Installation complète (5 services) | **11/11 liens établis**, tous validés par le bouton Test |
| Second passage | aucune création, tout « déjà présent » |
| Hardlink `/data/torrents/tv` → `/data/media/tv`, **depuis l'intérieur du conteneur Sonarr** | `stat -c %h` = **2** |

Le hardlink est la preuve qui manquait : sous Windows, seul `os.link` côté hôte avait
été testé. Ici c'est Sonarr lui-même, dans son conteneur, sur ext4, qui partage l'inode
entre les téléchargements et la médiathèque. C'est exactement ce que le montage `/data`
unique doit garantir.

### Docker dans un LXC : `nesting=1` suffit

Contrairement à ce qui est souvent écrit, `keyctl=1` n'a pas été nécessaire — et il
n'est de toute façon pas réglable via un jeton d'API Proxmox, seulement en `root@pam`
direct. Avec `nesting=1` seul, `docker run hello-world` et la stack complète
fonctionnent.

### Le bug que seul Linux pouvait révéler

`sudo arrsenal install` détectait `0:0` et faisait tourner **toute la stack en root**,
en silence. Les médias téléchargés appartiennent alors à root, et l'utilisateur ne peut
plus y toucher sans `sudo`.

`resolve_ids` signale désormais explicitement le cas root, au même titre qu'une
détection impossible. La valeur reste proposée — c'est un choix légitime sur certains
NAS — mais elle n'est plus silencieuse.

## Non vérifié à ce jour

- Bazarr est **volontairement absent du catalogue** : sa configuration passe par un
  fichier YAML et non par une API, et rien n'a encore été vérifié. Le projet ne livre
  pas de service qu'il ne sait pas câbler.
- Flood n'a pas encore été démarré dans une campagne de test.

## Indexeurs — constats vérifiés (Prowlarr 2.5.2)

### Ce que Prowlarr embarque

`GET /api/v1/indexer/schema` renvoie **626 définitions**, soit **5,7 Mo** — à charger une
seule fois et à mettre en cache, jamais à chaque frappe.

| | |
|---|---|
| privées | 475 |
| publiques | 88 |
| semi-privées | 63 |
| torrent / usenet | 605 / 21 |

### Repérer les champs d'identifiants

Le marqueur `privacy` au niveau champ (`apiKey`, `password`, `userName`) ne couvre que
**115 champs sur plus de 9500** : la majorité des définitions Cardigann laissent leurs
clés en `privacy: normal`. Une heuristique combinée est nécessaire :

1. `privacy` ∈ (`apiKey`, `password`, `userName`)
2. ou `type == "password"`
3. ou nom connu (`apikey`, `passkey`, `cookie`, `rsskey`, …)
4. ou — **règle structurelle** — `type == "textbox"` avec une valeur par défaut vide
5. en excluant les préfixes de réglage (`baseSettings.`, `torrentBaseSettings.`,
   `usenetBaseSettings.`), les 882 champs `type: "info"` purement décoratifs, et une
   courte liste de zones de texte libres qui n'en sont pas (`vipExpiration`,
   `additionalParameters`, préférences de langue)

### L'audit qui a produit la règle 4

Les règles 1 à 3 ont été confrontées aux **626 définitions** par
[`scripts/audit_indexers.py`](../scripts/audit_indexers.py). Elles laissaient passer
six identifiants : `mamId` (MyAnonamouse), `twoFactorAuthCode`, `alt2fatoken`, `passan`,
`staffpass`, `csrf_token`.

Tous étaient des **zones de texte sans valeur par défaut**. D'où la règle structurelle,
qui vaut mieux qu'une liste de noms à rallonge : une textbox vide est, par construction,
quelque chose que seul l'utilisateur peut fournir. Les réglages de comportement sont des
cases à cocher ou des listes, jamais des textbox vides.

Effet mesuré : **58 champs** rattrapés sur les 626 définitions, tous de vrais
identifiants (26 codes 2FA, 17 `useragent`, 8 `pin`, `mamId`, `passan`, `staffpass`…).
Aucun formulaire ne dépasse **3 identifiants**.

Deux familles de cas ont été examinées puis jugées correctes :

- **4 index privés sans aucun identifiant** — `BitMagnet (Local DHT)`, `comicat`,
  `MioBT`, `ConCen`. Ce sont des moteurs de recherche qui n'exigent pas de compte.
- **6 champs au nom trompeur** — `useFreeleechToken`, `usetoken`, `passid`… tous des
  cases à cocher ou des listes, donc des réglages.

L'audit tourne en CI contre le Prowlarr de la stack de test : **il échoue si une future
version introduit un champ d'identifiant d'une forme non prévue.**

### Les URL ne sont pas dans le champ `baseUrl`

**600 des 626** définitions exposent un `baseUrl` de type `select` **sans valeur et sans
`selectOptions`**. Les adresses vivent au niveau de la définition, dans `indexerUrls`.
Sans cette reprise, l'utilisateur devrait deviner l'adresse du tracker. Seules 3
définitions n'ont légitimement aucune URL : les génériques (`Generic Newznab`,
`Generic Torznab`, `Torrent RSS Feed`).

### L'ajout contacte forcément l'indexeur

`appProfileId` doit être `> 0`, comme le dossier racine de Lidarr. Résolu par nom
(`Standard`), jamais codé en dur.

Surtout : **`forceSave=true` ne saute pas la validation.** Vérifié sur deux cas d'échec :

| Situation | Résultat |
|---|---|
| indexeur injoignable | `400 — Unable to connect to indexer` |
| recherche de test sans résultat | `400 — Query successful, but no results were returned` |
| faux indexeur Torznab local renvoyant un résultat | enregistré |

Il n'existe donc **aucun moyen d'enregistrer un indexeur hors ligne**. Ce n'est pas un
choix d'arrsenal. La contrepartie est utile : la validation *est* le test, donc un ajout
réussi prouve que les identifiants fonctionnent.

Vérification menée contre un **faux serveur Torznab local**, jamais contre un vrai
tracker.

## Seerr remplace Jellyseerr et Overseerr — vérifié le 2026-08-31

Signalé par un utilisateur, vérifié plutôt que supposé. Ce n'est pas un renommage mais
une **fusion des deux projets**, annoncée le 10 février 2026.

| | |
|---|---|
| Dépôt canonique | `seerr-team/seerr` — 12 440 étoiles, actif |
| Image | `seerr/seerr`, dernière version stable **v3.4.1** (30/07/2026) |
| `sct/overseerr` | **archivé**, dernier push le 15/02/2026 |
| `fallenbagel/jellyseerr` | redirige (HTTP 301) vers `seerr-team/seerr` |

Seerr couvre Jellyfin, Emby **et** Plex — les deux projets d'origine se partageaient
ces cibles — et migre automatiquement les données au premier démarrage.

Conséquence pour arrsenal : la feuille de route ne vise plus qu'un seul service de
demandes utilisateurs. Prévoir la reprise d'une installation Jellyseerr ou Overseerr
existante est inutile : Seerr le fait lui-même.

## Reprise d'une stack existante — vérifié le 2026-08-31

Testé contre une stack **qu'arrsenal n'a pas créée** : quatre conteneurs aux noms
libres, répartis sur **deux réseaux Docker différents**, dont deux Sonarr.

Résultat : `prowlarr → sonarr` établi et validé par le bouton Test, sur des conteneurs
étrangers, avec des clés API lues dans leurs `config.xml`.

Trois erreurs de conception que seul le test réel a révélées.

### Ne pas imposer son arborescence

Le premier essai a échoué : `Path '/data/media/tv' does not exist`. arrsenal appliquait
sa propre arborescence à une stack qui a la sienne.

**Adopter, c'est câbler des services entre eux, pas réorganiser les dossiers de
quelqu'un.** Les dossiers racine existants sont désormais lus et respectés ; quand il
n'y en a aucun, arrsenal le signale au lieu d'en inventer un. Même règle pour les
catégories qBittorrent : les écraser déplacerait des téléchargements en cours.

### `localhost` ne veut rien dire entre conteneurs

Deuxième échec : `Unable to complete application test, cannot connect to Sonarr`. Les
services adoptés vivent sur leurs propres réseaux — le nom de service compose n'y résout
pas — et **depuis l'intérieur d'un conteneur, `localhost` désigne ce conteneur**, pas la
machine.

`adopt` détecte donc l'adresse de la machine sur le réseau local, et refuse de continuer
s'il n'y arrive pas plutôt que de câbler des URL mortes.

### Un nom de conteneur ne prouve rien

`looks_like_arrsenal` reconnaissait ses propres conteneurs à leur nom
(`<projet>-<service>`). Un test a montré que `mon-sonarr` correspondait : arrsenal
**sautait en silence un conteneur qui ne lui appartenait pas**.

Les services générés portent maintenant un libellé `arrsenal.managed=true`, et la
détection le lit au lieu de deviner.

### Ce qui reste hors de portée

Le mot de passe d'un client de téléchargement existant est haché dans sa configuration :
illisible. `--dl-user` et `--dl-pass` le demandent explicitement, et l'étape échoue avec
un message clair plutôt qu'une erreur technique.

## autobrr et qui — vérifiés le 2026-08-31

Signalés par un utilisateur depuis [github.com/autobrr](https://github.com/autobrr).

| | |
|---|---|
| autobrr | `ghcr.io/autobrr/autobrr:v1.85.0`, port **7474** |
| qui | `ghcr.io/autobrr/qui:v1.27.0`, port **7476** |

### Quatre particularités d'autobrr, aucune devinable

**L'en-tête d'authentification est `X-API-Token`**, pas `X-Api-Key` comme les *arr. Le
mauvais en-tête donne un `403` sans explication. Vérifié en essayant les trois.

**Une clé API exige un champ `scopes`.** Sans lui, la création échoue en `500` sur une
contrainte SQL : `NOT NULL constraint failed: api_key.scopes`. Le message d'erreur est
d'ailleurs ce qui a permis de trouver le champ manquant.

**Sonarr, Radarr et Lidarr sont des « clients de téléchargement ».** autobrr ne distingue
pas les applications des clients : même endpoint `POST /api/download_clients`, seul le
`type` change. Types confirmés un par un : `SONARR`, `RADARR`, `LIDARR`, `QBITTORRENT`,
`TRANSMISSION`, `DELUGE_V2`, `SABNZBD`, `WHISPARR`, `READARR`.

**L'accueil n'est jouable qu'une fois.** `GET /api/auth/onboard` renvoie `204` tant
qu'aucun compte n'existe, puis `503 — user already registered`. C'est ce qui rend
l'étape rejouable.

### Une mise en garde qui ne s'applique pas au conteneur

La documentation avertit qu'autobrr écoute sur `127.0.0.1` par défaut, ce qui rendrait un
conteneur injoignable. **Vérifié : l'image génère `host = "0.0.0.0"`.** La mise en garde
vaut pour une installation hors conteneur.

### Résultat

Installation réelle avec Sonarr et qBittorrent : autobrr créé, compte initialisé, clé API
générée, les deux services déclarés — et **les deux tests de connexion déclenchés par
autobrr lui-même répondent `204`**.

`qui` écoute bien sur 7476, confirmé par ses propres journaux. C'est une interface : elle
découvre ses instances qBittorrent par son écran de configuration, aucun câblage
automatique n'est possible.

## Gluetun — vérifié le 2026-08-31

| | |
|---|---|
| Image | `qmcgaw/gluetun:v3.41.3` |
| Dépôt | `qdm12/gluetun` **redirige vers `passteque/gluetun`** — 15 356 étoiles, actif |
| Healthcheck | fourni par l'image : `/gluetun-entrypoint healthcheck`, 5 s, 3 essais |

### La liste des fournisseurs vient de Gluetun

Plutôt que de recopier une liste d'article, on lui a passé un nom invalide. Il répond
avec l'énumération exacte : `airvpn, cyberghost, expressvpn, fastestvpn, giganews,
hidemyass, ipvanish, ivpn, mullvad, nordvpn, perfect privacy, privado, private internet
access, privatevpn, protonvpn, purevpn, slickvpn, surfshark, torguard, vpnsecure, vpn
unlimited, vyprvpn, windscribe, custom, pia`.

C'est cette liste qui est dans `models.py`, et `arrsenal vpn-providers` l'affiche.

### Les deux modes n'exigent pas les mêmes champs

Constaté en lançant Gluetun à vide et en lisant ce qu'il réclame :

| Mode | Ce qu'il exige |
|---|---|
| `wireguard` | `WIREGUARD_PRIVATE_KEY`, et une **vraie clé base64** — il refuse toute autre chaîne |
| `openvpn` | `OPENVPN_USER` et `OPENVPN_PASSWORD` |

### Deux pièges du `network_mode: service:`

**Les ports du client doivent migrer vers Gluetun.** Un conteneur qui partage la pile
réseau d'un autre n'a plus de pile propre : il *ne peut plus* publier de port. Sans ce
transfert, l'interface du client devient injoignable — panne silencieuse et déroutante.

**Le client perd son alias DNS.** Vérifié contre Docker Compose 5.3 avec deux conteneurs
factices :

```
depuis un tiers :
  getent hosts client    -> rien
  getent hosts faux-vpn  -> 172.18.0.2
```

`http://qbittorrent:8080` ne résout donc plus : le câblage doit viser `http://gluetun:8080`.
Sans cette correction, activer le VPN cassait tout le câblage en silence.

### La propriété qui compte : aucune fuite possible

Testé avec des identifiants volontairement faux :

```
gluetun      running  Up 47 seconds (unhealthy)
qbittorrent  created  Created
dependency failed to start: container arrsenal-gluetun is unhealthy
```

**Le client de téléchargement ne démarre pas tant que le tunnel n'est pas établi.** Ce
n'est pas une intention, c'est le comportement observé : `depends_on` sur le healthcheck
de Gluetun ferme la porte avant qu'un seul paquet puisse sortir hors du VPN.


## Détection des mises à jour — vérifié le 2026-08-31

### Deux choses différentes s'appellent « mise à jour »

| | Comment on la voit | Ce qu'elle demande |
|---|---|---|
| **Reconstruction** | digest local != digest distant, même tag | `pull` + recréation |
| **Nouvelle version** | un tag plus récent existe | changer le tag, donc réécrire `stack.yml` |

LinuxServer republie ses images très souvent. Confondre les deux rendrait l'information
inutile.

### Le tag déployé devait sortir du code

`arrsenal` épinglait ses tags dans `catalog.py`. Conséquence non voulue : **personne
n'aurait pu mettre Sonarr à jour sans attendre une nouvelle version de l'outil.**
Le tag vit désormais dans `stack.yml` ; le catalogue ne fournit que la valeur initiale.

### Lister les tags : la pagination n'est pas un détail

Le protocole registry v2 renvoie les tags dans l'ordre de **publication** — les plus
anciens d'abord, par pages de 200. Mesuré sur `linuxserver/sonarr` : 25 pages et
**6,2 secondes** ne suffisaient pas à atteindre la version courante ; le listage
s'arrêtait encore sur des tags de Sonarr 3.x.

Solution retenue : quand le dépôt est aussi sur Docker Hub, son API accepte
`ordering=last_updated` et donne les plus récents d'abord — une page suffit. Le protocole
générique reste le repli pour les autres registres.

**`lscr.io` est bien un miroir de Docker Hub**, vérifié par comparaison de digests :
`lscr.io/linuxserver/sonarr:4.0.19` et `linuxserver/sonarr:4.0.19` renvoient le même
sha256. C'est ce qui autorise ce raccourci.

Mesures après correction, sur les trois registres :

| Image | Temps | Résultat |
|---|---|---|
| `lscr.io/linuxserver/sonarr:4.0.15` | 1,3 s | 4.0.19 |
| `qmcgaw/gluetun:v3.40.0` | 0,9 s | v3.41.3 |
| `ghcr.io/autobrr/autobrr:v1.80.0` | 2,1 s | v1.85.0 |

### Comparer des versions, pas des chaînes

`4.9.5` vient **avant** `4.16.1`, ce que le tri alphabétique inverse. Les tags sont
convertis en tuples d'entiers, et seuls ceux de la même convention sont comparés — un
dépôt mélange `v1.85.0`, `1.85`, `version-1.85.0` et `latest`.

### Le bug qui rendait la page muette

Un retour à la ligne mal échappé dans le source Python s'est retrouvé **au milieu d'une
chaîne JavaScript**. La chaîne n'était pas terminée : le script entier mourait, la page
se chargeait normalement et plus rien ne se mettait à jour — ni l'état, ni les versions.

Un test vérifie désormais qu'aucune chaîne du script servi ne franchit une ligne.

### Deux serveurs sur le même port, en silence

`HTTPServer` active `allow_reuse_address`. Sous Linux, `SO_REUSEADDR` n'autorise pas deux
écoutes simultanées ; **sous Windows, si** : un second `bind` réussit sans un mot, et les
requêtes partent au hasard vers l'un ou l'autre processus. Chacun ayant tiré son propre
jeton, la page répondait « jeton invalide » une fois sur deux.

Le serveur refuse désormais de partager son port. Vérifié : le second démarrage échoue
avec `WinError 10048`, et il ne reste qu'une écoute.

---

## Recyclarr 8.7.1 — vérifié le 2026-09-01

Image `ghcr.io/recyclarr/recyclarr:8.7.1`. Recyclarr synchronise les profils de qualité
et les *custom formats* des TRaSH Guides vers Sonarr et Radarr. `arrsenal` ne
réimplémente rien : il demande à Recyclarr de générer sa configuration à partir d'un
template **officiel**, puis n'y écrit que l'adresse et la clé API.

### Le conteneur n'a pas d'interface web

Il tourne sur une planification, `CRON_SCHEDULE=@daily` par défaut, et
`RECYCLARR_CONFIG_DIR=/config`. Trois conséquences dans le code :

- son `internal_port` vaut `0` et **aucun port n'est publié** ;
- le préflight ne contrôle pas son port : la ligne « port 0 : libre » n'apprenait rien
  et faisait douter du reste du tableau ;
- la page d'accès ne lui donne **pas** de lien. Elle en proposait un vers
  `http://192.168.1.10:0`, juste sous une note disant « Aucune interface web ». Un lien
  mort au milieu d'une page de raccourcis fait conclure que l'installation a échoué.

L'entrypoint est `/sbin/tini -- /entrypoint.sh` et prend les sous-commandes
directement : `--version`, pas `recyclarr --version`.

### `config create` ignore `--path`

`config create --template X --template Y` écrit **un fichier par template** dans
`/config/configs/X.yml`, quel que soit `--path`. Recyclarr charge ensuite tout le
dossier. La génération se fait donc par `docker compose run --rm --no-deps`, un
conteneur jetable : la configuration existe avant que le service planifié n'ait tourné
une seule fois.

22 templates officiels Sonarr, 25 Radarr, dont des profils français
(`french-multi-vf-hd-bluray-web`). La liste est lue sur le disque, dans les ressources
que Recyclarr clone au premier démarrage — pas recopiée dans le code, où elle
vieillirait.

### Les templates portent des marqueurs en clair

```yaml
sonarr:
  web-1080p:
    base_url: Put your Sonarr URL here
    api_key: Put your API key here
```

Ce sont les deux seules lignes que `arrsenal` remplace. Tout le reste vient du guide et
doit rester intact — c'est la garantie centrale du module.

### Deux défauts trouvés par les tests, pas par la lecture

**`\s` matche aussi le retour à la ligne.** Le motif se terminait par `\s*$` : gourmand,
il avalait les lignes vides qui suivaient le marqueur. Le fichier restait valide et la
synchronisation réussissait, mais `arrsenal` reformatait au passage un fichier qu'il
s'était engagé à ne pas toucher. Les motifs sont désormais bornés à l'espace
**horizontal**, `[^\S\n]`.

Vérifié sur les **47 templates officiels** : chacun est rempli, aucune autre ligne
modifiée, aucune ligne perdue.

**Une chaîne de remplacement n'est pas un texte.** `re.sub` interprète les antislashs
dans le remplacement. Une `url_base` saisie à la main en contenant un aurait levé
`bad escape` au lieu d'écrire le fichier. Le remplacement passe maintenant par une
fonction.

### Un nom de fichier n'est pas un identifiant

Première version : lister `official/<service>/templates/*.yml` et proposer les noms de
fichiers. Faux, et sur deux plans à la fois.

C'est `templates.json`, à la racine du dépôt cloné, qui fait foi. Il associe à chaque
fichier l'`id` que `config create --template` accepte, et les deux diffèrent souvent :

| Fichier | Identifiant |
|---|---|
| `sonarr/templates/german-hd-bluray-web.yml` | `sonarr-german-hd-bluray-web` |
| `radarr/templates/german-hd-bluray-web.yml` | `radarr-german-hd-bluray-web` |

11 des 22 templates Sonarr et 11 des 35 Radarr portent ce préfixe — il lève l'ambiguïté
entre deux fichiers homonymes. Le glob aurait donc proposé des noms que Recyclarr
refuse. Il ratait en plus les **10 templates rangés dans `radarr/templates/sqp/`**, qu'un
`glob("*.yml")` ne voit pas : 25 trouvés au lieu de 35.

`scripts/audit_templates.py` confronte les deux noms par défaut au manifeste publié et
sort non nul si l'un disparaît.

### Le manifeste est lisible sans télécharger l'image

Le premier démarrage du conteneur clone les dépôts de templates : **59 secondes**,
mesurées. Imposer cela avant même le récapitulatif de l'assistant serait absurde.

`https://raw.githubusercontent.com/recyclarr/config-templates/master/templates.json`
répond en 0,3 s, et son contenu est **identique octet pour octet** (sha256 comparé) à ce
que Recyclarr clone. L'assistant lit donc le disque quand Recyclarr a déjà tourné — c'est
ce que cette installation-là connaît — et interroge le dépôt sinon. Sans réseau, les
noms restent saisissables, simplement non vérifiés : ne pas pouvoir lister n'est pas une
raison d'arrêter quelqu'un qui sait ce qu'il veut.

Vérifié de bout en bout avec un profil français : `french-multi-vf-hd-bluray-web` →
57 custom formats et le profil `[French MULTi.VF] HD Bluray + WEB` créés dans Radarr.

### Recyclarr refuse d'écraser, et `wire` doit rester idempotent

`config create` s'arrête sur `The file /config/configs/hd-bluray-web.yml already
exists`. Le refus est légitime : le fichier a pu être modifié à la main. Mais
`arrsenal wire` est documenté comme rejouable, et il échouait donc au second passage.

`arrsenal` ne demande désormais que les templates **absents**. `--force` existe, mais
l'employer détruirait les réglages de l'utilisateur à chaque câblage.

Corollaire dans la lecture du résultat : un fichier déjà renseigné n'a plus de marqueur
à remplacer. Ce n'est pas un échec, c'est un second passage. Seul un marqueur *restant*
est un problème. Vérifié : trois `wire` d'affilée, tous `OK`, un seul appel à
`config create`.

### Le service visé est lu dans le YAML, pas dans le nom du fichier

`hd-bluray-web` est un titre de template, pas un nom de service. Se fier au nom de
fichier enverrait la clé de Radarr dans un fichier Sonarr. La clé racine du YAML fait
foi.

Un fichier laissé par une installation précédente — l'utilisateur avait Radarr, il l'a
retiré — garde ses marqueurs et fait échouer `recyclarr sync` avec un message obscur.
`arrsenal` le signale par son nom à la fin du câblage.

### Résultat, confirmé par Sonarr et Radarr eux-mêmes

Installation `sonarr,radarr,recyclarr` puis `recyclarr sync` :

| Vérification | Sonarr | Radarr |
|---|---|---|
| Custom formats créés | 37 | 40 |
| Tailles de qualité synchronisées | 14 | 14 |
| Profil créé | `WEB-1080p` | `HD Bluray + WEB` |
| Formats **notés** dans ce profil | 37 | 25 |

Les chiffres viennent de `GET /api/v3/qualityprofile` et `GET /api/v3/customformat`
interrogés avec la clé de chaque instance, pas des journaux de Recyclarr. Un profil dont
les formats seraient tous à zéro ne trierait rien : c'est le score qui compte, et il est
là.

### Détection de mise à jour sur ghcr.io

Le dépôt n'est pas sur Docker Hub : la voie générique du protocole registry v2
s'applique. Elle répond en ~1 s. Vérifié dans les deux sens, sans quoi « aucune mise à
jour » ne prouve rien :

- `8.7.1` → aucune plus récente (c'est bien la dernière) ;
- `7.4.1` → propose `8.6.0`, `8.7.0`, `8.7.1`.
