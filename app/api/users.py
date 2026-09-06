from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.api.schemas import UserCreatedResponse, UserCreateRequest, WalletResponse
from app.application.exceptions import PermissionDeniedError
from app.application.wallet_service import create_user, create_wallet

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post(
    "",
    response_model=UserCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    payload: UserCreateRequest,
    session: DatabaseSession,
) -> UserCreatedResponse:
    user, api_key = create_user(session, payload.email)
    return UserCreatedResponse(
        id=user.id,
        email=user.email,
        status=user.status,
        api_key=api_key,
    )


@router.post(
    "/{user_id}/wallets",
    response_model=WalletResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_wallet(
    user_id: UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> WalletResponse:
    if current_user.id != user_id:
        raise PermissionDeniedError
    return WalletResponse.model_validate(create_wallet(session, current_user.id))
