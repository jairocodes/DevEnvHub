# Manual de usuario — DevEnv Hub

DevEnv Hub es una herramienta de línea de comandos (`devenv`) que habla con una API REST propia para crear, administrar y observar entornos de desarrollo reproducibles sobre Docker Compose. **No existe una interfaz web** — todas las acciones descritas en este manual se realizan desde la terminal.

Este manual cubre **todas las acciones posibles del sistema**, tanto para una cuenta de usuario normal como para una cuenta con rol de administrador.

## Índice

1. [Requisitos previos](#1-requisitos-previos)
2. [Instalación del CLI](#2-instalación-del-cli)
3. [Autenticación](#3-autenticación)
4. [Acciones de usuario normal](#4-acciones-de-usuario-normal)
5. [Los templates disponibles](#5-los-templates-disponibles)
6. [Acciones de administrador](#6-acciones-de-administrador)
7. [Errores comunes](#7-errores-comunes)

---

## 1. Requisitos previos

- **Docker Desktop** (o Docker Engine) instalado y **corriendo**. Cada `devenv up` construye y levanta contenedores reales — si Docker no está corriendo, el comando falla.
- **Python 3.12+** para instalar el CLI.
- Una instancia de la **API de DevEnv Hub** accesible (por defecto `http://localhost:8000`; configurable con la variable de entorno `DEVENV_API_URL`).

## 2. Instalación del CLI

Desde la raíz del repositorio:

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"   # Windows
# o: .venv/bin/pip install -e ".[dev]"  # Linux/macOS
```

Esto instala el comando `devenv` (entry point definido en `pyproject.toml`). Todos los ejemplos de este manual asumen que `devenv` está en el PATH (o se invoca como `./.venv/Scripts/devenv`).

## 3. Autenticación

Todas las acciones sobre entornos requieren estar logueado. El CLI guarda el token de sesión en `~/.devenv/config.json`.

| Comando | Qué hace |
|---|---|
| `devenv register --email <email> --password <pass>` | Crea una cuenta nueva. Si se omiten `--email`/`--password`, los pregunta interactivamente (la contraseña no se muestra en pantalla). |
| `devenv login --email <email> --password <pass>` | Inicia sesión y guarda el token localmente. Necesario antes de cualquier otra acción. |
| `devenv logout` | Borra el token local. Los siguientes comandos volverán a pedir `devenv login`. |

No existe "recuperar contraseña" ni "eliminar cuenta" — no están implementados en este sistema.

## 4. Acciones de usuario normal

Estas acciones están disponibles para **cualquier cuenta**, admin o no.

### 4.1. Crear un entorno — `devenv up`

```
devenv up <nombre> --template <template> [--set clave=valor ...] [--yes]
```

- `<nombre>`: nombre del entorno (identifica sus contenedores y su carpeta de trabajo).
- `--template`: uno de `node`, `django`, `laravel`, `spring` (ver [sección 5](#5-los-templates-disponibles)).
- Cada template declara **opciones personalizables** (versión del runtime, si incluir Postgres/Redis, etc.). Si no se fijan todas por `--set`, `devenv up` las **pregunta interactivamente** — es un asistente paso a paso, similar a Spring Initializr:

  ```
  $ devenv up mi-api --template node
  Versión de Node (18, 20, 22) [20]: 22
  Incluir Postgres [Y/n]: y
  Incluir Redis [Y/n]: n
  Environment 'mi-api' running on port 3000
  ```

- `--set clave=valor` (repetible): fija una opción sin que la pregunte. Ej: `--set include_redis=false --set runtime_version=22`.
- `--yes` / `-y`: no preguntar nada — cualquier opción no fijada con `--set` toma el valor por defecto del template. Ideal para scripts.

Ejemplo totalmente no interactivo:
```bash
devenv up mi-api --template laravel --set server=nginx-fpm --set include_redis=false --yes
```

Al terminar, el comando muestra el puerto donde quedó publicado el entorno (ej. `running on port 3000` → accesible en `http://localhost:3000`).

**Quotas**: cada cuenta tiene un límite de cuántos entornos puede tener corriendo a la vez (por defecto 3, ver [quotas](#quotas)). Superarlo devuelve un error (`Environment quota exceeded`) en vez de crear el entorno.

### 4.2. Listar entornos — `devenv ls`

```
devenv ls
```

Muestra únicamente **tus propios entornos** (nunca los de otros usuarios): id, nombre, template, estado y puerto.

### 4.3. Ver logs en vivo — `devenv logs`

```
devenv logs <nombre>
```

Transmite en tiempo real (WebSocket) la salida del contenedor principal (`app`) del entorno. Se corta con `Ctrl+C`.

### 4.4. Ver métricas de uso en vivo — `devenv stats`

```
devenv stats <nombre>
```

Transmite en tiempo real (cada ~2 segundos) el uso de CPU, memoria y el tiempo activo (uptime) de **cada contenedor** del entorno (app, y si aplica postgres/redis/nginx/php-fpm):

```
app     cpu 0.4%   mem 42.1/512.0 MB (8.2%)   uptime 130s
postgres  cpu 0.1%   mem 18.3/512.0 MB (3.5%)   uptime 132s
---
```

### 4.5. Borrar un entorno — `devenv down`

```
devenv down <nombre>
```

Detiene y elimina todos los contenedores del entorno (y su red de Docker). No se puede deshacer.

## 5. Los templates disponibles

`devenv up --template <nombre>` acepta uno de estos cuatro. Todos incluyen, si se activan, Postgres 16 y Redis 7 como servicios de apoyo; el puerto donde se publica la app lo asigna automáticamente el sistema, evitando colisiones con **cualquier** entorno corriendo en el mismo servidor (sea tuyo o de otro usuario) — los puertos son un recurso del host, compartido entre todas las cuentas.

| Template | Runtime | Opciones (`--set clave=valor`) |
|---|---|---|
| `node` | Node.js | `runtime_version` (`18`\|`20`\|`22`, default `20`), `include_postgres` (bool, default `true`), `include_redis` (bool, default `true`) |
| `django` | Python / Django | `runtime_version` (`3.11`\|`3.12`\|`3.13`, default `3.12`), `include_postgres`, `include_redis` |
| `spring` | Java / Spring Boot | `runtime_version` (`17`\|`21`, default `21`), `include_postgres`, `include_redis` |
| `laravel` | PHP | `runtime_version` (`8.2`\|`8.3`, default `8.3`), **`server`** (`simple`\|`nginx-fpm`, default `simple`), `include_postgres`, `include_redis` |

**Sobre `laravel --set server=...`**:
- `simple`: un solo contenedor con el servidor built-in de PHP. Rápido de levantar.
- `nginx-fpm`: topología real de producción — un contenedor `nginx` y otro `php-fpm` separados, comunicándose por FastCGI. Más representativo de un entorno Laravel real.

**Importante sobre los starters**: cada template incluye una aplicación mínima de ejemplo ("Hello from DevEnv Hub...") solo para que el entorno arranque y sea verificable de inmediato. Para trabajar en tu propio proyecto, reemplaza los archivos del workspace del entorno (bajo `data/environments/<tu_user_id>/<nombre>/`) por tu propio código — el `docker-compose.yml` generado sigue funcionando igual.

## 6. Acciones de administrador

### ¿Cómo se obtiene el rol admin?

No hay un endpoint ni un comando para "hacerse admin" (por seguridad). Quien opera el servidor configura la variable de entorno `ADMIN_EMAILS` (una o varias direcciones separadas por coma) en el `.env` de la API. La **próxima vez que esa cuenta haga `devenv login`**, queda promovida a admin automáticamente. No requiere reiniciar nada del lado del usuario.

### 6.1. Listar todos los usuarios — `devenv admin users`

```
devenv admin users
```

Muestra **todas** las cuentas del sistema (no solo la propia): id, email, si es admin, y su quota actual (`max_environments`, `cpu_limit`, `mem_limit_mb`). Un valor en blanco/`None` significa "usa el default global del servidor".

Requiere ser admin — cualquier otra cuenta recibe un error de permisos.

### 6.2. Ajustar la quota de un usuario — `devenv admin set-quota`

```
devenv admin set-quota <email> [--max-environments N] [--cpu-limit X] [--mem-limit-mb Y]
                                [--reset-max-environments] [--reset-cpu-limit] [--reset-mem-limit-mb]
```

- `--max-environments N`: máximo de entornos corriendo simultáneamente para ese usuario.
- `--cpu-limit X`: núcleos de CPU máximos por contenedor (ej. `0.5`).
- `--mem-limit-mb Y`: memoria máxima por contenedor, en MB.
- `--reset-*`: vuelve ese campo específico al default global del servidor (equivalente a "quitar el override").

Ejemplo — limitar a un usuario a un solo entorno a la vez:
```bash
devenv admin set-quota alguien@example.com --max-environments 1
```

Ejemplo — devolverle el límite de CPU al default global sin tocar lo demás:
```bash
devenv admin set-quota alguien@example.com --reset-cpu-limit
```

Un admin puede seguir usando todos los comandos de la [sección 4](#4-acciones-de-usuario-normal) normalmente — el rol admin solo **agrega** estas dos acciones, no quita nada.

<a id="quotas"></a>
### Sobre las quotas (aplica a todas las cuentas)

- **Tope de entornos concurrentes**: por defecto 3 (configurable globalmente por el servidor, u override por cuenta vía `admin set-quota`).
- **CPU/memoria por contenedor**: por defecto 0.5 núcleos / 512 MB por contenedor (mismo mecanismo de override).
- Cada entorno, sin importar el usuario, corre en su **propia red de Docker aislada** — dos usuarios pueden tener un entorno llamado igual sin chocar entre sí.

## 7. Errores comunes

| Código | Significado | Causa típica |
|---|---|---|
| `401 Unauthorized` | No autenticado o token inválido/expirado. | No se hizo `devenv login`, o pasó mucho tiempo desde el login. |
| `403 Forbidden` | Autenticado, pero sin permiso. | Un usuario normal intentando usar `devenv admin ...`. |
| `404 Not Found` | El recurso no existe. | Nombre de entorno o de template incorrecto. |
| `409 Conflict` | Ya existe algo con ese identificador. | Registrarse con un email ya usado. |
| `422 Unprocessable Entity` | Datos inválidos. | Una opción de template desconocida, o un valor fuera de las opciones válidas (ej. `runtime_version=99`). |
| `429 Too Many Requests` | Se superó la quota de entornos concurrentes. | Ya tienes el máximo de entornos corriendo — borra uno con `devenv down` o pide a un admin que suba tu límite. |
