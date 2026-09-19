from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.exceptions import AuthenticationError
from app.infrastructure.database.models import UserModel, UserStatus
from app.infrastructure.database.session import get_db_session
from app.security import hash_api_key

bearer_security = HTTPBearer(
    auto_error=False,
    description="Use the API key returned when the user is created.",
)

# Close the yielded dependency before the response is sent.  This makes the
# commit in get_db_session() visible to an immediate follow-up request.
DatabaseSession = Annotated[
    Session,
    Depends(get_db_session, scope="function"),
]


def get_current_user(
    session: DatabaseSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_security),
    ],
) -> UserModel:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError

    user = session.scalar(
        select(UserModel).where(
            UserModel.api_key_hash == hash_api_key(credentials.credentials),
            UserModel.status == UserStatus.ACTIVE.value,
        )
    )
    if user is None:
        raise AuthenticationError
    return user


CurrentUser = Annotated[UserModel, Depends(get_current_user)]

IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    ),
]
