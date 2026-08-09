from fastapi import APIRouter

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("")
def list_templates() -> list:
    return []
