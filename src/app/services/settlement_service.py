"""结算业务服务：按月份范围汇总净余额并生成可执行转账方案。"""

from app.algorithms.settling import min_transfers
from app.core.exceptions import AppError
from app.models.settlement import MemberBalance
from app.schemas.report import SettlementPlan, SettlementRange
from app.services.bill_service import posted_bills
from app.services.splitting_service import calculate_shares, stay_map
from app.storage import FileStore


def settlement_plan(store: FileStore, book_id: int, period: SettlementRange) -> SettlementPlan:
    """基于指定范围内的 POSTED 账单生成一次只读结算方案。"""

    stays = stay_map(store, book_id)
    if len(stays) > 6:
        raise AppError("TOO_MANY_MEMBERS", "结算算法最多支持6名成员", status_code=422)
    paid = dict.fromkeys(stays, 0)
    shares = dict.fromkeys(stays, 0)
    # 每笔账单增加垫付人的已付金额，再累计每位参与人的应分摊金额。
    for bill in posted_bills(store, book_id, period.start_month, period.end_month):
        paid[bill.payer_id] += bill.amount_cents
        for item in calculate_shares(bill, stays):
            shares[item.member_id] += item.share_cents
    balances = [
        MemberBalance(
            member_id=member_id, paid_cents=paid[member_id],
            share_cents=shares[member_id], net_cents=paid[member_id] - shares[member_id],
        )
        for member_id in stays
    ]
    net_sum = sum(item.net_cents for item in balances)
    # min_transfers 使用净余额计算最少转账；此接口不会创建结算快照。
    return SettlementPlan(
        start_month=period.start_month, end_month=period.end_month,
        balances=balances, net_sum_cents=net_sum, balanced=net_sum == 0,
        transfers=min_transfers([(item.member_id, item.net_cents) for item in balances]),
    )
