# DevEnv Hub

Gestor de entornos de desarrollo: CLI + API REST que permite a equipos definir, compartir y levantar entornos de desarrollo reproducibles con Docker Compose. El "GitHub Codespaces" self-hosted para equipos pequeños.

## Stack

Python · FastAPI · Docker SDK · Docker Compose · PostgreSQL · Redis · JWT Auth · WebSockets

## Estado

En construcción activa. Progreso:

- [x] Scaffolding: API FastAPI, CLI Click, Docker Compose de desarrollo (Postgres/Redis), tests, Gitflow.
- [x] Template de entorno end-to-end (Node): `templates/node/` + `ComposeService`/`DockerService` reales, creación/listado/borrado de entornos, logs en vivo por WebSocket.
- [x] Auth JWT real: registro/login (`/auth/register`, `/auth/login`), entornos protegidos y aislados por usuario (`devenv login`, `devenv register`).
- [ ] Templates adicionales (Django, Laravel, Spring).
- [ ] Métricas de uso (CPU/memoria/uptime vía Docker stats).
- [ ] Multi-tenant a nivel de infraestructura (namespaces/quotas por usuario).

## Flujo de ramas

Este repositorio usa **Gitflow**:
- `main`: releases estables.
- `develop`: rama de integración.
- `feature/*`, `release/*`, `hotfix/*`: trabajo en curso.
