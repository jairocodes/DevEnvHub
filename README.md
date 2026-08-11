# DevEnv Hub

Gestor de entornos de desarrollo: CLI + API REST que permite a equipos definir, compartir y levantar entornos de desarrollo reproducibles con Docker Compose. El "GitHub Codespaces" self-hosted para equipos pequeños.

## Stack

Python · FastAPI · Docker SDK · Docker Compose · PostgreSQL · Redis · JWT Auth · WebSockets

## Estado

En construcción activa. Progreso:

- [x] Scaffolding: API FastAPI, CLI Click, Docker Compose de desarrollo (Postgres/Redis), tests, Gitflow.
- [x] Template de entorno end-to-end (Node): `templates/node/` + `ComposeService`/`DockerService` reales, creación/listado/borrado de entornos, logs en vivo por WebSocket.
- [x] Auth JWT real: registro/login (`/auth/register`, `/auth/login`), entornos protegidos y aislados por usuario (`devenv login`, `devenv register`).
- [x] Template Django (proyecto Django minimal real, SQLite por defecto).
- [x] Template Laravel (entorno PHP listo para recibir un proyecto Laravel real; starter con servidor built-in de PHP).
- [x] Template Spring (Spring Boot minimal real con Maven).
- [ ] Métricas de uso (CPU/memoria/uptime vía Docker stats).
- [ ] Multi-tenant a nivel de infraestructura (namespaces/quotas por usuario).
- [ ] Personalización interactiva de templates (elegir servicios/variantes al crear un entorno, ej. Laravel con Nginx+PHP-FPM vs. servidor simple).

## Flujo de ramas

Este repositorio usa **Gitflow**:
- `main`: releases estables.
- `develop`: rama de integración.
- `feature/*`, `release/*`, `hotfix/*`: trabajo en curso.
