from fastapi import FastAPI

from api.routers import environments, templates, users

app = FastAPI(title="DevEnv Hub API")

app.include_router(environments.router)
app.include_router(templates.router)
app.include_router(users.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
