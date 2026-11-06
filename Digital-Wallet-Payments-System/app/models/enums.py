import enum


class Role(str, enum.Enum):
    ADMIN = "Admin"
    USER = "User"
    MERCHANT = "Merchant"


class KYCLevel(str, enum.Enum):
    MINIMUM = "Minimum"
    FULL = "Full"


class WalletStatus(str, enum.Enum):
    ACTIVE = "Active"
    FROZEN = "Frozen"


class KYCStatus(str, enum.Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class OTPPurpose(str, enum.Enum):
    HIGH_VALUE_TRANSFER = "High Value Transfer"
    ADD_BANK_ACCOUNT = "Add Bank Account"
    PIN_RESET = "PIN Reset"


class AccountType(str, enum.Enum):
    USER_WALLET = "User Wallet"
    MERCHANT_WALLET = "Merchant Wallet"
    BANK_SETTLEMENT = "Bank Settlement"
    CASHBACK_POOL = "Cashback Pool"
    FEES = "Fees"
    WITHDRAWAL_CLEARING = "Withdrawal Clearing"
    HOLD = "Hold"


class TxnType(str, enum.Enum):
    ADD_MONEY = "Add Money"
    P2P_TRANSFER = "P2P Transfer"
    MERCHANT_PAYMENT = "Merchant Payment"
    MERCHANT_REFUND = "Merchant Refund"
    CASHBACK = "Cashback"
    WITHDRAWAL = "Withdrawal"
    WITHDRAWAL_REVERSAL = "Withdrawal Reversal"
    REVERSAL = "Reversal"


class TxnStatus(str, enum.Enum):
    PENDING = "Pending"
    SUCCESS = "Success"
    FAILED = "Failed"
    ON_HOLD = "On Hold"
    REVERSED = "Reversed"


class EntryType(str, enum.Enum):
    DEBIT = "Debit"
    CREDIT = "Credit"


class RequestStatus(str, enum.Enum):
    PENDING = "Pending"
    PAID = "Paid"
    DECLINED = "Declined"
    CANCELLED = "Cancelled"
    EXPIRED = "Expired"


class WithdrawalStatus(str, enum.Enum):
    PENDING = "Pending"
    COMPLETED = "Completed"
    FAILED = "Failed"


class CashbackStatus(str, enum.Enum):
    PENDING = "Pending"
    CREDITED = "Credited"
    CANCELLED = "Cancelled"


class IdemStatus(str, enum.Enum):
    PROCESSING = "Processing"
    COMPLETED = "Completed"


class DecisionType(str, enum.Enum):
    APPROVED = "Approved"
    REJECTED = "Rejected"


class AddMoneySource(str, enum.Enum):
    UPI = "UPI"
    CARD = "Card"
    NET_BANKING = "Net Banking"


class SimulateStatus(str, enum.Enum):
    SUCCESS = "Success"
    FAILED = "Failed"
