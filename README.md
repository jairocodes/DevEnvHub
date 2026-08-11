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
- [x] Métricas de uso en vivo (CPU/memoria/uptime por contenedor vía Docker stats, WebSocket + `devenv stats`).
- [x] Multi-tenant a nivel de infraestructura:
  - Namespaces: cada entorno usa su propio Compose project name (`devenv-{user_id}-{name}`), lo que le da red/contenedores/volúmenes aislados por entorno (más fino que por usuario) desde el primer template.
  - Quotas: tope de entornos concurrentes y límites de CPU/memoria por contenedor, con override opcional por usuario (`users.max_environments/cpu_limit/mem_limit_mb`, `NULL` = default global en `Settings`).
- [x] Personalización interactiva de templates (estilo Spring Initializr, solo CLI — no hay UI web):
  - `template.yaml` declara `options` (versión de runtime, incluir Postgres/Redis, y en Laravel el servidor: PHP built-in simple vs. Nginx+PHP-FPM real).
  - `devenv up` pregunta cada opción interactivamente, o se puede fijar sin prompts con `--set key=value` / `--yes`.
  - El servidor valida las opciones contra lo declarado en el template y renderiza el `docker-compose.yml`/`Dockerfile` condicionalmente con Jinja2.
- [x] Rol admin para gestionar quotas por usuario:
  - Bootstrap sin UI: `ADMIN_EMAILS` (allowlist por email) promueve automáticamente a admin en el siguiente login — sin endpoint de "promover a admin" para no abrir superficie de escalamiento de privilegios.
  - `GET /admin/users` / `PATCH /admin/users/{id}/quota` (protegidos, 403 si no es admin) y `devenv admin users` / `devenv admin set-quota <email>` en el CLI.

## Flujo de ramas

Este repositorio usa **Gitflow**:
- `main`: releases estables.
- `develop`: rama de integración.
- `feature/*`, `release/*`, `hotfix/*`: trabajo en curso.
