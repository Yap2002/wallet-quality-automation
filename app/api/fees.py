from fastapi import APIRouter

from app.api.dependencies import CurrentUser, DatabaseSession
from app.api.schemas import FeeCalculationRequest, FeeCalculationResponse
from app.application.wallet_service import calculate_transfer_fee

router = APIRouter(prefix="/api/v1/fees", tags=["fees"])


@router.post("/calculate", response_model=FeeCalculationResponse)
def calculate_fee(
    payload: FeeCalculationRequest,
    session: DatabaseSession,
    _current_user: CurrentUser,
) -> FeeCalculationResponse:
    calculation = calculate_transfer_fee(session, payload.amount)
    return FeeCalculationResponse(
        amount=calculation.amount,
        fee_amount=calculation.fee_amount,
        total_debit=calculation.amount + calculation.fee_amount,
        currency="CNY",
        rule_id=calculation.rule_id,
        rule_name=calculation.rule_name,
    )
