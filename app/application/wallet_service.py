from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.exceptions import (
    ConflictError,
    FeeConfigurationError,
    InsufficientBalanceError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from app.domain.fee import FeePolicy
from app.domain.money import Money
from app.domain.transaction import (
    TransactionStatus,
    TransactionType,
    transition,
)
from app.infrastructure.database.models import (
    FeeRuleModel,
    LedgerAccountModel,
    LedgerAccountType,
    LedgerDirection,
    LedgerEntryModel,
    TransactionModel,
    UserModel,
    WalletModel,
)
from app.security import generate_api_key, hash_api_key

ZERO = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class FeeCalculation:
    amount: Decimal
    fee_amount: Decimal
    rule_id: UUID | None
    rule_name: str | None


def create_user(session: Session, email: str) -> tuple[UserModel, str]:
    api_key = generate_api_key()
    user = UserModel(email=email, api_key_hash=hash_api_key(api_key))
    try:
        with session.begin_nested():
            session.add(user)
            session.flush()
    except IntegrityError as error:
        raise ConflictError(
            code="EMAIL_ALREADY_EXISTS",
            message="a user with this email already exists",
        ) from error
    return user, api_key


def create_wallet(session: Session, user_id: UUID) -> WalletModel:
    wallet = WalletModel(user_id=user_id)
    try:
        with session.begin_nested():
            session.add(wallet)
            session.flush()
            session.add(
                LedgerAccountModel(
                    account_type=LedgerAccountType.USER_WALLET.value,
                    account_key=f"WALLET:{wallet.id.hex}",
                    wallet_id=wallet.id,
                )
            )
            _get_or_create_channel_account(session)
            session.flush()
    except IntegrityError as error:
        raise ConflictError(
            code="WALLET_ALREADY_EXISTS",
            message="the user already has a CNY wallet",
        ) from error
    return wallet


def get_wallet_for_user(
    session: Session,
    wallet_id: UUID,
    user_id: UUID,
) -> WalletModel:
    wallet = session.get(WalletModel, wallet_id)
    if wallet is None:
        raise ResourceNotFoundError("wallet")
    if wallet.user_id != user_id:
        raise PermissionDeniedError
    return wallet


def deposit(
    session: Session,
    wallet_id: UUID,
    user_id: UUID,
    raw_amount: str,
    trace_id: str,
) -> TransactionModel:
    money = Money.from_value(raw_amount)
    wallet = _lock_owned_wallet(session, wallet_id, user_id)
    transaction = _new_transaction(
        transaction_type=TransactionType.DEPOSIT,
        amount=money.amount,
        trace_id=trace_id,
        destination_wallet_id=wallet.id,
    )
    session.add(transaction)
    session.flush()

    wallet.balance += money.amount
    wallet.version += 1
    _post_entry(
        session,
        transaction,
        _get_or_create_channel_account(session),
        LedgerDirection.DEBIT,
        money.amount,
    )
    _post_entry(
        session,
        transaction,
        _get_wallet_account(session, wallet.id),
        LedgerDirection.CREDIT,
        money.amount,
    )
    _succeed(transaction)
    session.flush()
    return transaction


def create_channel_deposit(
    session: Session,
    wallet_id: UUID,
    user_id: UUID,
    raw_amount: str,
    trace_id: str,
) -> TransactionModel:
    money = Money.from_value(raw_amount)
    wallet = _lock_owned_wallet(session, wallet_id, user_id)
    transaction = _new_transaction(
        transaction_type=TransactionType.DEPOSIT,
        amount=money.amount,
        trace_id=trace_id,
        destination_wallet_id=wallet.id,
    )
    session.add(transaction)
    session.flush()
    return transaction


def apply_channel_deposit_success(
    session: Session,
    transaction: TransactionModel,
) -> None:
    if transaction.destination_wallet_id is None:
        raise RuntimeError("channel deposit has no destination wallet")
    wallet = session.scalar(
        select(WalletModel)
        .where(WalletModel.id == transaction.destination_wallet_id)
        .with_for_update()
    )
    if wallet is None:
        raise ResourceNotFoundError("wallet")
    wallet.balance += transaction.amount
    wallet.version += 1
    _post_entry(
        session,
        transaction,
        _get_or_create_channel_account(session),
        LedgerDirection.DEBIT,
        transaction.amount,
    )
    _post_entry(
        session,
        transaction,
        _get_wallet_account(session, wallet.id),
        LedgerDirection.CREDIT,
        transaction.amount,
    )
    _succeed(transaction)


def withdraw(
    session: Session,
    wallet_id: UUID,
    user_id: UUID,
    raw_amount: str,
    trace_id: str,
) -> TransactionModel:
    money = Money.from_value(raw_amount)
    wallet = _lock_owned_wallet(session, wallet_id, user_id)
    if wallet.balance < money.amount:
        raise InsufficientBalanceError

    transaction = _new_transaction(
        transaction_type=TransactionType.WITHDRAWAL,
        amount=money.amount,
        trace_id=trace_id,
        source_wallet_id=wallet.id,
    )
    session.add(transaction)
    session.flush()

    wallet.balance -= money.amount
    wallet.version += 1
    _post_entry(
        session,
        transaction,
        _get_wallet_account(session, wallet.id),
        LedgerDirection.DEBIT,
        money.amount,
    )
    _post_entry(
        session,
        transaction,
        _get_or_create_channel_account(session),
        LedgerDirection.CREDIT,
        money.amount,
    )
    _succeed(transaction)
    session.flush()
    return transaction


def transfer(
    session: Session,
    source_wallet_id: UUID,
    destination_wallet_id: UUID,
    user_id: UUID,
    raw_amount: str,
    trace_id: str,
) -> TransactionModel:
    money = Money.from_value(raw_amount)
    if source_wallet_id == destination_wallet_id:
        raise ConflictError(
            code="SAME_WALLET_TRANSFER",
            message="source and destination wallets must be different",
        )

    wallets = _lock_wallet_pair(session, source_wallet_id, destination_wallet_id)
    source = wallets[source_wallet_id]
    destination = wallets[destination_wallet_id]
    if source.user_id != user_id:
        raise PermissionDeniedError
    if source.currency != destination.currency:
        raise ConflictError(
            code="CURRENCY_MISMATCH",
            message="wallet currencies must match",
        )
    fee = calculate_transfer_fee(session, raw_amount)
    total_debit = money.amount + fee.fee_amount
    if source.balance < total_debit:
        raise InsufficientBalanceError

    transaction = _new_transaction(
        transaction_type=TransactionType.TRANSFER,
        amount=money.amount,
        trace_id=trace_id,
        source_wallet_id=source.id,
        destination_wallet_id=destination.id,
    )
    session.add(transaction)
    session.flush()

    transaction.fee_amount = fee.fee_amount
    source.balance -= total_debit
    source.version += 1
    destination.balance += money.amount
    destination.version += 1
    _post_entry(
        session,
        transaction,
        _get_wallet_account(session, source.id),
        LedgerDirection.DEBIT,
        total_debit,
    )
    _post_entry(
        session,
        transaction,
        _get_wallet_account(session, destination.id),
        LedgerDirection.CREDIT,
        money.amount,
    )
    if fee.fee_amount > ZERO:
        _post_entry(
            session,
            transaction,
            _get_or_create_platform_fee_account(session),
            LedgerDirection.CREDIT,
            fee.fee_amount,
        )
    _succeed(transaction)
    session.flush()
    return transaction


def calculate_transfer_fee(session: Session, raw_amount: str) -> FeeCalculation:
    amount = Money.from_value(raw_amount).amount
    rule = session.scalar(
        select(FeeRuleModel)
        .where(
            FeeRuleModel.transaction_type == TransactionType.TRANSFER.value,
            FeeRuleModel.is_active.is_(True),
        )
        .order_by(
            FeeRuleModel.priority.desc(),
            FeeRuleModel.created_at.desc(),
            FeeRuleModel.id.desc(),
        )
        .limit(1)
    )
    if rule is None:
        raise FeeConfigurationError
    policy = FeePolicy.from_values(
        fixed_fee=rule.fixed_fee,
        percentage_rate=rule.percentage_rate,
        minimum_fee=rule.minimum_fee,
        maximum_fee=rule.maximum_fee,
        is_fee_free=rule.is_fee_free,
    )
    return FeeCalculation(amount, policy.calculate(amount), rule.id, rule.name)


def refund_transfer(
    session: Session,
    original_transaction_id: UUID,
    user_id: UUID,
    raw_amount: str,
    trace_id: str,
) -> TransactionModel:
    money = Money.from_value(raw_amount)
    original = session.scalar(
        select(TransactionModel)
        .where(TransactionModel.id == original_transaction_id)
        .with_for_update()
    )
    if original is None:
        raise ResourceNotFoundError("transaction")
    if original.type != TransactionType.TRANSFER.value:
        raise ConflictError(
            code="TRANSACTION_NOT_REFUNDABLE",
            message="only a successful transfer can be refunded",
        )
    if original.status not in {
        TransactionStatus.SUCCEEDED.value,
        TransactionStatus.REFUNDED.value,
    }:
        raise ConflictError(
            code="TRANSACTION_NOT_REFUNDABLE",
            message="only a successful transfer can be refunded",
        )
    if original.source_wallet_id is None or original.destination_wallet_id is None:
        raise RuntimeError("transfer transaction has an invalid wallet shape")

    wallets = _lock_wallet_pair(
        session,
        original.source_wallet_id,
        original.destination_wallet_id,
    )
    payer = wallets[original.source_wallet_id]
    payee = wallets[original.destination_wallet_id]
    if payer.user_id != user_id:
        raise PermissionDeniedError

    refunded_amount = session.scalar(
        select(func.coalesce(func.sum(TransactionModel.amount), ZERO)).where(
            TransactionModel.type == TransactionType.REFUND.value,
            TransactionModel.parent_transaction_id == original.id,
            TransactionModel.status == TransactionStatus.SUCCEEDED.value,
        )
    )
    already_refunded = Decimal(refunded_amount or ZERO)
    if already_refunded + money.amount > original.amount:
        raise ConflictError(
            code="REFUND_AMOUNT_EXCEEDED",
            message="cumulative refund amount cannot exceed the original transfer amount",
        )
    if payee.balance < money.amount:
        raise InsufficientBalanceError

    refund = _new_transaction(
        transaction_type=TransactionType.REFUND,
        amount=money.amount,
        trace_id=trace_id,
        source_wallet_id=payee.id,
        destination_wallet_id=payer.id,
        parent_transaction_id=original.id,
    )
    session.add(refund)
    session.flush()

    payee.balance -= money.amount
    payee.version += 1
    payer.balance += money.amount
    payer.version += 1
    _post_entry(
        session,
        refund,
        _get_wallet_account(session, payee.id),
        LedgerDirection.DEBIT,
        money.amount,
    )
    _post_entry(
        session,
        refund,
        _get_wallet_account(session, payer.id),
        LedgerDirection.CREDIT,
        money.amount,
    )
    _succeed(refund)
    if already_refunded + money.amount == original.amount:
        original.status = transition(
            TransactionStatus(original.status),
            TransactionStatus.REFUNDED,
        ).value
    session.flush()
    return refund


def get_transaction_for_user(
    session: Session,
    transaction_id: UUID,
    user_id: UUID,
) -> TransactionModel:
    transaction = session.get(TransactionModel, transaction_id)
    if transaction is None:
        raise ResourceNotFoundError("transaction")

    related_ids = {
        wallet_id
        for wallet_id in (
            transaction.source_wallet_id,
            transaction.destination_wallet_id,
        )
        if wallet_id is not None
    }
    owns_related_wallet = session.scalar(
        select(WalletModel.id)
        .where(WalletModel.id.in_(related_ids), WalletModel.user_id == user_id)
        .limit(1)
    )
    if owns_related_wallet is None:
        raise PermissionDeniedError
    return transaction


def _lock_owned_wallet(
    session: Session,
    wallet_id: UUID,
    user_id: UUID,
) -> WalletModel:
    wallet = session.scalar(
        select(WalletModel).where(WalletModel.id == wallet_id).with_for_update()
    )
    if wallet is None:
        raise ResourceNotFoundError("wallet")
    if wallet.user_id != user_id:
        raise PermissionDeniedError
    return wallet


def _lock_wallet_pair(
    session: Session,
    first_id: UUID,
    second_id: UUID,
) -> dict[UUID, WalletModel]:
    ordered_ids = sorted((first_id, second_id), key=str)
    wallets = session.scalars(
        select(WalletModel)
        .where(WalletModel.id.in_(ordered_ids))
        .order_by(WalletModel.id)
        .with_for_update()
    ).all()
    by_id = {wallet.id: wallet for wallet in wallets}
    if len(by_id) != 2:
        raise ResourceNotFoundError("wallet")
    return by_id


def _get_wallet_account(session: Session, wallet_id: UUID) -> LedgerAccountModel:
    account = session.scalar(
        select(LedgerAccountModel).where(
            LedgerAccountModel.wallet_id == wallet_id,
            LedgerAccountModel.account_type == LedgerAccountType.USER_WALLET.value,
        )
    )
    if account is None:
        raise ResourceNotFoundError("wallet ledger account")
    return account


def _get_or_create_channel_account(session: Session) -> LedgerAccountModel:
    account = session.scalar(
        select(LedgerAccountModel).where(
            LedgerAccountModel.account_type == LedgerAccountType.CHANNEL_CLEARING.value,
            LedgerAccountModel.currency == "CNY",
        )
    )
    if account is None:
        account = LedgerAccountModel(
            account_type=LedgerAccountType.CHANNEL_CLEARING.value,
            account_key="SYSTEM:CHANNEL_CLEARING:CNY",
            wallet_id=None,
        )
        session.add(account)
        session.flush()
    return account


def _get_or_create_platform_fee_account(session: Session) -> LedgerAccountModel:
    account = session.scalar(
        select(LedgerAccountModel).where(
            LedgerAccountModel.account_type == LedgerAccountType.PLATFORM_FEE.value,
            LedgerAccountModel.currency == "CNY",
        )
    )
    if account is None:
        account = LedgerAccountModel(
            account_type=LedgerAccountType.PLATFORM_FEE.value,
            account_key="SYSTEM:PLATFORM_FEE:CNY",
            wallet_id=None,
        )
        session.add(account)
        session.flush()
    return account


def _new_transaction(
    transaction_type: TransactionType,
    amount: Decimal,
    trace_id: str,
    source_wallet_id: UUID | None = None,
    destination_wallet_id: UUID | None = None,
    parent_transaction_id: UUID | None = None,
) -> TransactionModel:
    status = transition(TransactionStatus.PENDING, TransactionStatus.PROCESSING)
    return TransactionModel(
        type=transaction_type.value,
        status=status.value,
        source_wallet_id=source_wallet_id,
        destination_wallet_id=destination_wallet_id,
        parent_transaction_id=parent_transaction_id,
        amount=amount,
        fee_amount=ZERO,
        currency="CNY",
        trace_id=trace_id,
    )


def _post_entry(
    session: Session,
    transaction: TransactionModel,
    account: LedgerAccountModel,
    direction: LedgerDirection,
    amount: Decimal,
) -> None:
    session.add(
        LedgerEntryModel(
            transaction_id=transaction.id,
            account_id=account.id,
            direction=direction.value,
            amount=amount,
            currency="CNY",
        )
    )


def _succeed(transaction: TransactionModel) -> None:
    current = TransactionStatus(transaction.status)
    transaction.status = transition(current, TransactionStatus.SUCCEEDED).value
    transaction.completed_at = datetime.now(UTC)
