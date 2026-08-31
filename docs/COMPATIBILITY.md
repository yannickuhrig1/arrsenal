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
| Flood | `jesec/flood` | `4.16.1` | non testé en Phase 1 |

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

## Non vérifié à ce jour

- `TODO(verify)` — PUID/PGID par défaut sur Unraid et Synology (`layout.py`).
- Flood n'a pas encore été démarré dans une campagne de test.
- Aucun test sur Linux natif : la campagne a tourné sous Docker Desktop / WSL2.
  Le comportement des permissions y est plus permissif que sur un NAS réel.
