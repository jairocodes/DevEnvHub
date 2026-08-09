from fastapi import APIRouter

router = APIRouter(prefix="/environments", tags=["environments"])


@router.get("")
def list_environments() -> list:
    return []
