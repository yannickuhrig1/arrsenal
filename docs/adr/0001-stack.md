# ADR 0001 — Python plutot que Go

Statut : **acte** (2026-08-31)

## Contexte

L'outil doit tourner sur des NAS et des serveurs Linux ou l'on ne veut rien installer
sur le systeme hote. Le binaire statique de Go est l'argument evident.

## Decision

**Python 3.12 + Typer + Textual.**

## Justification

1. Le travail reel est de l'orchestration HTTP / JSON / YAML. Aucun besoin de
   performance qui justifierait Go.
2. La communaute homelab et *arr contribue en Python et en shell. L'objectif declare
   du projet est d'attirer des contributeurs : le langage doit leur etre familier.
3. Textual donne un wizard terminal spectaculaire pour un cout tres faible. C'est le
   GIF du README, donc un levier direct sur la visibilite.
4. L'argument « pas de Python sur un NAS » est neutralise par la distribution.

## Distribution

Deux chemins, aucun n'installe Python sur l'hote :

- `uvx arrsenal` pour ceux qui ont `uv`
- une image installeur qui pilote le Docker de l'hote via le socket monte.
  C'est le chemin documente par defaut pour Unraid et Synology.

## Consequences

- Le paquet declare peu de dependances : typer, httpx, pydantic, PyYAML, rich.
- Le coeur (`core/`) est teste sans Docker ni reseau. La CLI et le futur TUI
  consomment exactement les memes fonctions.
- Si le projet devait un jour cibler des environnements sans Docker du tout, cette
  decision serait a rouvrir.
