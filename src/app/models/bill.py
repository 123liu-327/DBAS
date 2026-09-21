from datetime import date as Date
from enum import StrEnum

from pydantic import Field, StrictInt, model_validator

from app.models.attachment import Attachment
from app.models.base import CamelModel, StoredModel


##以下为手写
class SplitMethod(StrEnum):
    """账单分摊方式。

    EVEN：所有参与人平均分摊；BY_DAYS：根据有效入住天数分摊；
    BY_WEIGHT：根据前端为每位参与人设置的正整数权重分摊。
    """

    EVEN = "EVEN"
    BY_DAYS = "BY_DAYS"
    BY_WEIGHT = "BY_WEIGHT"
##手写区域结束


##以下为手写
class BillStatus(StrEnum):
    """账单业务状态，与 HTTP 状态码无关。

    DRAFT 是允许字段暂不完整的草稿；POSTED 是已入账且参与统计的账单；
    LOCKED、SETTLED 为结算流程预留，不能由普通创建或修改请求直接设置。
    """

    DRAFT = "DRAFT"
    POSTED = "POSTED"
    LOCKED = "LOCKED"
    SETTLED = "SETTLED"
##手写区域结束


##以下为手写
class BillPeriod(CamelModel):
    """按天分摊的闭区间，开始和结束日期当天都计入有效天数。"""

    start: Date
    end: Date

    @model_validator(mode="after")
    def check_dates(self) -> "BillPeriod":
        if self.end < self.start:
            raise ValueError("分摊周期结束日期不能早于开始日期")
        return self
##手写区域结束


##以下为手写
class Bill(StoredModel):
    """持久化账单模型。

    继承的 ``id``、``createdAt`` 和 ``updatedAt`` 由服务端生成。
    API 使用 camelCase 字段名，Python 内部使用 snake_case 字段名。
    ``ShareDetail`` 是查询时计算的结果，因此不作为 Bill 字段持久化。
    """

    # 账单只能属于一个账本。账本 ID 是正整数，对应 data/books/{bookId}/。
    book_id: StrictInt = Field(gt=0)

    # 草稿可以暂不填写名称；正式入账时名称必填，最多 20 个字符。
    title: str | None = Field(default=None, max_length=20)

    # 类别和备注是可选的展示信息，不参与分摊计算。
    category: str | None = None
    note: str | None = None

    # 金额始终使用整数“分”保存，例如 62.00 元保存为 6200。
    amount_cents: StrictInt | None = None

    # date 是记账日期，也是账单月份筛选和报表统计的依据。
    date: Date | None = None

    # method 决定使用平均、按天或按权重分摊。
    method: SplitMethod | None = None

    # 有序成员 ID 列表。顺序还用于最大余数法余数相同时的分配优先级。
    participants: list[StrictInt] = Field(default_factory=list)

    # payerId 是实际先行垫付整笔费用的成员，并且必须属于 participants。
    payer_id: StrictInt | None = None

    # period 仅在 BY_DAYS 时使用，实际权重由周期与成员入住日期的交集决定。
    period: BillPeriod | None = None

    # weights 仅在 BY_WEIGHT 时使用，键是成员 ID，值是该成员的正整数权重。
    # JSON 对象键会以字符串形式传输，例如 {"1": 3, "2": 1}，Pydantic
    # 会将键转换为 int。键集合必须与 participants 的成员 ID 集合完全一致。
    weights: dict[int, StrictInt] | None = None

    # 新建请求默认 POSTED；显式传 DRAFT 时允许保存不完整账单。
    status: BillStatus = BillStatus.DRAFT

    # 附件元数据随账单保存，实际文件位于所属账本的 attachments 目录。
    attachments: list[Attachment] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def check_bill(self) -> "Bill":
        """校验所有状态通用的规则，以及正式账单的完整性规则。"""

        # 以下规则对草稿和正式账单都生效，防止保存自相矛盾的数据。
        if len(self.participants) != len(set(self.participants)):
            raise ValueError("参与人不能重复")
        if any(member_id <= 0 for member_id in self.participants):
            raise ValueError("参与人 ID 必须为正整数")
        if self.amount_cents is not None and self.amount_cents <= 0:
            raise ValueError("账单金额必须为正整数分")
        if (
            self.payer_id is not None
            and self.participants
            and self.payer_id not in self.participants
        ):
            raise ValueError("垫付人必须属于参与人")
        if self.weights is not None and any(weight <= 0 for weight in self.weights.values()):
            raise ValueError("所有权重必须为正整数")

        # 草稿允许缺少业务字段；POSTED、LOCKED、SETTLED 必须是一笔完整账单。
        if self.status != BillStatus.DRAFT:
            if not self.title or not self.title.strip():
                raise ValueError("已入账账单必须填写名称")
            if self.amount_cents is None or self.date is None or self.method is None:
                raise ValueError("已入账账单必须填写金额、记账日期和分摊方式")
            if not self.participants or self.payer_id not in self.participants:
                raise ValueError("已入账账单必须包含参与人和垫付人")
            if self.method == SplitMethod.BY_DAYS and self.period is None:
                raise ValueError("按天分摊必须提供分摊周期")
            if self.method == SplitMethod.BY_WEIGHT:
                # 防止漏填某位参与人的权重，或者为非参与人提交多余权重。
                if self.weights is None or set(self.weights) != set(self.participants):
                    raise ValueError("按权重分摊必须为每位参与人提供且只提供一个权重")
        return self
##手写区域结束
