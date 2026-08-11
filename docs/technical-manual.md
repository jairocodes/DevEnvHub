# Manual técnico — DevEnv Hub

Este documento explica **todo lo que compone el sistema a nivel técnico**: arquitectura, modelo de datos, mecanismos internos, API completa, y las decisiones detrás de cada pieza. Está pensado para alguien que va a mantener o extender el código, no para el usuario final (para eso está [`user-manual.md`](./user-manual.md)).

## Índice

1. [Resumen y arquitectura](#1-resumen-y-arquitectura)
2. [Stack tecnológico](#2-stack-tecnológico)
3. [Estructura del repositorio](#3-estructura-del-repositorio)
4. [Modelo de datos](#4-modelo-de-datos)
5. [Autenticación y rol admin](#5-autenticación-y-rol-admin)
6. [Sistema de templates](#6-sistema-de-templates)
7. [Orquestación de Docker](#7-orquestación-de-docker)
8. [Referencia completa de la API REST](#8-referencia-completa-de-la-api-rest)
9. [Arquitectura del CLI](#9-arquitectura-del-cli)
10. [Multi-tenancy y quotas](#10-multi-tenancy-y-quotas)
11. [Flujo interno end-to-end](#11-flujo-interno-end-to-end)
12. [Testing](#12-testing)
13. [Control de versiones](#13-control-de-versiones)
14. [Variables de entorno](#14-variables-de-entorno)
15. [Limitaciones conocidas y backlog](#15-limitaciones-conocidas-y-backlog)

---

## 1. Resumen y arquitectura

DevEnv Hub tiene dos componentes, sin interfaz web:

- **`cli/`** — un cliente de línea de comandos (Click) que habla HTTP/WebSocket con la API. No contiene lógica de negocio: todo lo valida y ejecuta el servidor.
- **`api/`** — una API REST (FastAPI) que es la única que toca la base de datos y el daemon de Docker.

```mermaid
flowchart LR
    subgraph Cliente
        CLI["devenv (Click)\n~/.devenv/config.json"]
    end
    subgraph Servidor
        API["API REST (FastAPI)"]
        DB[(PostgreSQL)]
        REDIS[(Redis)]
    end
    subgraph Host Docker
        DAEMON["Docker daemon"]
        ENV1["Entorno de usuario A\n(red aislada)"]
        ENV2["Entorno de usuario B\n(red aislada)"]
    end

    CLI -- "HTTP + WebSocket\n(Bearer JWT)" --> API
    API -- "SQLAlchemy" --> DB
    API -.disponible para las apps de los entornos.-> REDIS
    API -- "docker-py + subprocess\n'docker compose'" --> DAEMON
    DAEMON --> ENV1
    DAEMON --> ENV2
```

La API nunca ejecuta código del usuario directamente: todo corre dentro de contenedores Docker, uno por entorno, aislados entre sí por su propia red de Compose (ver [sección 10](#10-multi-tenancy-y-quotas)).

## 2. Stack tecnológico

| Pieza | Tecnología | Uso |
|---|---|---|
| API | Python 3.12, FastAPI, Uvicorn | Servidor HTTP/WebSocket |
| CLI | Click | Comandos, prompts interactivos |
| ORM / migraciones | SQLAlchemy 2.0, Alembic | Modelos y esquema de base de datos |
| Base de datos | PostgreSQL 16 | Persistencia de usuarios y entornos |
| Cache/infra de apps | Redis 7 | Servicio opcional dentro de los entornos generados (no lo usa la API para sí misma) |
| Orquestación | Docker SDK (`docker-py`), `docker compose` (subprocess) | Crear/listar/parar contenedores; levantar/bajar stacks |
| Templating de infra | Jinja2 | Renderizar `docker-compose.yml`/`Dockerfile` por entorno |
| Auth | PyJWT, `bcrypt` | Tokens de sesión, hash de contraseñas |
| Config | `pydantic-settings` | Lectura de `.env` y variables de entorno |
| Cliente HTTP (CLI) | `httpx`, `websockets` | Llamadas a la API y streaming |
| Testing | `pytest`, SQLite in-memory | Suite automatizada |
| Lint | `ruff` | Estilo y errores estáticos |

## 3. Estructura del repositorio

```
DevEnvHub/
├── api/
│   ├── main.py              # instancia FastAPI, monta todos los routers
│   ├── core/
│   │   ├── config.py        # Settings (pydantic-settings)
│   │   ├── security.py      # JWT + hashing de passwords
│   │   ├── deps.py          # dependencies de auth (get_current_user, admin, ws)
│   │   └── paths.py         # BASE_DIR, TEMPLATES_DIR
│   ├── db/session.py        # engine, Base, get_db
│   ├── models/               # User, Environment (SQLAlchemy)
│   ├── schemas/               # Pydantic (request/response)
│   ├── routers/                # auth, environments, templates, admin, users
│   └── services/
│       ├── compose_service.py  # renderizado + subprocess docker compose
│       └── docker_service.py   # docker-py: contenedores, logs, stats
├── cli/main.py               # todos los comandos `devenv ...`
├── templates/{node,django,laravel,spring}/  # cada template: Dockerfile(s), compose, template.yaml, app starter
├── alembic/                  # migraciones
├── docker/                   # docker-compose.dev.yml + Dockerfile (infra de desarrollo del propio proyecto)
├── tests/
└── docs/                     # este manual y el de usuario
```

## 4. Modelo de datos

### `User` (`api/models/user.py`)

| Columna | Tipo | Notas |
|---|---|---|
| `id` | `int` PK | |
| `email` | `str` único | |
| `hashed_password` | `str` | bcrypt, nunca se expone en las respuestas |
| `is_admin` | `bool`, default `False` | ver [sección 5](#5-autenticación-y-rol-admin) |
| `max_environments` | `int \| None` | `NULL` = usa `Settings.default_max_environments` |
| `cpu_limit` | `float \| None` | `NULL` = usa `Settings.default_cpu_limit` |
| `mem_limit_mb` | `int \| None` | `NULL` = usa `Settings.default_mem_limit_mb` |
| `created_at` | `datetime` (tz-aware) | |

### `Environment` (`api/models/environment.py`)

| Columna | Tipo | Notas |
|---|---|---|
| `id` | `int` PK | |
| `user_id` | `int` | dueño del entorno (sin FK física a `users`, filtrado a nivel de aplicación) |
| `name` | `str` | nombre elegido por el usuario |
| `template` | `str` | `node`\|`django`\|`laravel`\|`spring` |
| `project_name` | `str` único | `devenv-{user_id}-{name}` — es el `-p` de `docker compose` |
| `port` | `int` | puerto host publicado |
| `status` | `str` | `starting`\|`running`\|`error` |
| `created_at` | `datetime` | |

### Migraciones (orden cronológico, `alembic/versions/`)

1. `9f9b65c1b89e` — crea `environments`.
2. `2bfd649f8588` — crea `users`.
3. `a7beeba57ba6` — agrega `max_environments`/`cpu_limit`/`mem_limit_mb` a `users`.
4. `7742f4e2c06d` — agrega `is_admin` a `users` (con `server_default=false` para no romper filas existentes).

Cada una se generó con `alembic revision --autogenerate` y se verificó manualmente que `upgrade` → `downgrade` → `upgrade` fuera reversible antes de aplicarla en desarrollo.

## 5. Autenticación y rol admin

**Registro** (`POST /auth/register`): valida email único, guarda `hash_password(password)` (bcrypt con salt aleatorio por usuario).

**Login** (`POST /auth/login`): verifica la contraseña con `verify_password`, y si las credenciales son válidas:
1. Si el email está en `settings.admin_email_list` (parseado desde `ADMIN_EMAILS`, coma-separado) y el usuario aún no es admin, lo promueve (`is_admin = True`) — **este es el único mecanismo para obtener el rol admin**, no existe un endpoint que lo haga directamente, para no exponer una vía de escalamiento de privilegios.
2. Emite un JWT: `create_access_token(subject=str(user.id))` → `{"sub": "<id>", "exp": <ahora + 60 min>}`, firmado con `HS256` y `settings.jwt_secret`.

**Dependencias de FastAPI** (`api/core/deps.py`):
- `get_current_user`: extrae el header `Authorization: Bearer <token>` vía `HTTPBearer`, decodifica el JWT, busca el `User` por el `sub`. 401 si el token es inválido/expirado o el usuario ya no existe.
- `get_current_admin_user`: envuelve a `get_current_user` y devuelve 403 si `not current_user.is_admin`.
- `get_current_user_ws(token, db)`: variante para WebSockets — no hay forma estándar de mandar un header `Authorization` al hacer un handshake de WebSocket desde cualquier cliente, así que el token viaja como **query param** (`?token=...`) en vez de header.

```python
# api/core/deps.py — el corazón de la protección de endpoints
def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: DbSession,
) -> User:
    payload = decode_access_token(credentials.credentials)   # lanza si el JWT es inválido
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(401, "Invalid token")
    return user
```

## 6. Sistema de templates

### `template.yaml` — esquema

Cada carpeta en `templates/<nombre>/` tiene un `template.yaml`:

```yaml
name: node
language: Node.js
description: Entorno Node.js con Postgres y Redis
default_port: 3000
env: [DATABASE_URL, REDIS_URL]        # solo informativo, documenta qué env vars espera la app
options:                               # lo que el CLI convierte en wizard interactivo
  - key: runtime_version
    label: "Versión de Node"
    type: choice                       # choice | boolean
    choices: ["18", "20", "22"]
    default: "20"
  - key: include_postgres
    label: "Incluir Postgres"
    type: boolean
    default: true
```

`GET /templates` simplemente lee y devuelve el YAML de cada carpeta (`api/routers/templates.py`) — el CLI y la validación del servidor comparten la misma fuente de verdad, no hay esquema duplicado en código Python.

### Los 4 templates

| Template | App starter | Particularidad |
|---|---|---|
| `node` | Servidor HTTP built-in de Node (`http` core, sin framework) | El más simple; sirve de plantilla base para los demás |
| `django` | Proyecto Django real minimal (`manage.py` + `config/`), SQLite por defecto | Es el "hello world" idiomático de Django, no un stub artificial |
| `spring` | Proyecto Spring Boot real minimal (`pom.xml` + una clase `@RestController`) | Build con Maven dentro del propio contenedor (`mvn spring-boot:run`) |
| `laravel` | Script PHP plano (documentado como punto de partida, no un scaffold de Laravel completo) | Única variante estructural: `server=simple` (PHP built-in) vs `server=nginx-fpm` (dos contenedores reales: `nginx` + `php-fpm`, con `nginx.conf` propio) |

### Motor de renderizado (`api/services/compose_service.py`)

`ComposeService.prepare_workspace(template_dir, workspace, context)`:
1. Copia cada archivo del template al workspace del entorno (`data/environments/<user_id>/<name>/`), **excepto** `template.yaml`/`README.md`.
2. Si el archivo está en `RENDERED_FILES` (`docker-compose.yml`, `Dockerfile`, `Dockerfile.fpm`, `pom.xml`, `nginx.conf`), lo procesa como plantilla Jinja2 con el `context` (puerto, límites de CPU/memoria, y las opciones resueltas del template).
3. Si es una carpeta (ej. `templates/django/config/`), la copia recursivamente (`shutil.copytree`, ignorando `__pycache__`).

Los `docker-compose.yml` usan control de flujo de Jinja2 directamente en YAML para incluir/excluir servicios:

```yaml
{%- if include_postgres %}
      DATABASE_URL: postgresql://devenv:devenv@postgres:5432/devenv
{%- endif %}
```

**Nota de encoding**: todas las lecturas/escrituras de estos archivos usan `encoding="utf-8"` explícito. `Path.read_text()` sin ese argumento cae al encoding por defecto del sistema operativo (en Windows, típicamente `cp1252`), lo que corrompía las tildes de los labels (`"Versión"` → mojibake) — bug real encontrado y corregido durante el desarrollo.

### Resolución y validación de opciones (`api/routers/environments.py::_resolve_options`)

```python
def _resolve_options(manifest: dict, submitted: dict) -> dict:
    declared = {opt["key"]: opt for opt in manifest.get("options", [])}
    if set(submitted) - set(declared):
        raise HTTPException(422, "Unknown template option(s): ...")
    resolved = {}
    for key, option in declared.items():
        value = submitted.get(key, option["default"])      # completa lo no enviado
        if option["type"] == "choice" and value not in option["choices"]:
            raise HTTPException(422, "...")
        resolved[key] = value
    return resolved
```

Esto es lo que le da seguridad de tipos al sistema de personalización: el servidor nunca confía en lo que manda el cliente sin verificarlo contra lo declarado en el propio `template.yaml`.

## 7. Orquestación de Docker

Dos servicios con responsabilidades separadas a propósito:

### `ComposeService` — orquesta el *stack* (subprocess a la CLI de `docker compose`)
- `up(compose_file, project_name)` → `docker compose -p <project_name> -f <compose_file> up -d --build`.
- `down(...)` → `... down`.
- `ps(...)` → `... ps --format json` (parseado línea por línea; no se usa actualmente pero queda expuesto).
- Por qué subprocess y no docker-py: el SDK de Python de Docker **no implementa Compose** — no hay forma de levantar un stack multi-servicio con dependencias sin invocar el binario/plugin `docker compose`.
- `project_name = devenv-{user_id}-{name}` es lo que le da a cada entorno su propia red, y namespacea los nombres de contenedor — dos entornos nunca comparten red aunque usen el mismo template.

### `DockerService` — inspecciona *contenedores individuales* (docker-py)
- `list_containers(project_name)`: filtra por la label `com.docker.compose.project` que Compose pone automáticamente.
- `stream_logs(project_name)`: generador que prefiere el contenedor con label `com.docker.compose.service=app` (si no existe, usa el primero) y hace streaming de sus logs.
- `get_stats(project_name)`: snapshot de CPU/memoria/uptime de **todos** los contenedores del entorno, en paralelo:

```python
def get_stats(self, project_name: str) -> list[dict]:
    containers = self.list_containers(project_name)
    with ThreadPoolExecutor(max_workers=len(containers)) as executor:
        return list(executor.map(_container_stats, containers))
```
  `container.stats(stream=False)` de docker-py tarda ~1-2s por contenedor; sin paralelizar, un entorno de 3 contenedores tardaba +5s en responder — se paralelizó para que las métricas se sientan "en vivo" de verdad.

- Cliente **perezoso**: `DockerService.client` es una `@property` que solo llama `docker.from_env()` la primera vez que se usa — así, importar el módulo (y por lo tanto los tests que no tocan Docker) no requiere tener el daemon corriendo.

### Cálculo de CPU% y memoria (`_cpu_percent`, `_memory_stats`)

Misma fórmula que usa el `docker stats` nativo:
- `cpu_percent = (cpu_delta / system_delta) * cores_online * 100`, donde los deltas son contra la muestra anterior que el propio daemon de Docker ya trae en la respuesta (`precpu_stats`).
- `mem_usage = usage - cache` (Docker cuenta la cache de páginas del kernel como "uso", lo cual es engañoso; se resta, igual que hace la CLI oficial).

### Por qué los WebSockets usan `asyncio.to_thread`

`container.logs(stream=True)` y `container.stats(stream=False)` son **llamadas bloqueantes** de docker-py. Iterarlas directamente dentro de una función `async def` bloquea el *único* event loop de Uvicorn — mientras un cliente escuchaba logs, **ninguna otra request** (de ningún usuario) podía ser atendida. Se detectó real durante las pruebas manuales (una segunda conexión WebSocket se quedaba colgada). La corrección: cada lectura bloqueante se ejecuta en un hilo del pool por defecto vía `await asyncio.to_thread(...)`, liberando el event loop entre lecturas.

## 8. Referencia completa de la API REST

Todas las rutas bajo `/auth` son públicas. Todo lo demás requiere `Authorization: Bearer <token>` salvo `GET /templates` y `GET /health`.

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `POST` | `/auth/register` | — | Crea cuenta. 409 si el email ya existe. |
| `POST` | `/auth/login` | — | Devuelve `{access_token, token_type}`. Auto-promueve a admin si aplica. 401 si las credenciales son inválidas. |
| `GET` | `/templates` | — | Lista los 4 templates con su `options` declarada. |
| `GET` | `/environments` | usuario | Lista **solo** los entornos del usuario autenticado. |
| `POST` | `/environments` | usuario | Crea un entorno. Body: `{name, template, options}`. 429 si se supera la quota, 404 si el template no existe, 422 si una opción es inválida, 500 si `docker compose up` falla. |
| `DELETE` | `/environments/{id}` | usuario (dueño) | Baja y borra el entorno. 404 si no existe o no es tuyo. |
| `WS` | `/environments/{id}/logs?token=` | usuario (dueño) | Streaming de logs del contenedor `app`. |
| `WS` | `/environments/{id}/metrics?token=` | usuario (dueño) | Snapshot de CPU/memoria/uptime cada ~2s. |
| `GET` | `/admin/users` | admin | Lista **todos** los usuarios con sus quotas. |
| `PATCH` | `/admin/users/{id}/quota` | admin | Actualiza `max_environments`/`cpu_limit`/`mem_limit_mb`. Campo omitido = sin cambios; `null` explícito = vuelve al default global (implementado con `payload.model_dump(exclude_unset=True)`). |
| `GET` | `/users` | — | **Stub heredado del scaffolding inicial** — siempre devuelve `[]`. No tiene relación con `/admin/users` y no se usa en ningún flujo real; ver [limitaciones](#15-limitaciones-conocidas-y-backlog). |
| `GET` | `/health` | — | `{"status": "ok"}`, para healthchecks. |

## 9. Arquitectura del CLI

`cli/main.py` es un único árbol de comandos Click:

```
devenv
├── register / login / logout          # api/routers/auth.py
├── up / down / ls / logs / stats       # api/routers/environments.py
└── admin
    ├── users                          # GET /admin/users
    └── set-quota                      # PATCH /admin/users/{id}/quota
```

- La sesión se guarda en `~/.devenv/config.json` (`{"access_token": "..."}`), leída por `_load_token()`/`_auth_headers()` antes de cada llamada autenticada.
- `API_BASE_URL` (env var `DEVENV_API_URL`, default `http://localhost:8000`) permite apuntar el mismo CLI a cualquier servidor.
- El wizard interactivo de `devenv up` (`_resolve_template_options`) hace `GET /templates`, encuentra el template pedido, y por cada opción declarada: si vino por `--set`, la castea (`_coerce_option_value`); si no vino y no se pasó `--yes`, la pregunta (`_prompt_for_option` usa `click.confirm`/`click.prompt` según el `type`); si no vino y sí se pasó `--yes`, la omite y el servidor aplica el default del template.
- `devenv logs`/`devenv stats`/`devenv down` comparten `_find_environment(name)` (resuelve nombre → id vía `GET /environments`).

## 10. Multi-tenancy y quotas

**Aislamiento** (namespaces): cada entorno, sin importar el usuario, es su propio `project_name` de Compose (`devenv-{user_id}-{name}`). Docker Compose crea una red bridge exclusiva por proyecto — dos entornos nunca comparten red ni pueden verse entre sí a nivel de contenedor, aunque sean del mismo usuario o de usuarios distintos. Esto existe desde el primer template (Node), no fue una feature añadida después.

**Quotas** (`api/routers/environments.py::create_environment`):
- **Tope de entornos concurrentes**: se cuenta cuántos `Environment` del usuario están `status="running"` y se compara contra `current_user.max_environments or settings.default_max_environments`. 429 si ya llegó al tope.
- **CPU/memoria por contenedor**: `current_user.cpu_limit or settings.default_cpu_limit` (núcleos) y `mem_limit_mb` análogo, inyectados al render de Jinja2 como `deploy.resources.limits.cpus`/`memory` en el `docker-compose.yml` del template. Esto **funciona con `docker compose up` normal** (sin Swarm) — Compose V2 traduce ese bloque a límites reales del contenedor incluso fuera de un swarm, verificado con `docker inspect` (`NanoCpus`, `Memory`).
- **Override por usuario**: las tres columnas de `User` son nullable; `NULL` = usa el default global. Solo un admin puede cambiarlas (`PATCH /admin/users/{id}/quota`).
- **Asignación de puertos** (`_allocate_port`): revisa los puertos de **todos** los entornos `running` del sistema (de cualquier usuario, no solo el actual) y evita colisiones — los puertos son un recurso del host Docker, compartido entre todas las cuentas.

## 11. Flujo interno end-to-end

Qué pasa exactamente cuando alguien corre `devenv up mi-app --template node --set include_redis=false --yes`:

```mermaid
sequenceDiagram
    participant U as devenv (CLI)
    participant A as API (FastAPI)
    participant DB as PostgreSQL
    participant C as ComposeService
    participant D as Docker daemon

    U->>A: GET /templates
    A-->>U: manifest de "node" (con sus options)
    Note over U: resuelve options: --set + defaults (--yes)
    U->>A: POST /environments {name, template, options}
    A->>DB: contar entornos running del usuario
    alt supera la quota
        A-->>U: 429 Environment quota exceeded
    else OK
        A->>A: _resolve_options (valida contra template.yaml)
        A->>DB: INSERT Environment status=starting
        A->>C: prepare_workspace(template_dir, workspace, context)
        C->>C: render Jinja2 (docker-compose.yml, Dockerfile)
        A->>C: up(compose_file, project_name)
        C->>D: docker compose -p ... up -d --build
        D-->>C: contenedores corriendo
        A->>DB: UPDATE Environment status=running
        A-->>U: 201 {id, name, port, status: running}
    end
```

## 12. Testing

- **Sin Docker real**: la mayoría de los tests (`tests/test_environments.py`, `test_admin.py`, `test_auth.py`, `test_templates.py`) usan una base SQLite en memoria (`create_engine("sqlite://", poolclass=StaticPool)`) inyectada vía `app.dependency_overrides[get_db]`, y un `TestClient` de FastAPI. Las llamadas a `ComposeService.prepare_workspace`/`up`/`down` se reemplazan con `monkeypatch` — así se prueba toda la lógica de negocio (auth, quotas, validación de opciones) sin necesitar el daemon de Docker.
- **Lógica pura, sin mocks**: `test_docker_service.py` prueba `_cpu_percent`/`_memory_stats`/`_uptime_seconds` con diccionarios de ejemplo — son funciones puras, no necesitan Docker ni una base de datos.
- **Verificación con Docker real**: no está automatizada (no hay Docker-in-CI configurado); se hizo manualmente en cada feature — levantar el entorno, `docker inspect`/`docker ps`/`curl` contra el puerto publicado, y limpiar todo al final. Es el único método usado para confirmar que un `docker-compose.yml` generado es válido de verdad (además de `docker compose config` como validación estructural rápida).
- Correr todo: `pytest -q` y `ruff check api cli tests` desde la raíz del repo (con el venv activado).

## 13. Control de versiones

**Gitflow** (extensión AVH, `git flow ...`):
- `main`: solo releases.
- `develop`: rama de integración — todo el trabajo termina acá.
- `feature/<nombre>`: una rama por unidad de trabajo (un template, una feature, un fix), fusionada a `develop` con `git flow feature finish` y borrada.

**Convención de commits**: varios commits pequeños y enfocados por feature (uno por archivo/mecanismo lógico: modelo+migración, lógica de negocio, tests, README) en vez de un solo commit gigante al finalizar — facilita revisar el historial y aislar cuándo se introdujo cada pieza.

## 14. Variables de entorno

Todas configurables por `.env` (ver `.env.example`) o variables de entorno reales; leídas por `api/core/config.py::Settings` (pydantic-settings).

| Variable | Default | Descripción |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://devenv:devenv@localhost:5432/devenv` | Conexión a Postgres |
| `REDIS_URL` | `redis://localhost:6379/0` | No la usa la API; queda disponible para servicios propios |
| `JWT_SECRET` | `change-me` | **Debe cambiarse en cualquier despliegue real** — firma los tokens de sesión |
| `JWT_ALGORITHM` | `HS256` | |
| `DATA_DIR` | `data` | Carpeta base donde viven los workspaces de cada entorno |
| `DEFAULT_MAX_ENVIRONMENTS` | `3` | Quota global de entornos concurrentes |
| `DEFAULT_CPU_LIMIT` | `0.5` | Núcleos por contenedor |
| `DEFAULT_MEM_LIMIT_MB` | `512` | Memoria por contenedor |
| `ADMIN_EMAILS` | *(vacío)* | Emails (coma-separados) que se auto-promueven a admin en su próximo login |

Del lado del CLI (no leída por la API):

| Variable | Default | Descripción |
|---|---|---|
| `DEVENV_API_URL` | `http://localhost:8000` | A qué servidor apunta el CLI |

## 15. Limitaciones conocidas y backlog

- **Sin interfaz web**: todo es CLI + API REST, por decisión explícita (ver discusión de personalización de templates).
- **Sin CI/CD configurado**: no hay `.github/workflows/`; los tests y el lint se corren manualmente. Sería el siguiente paso natural de madurez si el proyecto lo requiere.
- **`GET /users` es un stub muerto**: quedó del scaffolding inicial (`api/routers/users.py`), siempre devuelve `[]`, sin relación con `/admin/users`. No rompe nada porque nada lo usa, pero es dead code pendiente de limpiar.
- **`devenv logs` es de un solo contenedor**: si un entorno no tiene un servicio llamado `app` (no aplica a los 4 templates actuales, todos lo tienen), tomaría uno arbitrario. No hay flag para elegir servicio.
- **Rol admin sin gestión de administradores vía API**: promover/revocar admins solo se puede hacer editando `ADMIN_EMAILS` y reiniciando la API — no hay endpoint (a propósito, para no abrir una vía de escalamiento de privilegios).
- **Personalización de templates limitada a lo declarado**: versión de runtime + incluir Postgres/Redis + (solo Laravel) variante de servidor. No se puede, por ejemplo, agregar un servicio arbitrario nuevo (ej. Elasticsearch) sin tocar el `template.yaml`/`docker-compose.yml` del template a mano.
- **Sin recuperación de contraseña ni borrado de cuenta**.
