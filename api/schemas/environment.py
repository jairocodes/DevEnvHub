from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EnvironmentCreate(BaseModel):
    name: str
    template: str


class EnvironmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    template: str
    project_name: str
    port: int
    status: str
    created_at: datetime
