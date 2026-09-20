# API 说明

所有业务路径以 `/api` 开头。当前没有登录接口。

所有面向用户的 `message` 均返回中文。`error.code`、账单状态（如 `POSTED`）和字段名（如 `period.end`）属于稳定的程序协议，继续使用英文，前端应依据这些值进行逻辑判断。

## 资源路由

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET / POST | `/members` | 全局成员分页列表／创建成员档案 |
| GET / PATCH / DELETE | `/members/{memberId}` | 成员详情／改名／删除无入住关系的成员 |
| GET / POST | `/books` | 账本分页列表／创建账本 |
| GET / PATCH / DELETE | `/books/{bookId}` | 账本组合详情／修改／删除空账本 |
| GET / POST | `/books/{bookId}/stays` | 入住记录分页列表／登记入住 |
| GET / PATCH / DELETE | `/books/{bookId}/stays/{memberId}` | 入住详情／修改日期／删除未参与账单的入住记录 |
| GET / POST | `/books/{bookId}/bills` | 账单分页列表／创建账单 |
| GET / PATCH / DELETE | `/books/{bookId}/bills/{billId}` | 账单组合详情／修改／删除 |
| POST | `/books/{bookId}/bill-previews` | 计算预览，不写文件 |
| GET | `/books/{bookId}/statistics/member-shares?month=YYYY-MM` | 月度累计分摊 |
| POST | `/books/{bookId}/settlement-plans` | 月份范围余额和转账建议 |
| GET | `/books/{bookId}/statistics/monthly` | 最近六个月趋势 |
| GET | `/books/{bookId}/exports/bills.csv` | CSV 导出 |

附件接口仍位于 `/books/{bookId}/bills/{billId}/attachments`。原 `/books/{bookId}/members` 已删除。

## 成员与入住

创建全局成员：

```json
{"name":"张三"}
```

响应中的 `id` 是全局数字成员 ID。登记到某账本：

```json
{"memberId":1,"joinDate":"2026-03-01","leaveDate":null}
```

同一 `(bookId, memberId)` 只能有一条 Stay。删除 Stay 不删除 Member；Member 仍存在任何 Stay 时不能删除。修改成员姓名后，账单详情、CSV 和报表会读取最新姓名。

## 账单

创建默认直接 `POSTED`：

```json
{
  "title":"3月电费",
  "amountCents":6200,
  "date":"2026-03-31",
  "method":"BY_DAYS",
  "participants":[1,2],
  "payerId":1,
  "period":{"start":"2026-03-01","end":"2026-03-31"}
}
```

- `participants` 是有序数字成员 ID，决定最大余数同余数时的优先顺序。
- 垫付人和所有参与人都必须在当前账本有 Stay，且垫付人必须属于参与人。
- `EVEN` 平均分摊；`BY_DAYS` 使用周期与 Stay 的日期交集；`BY_WEIGHT` 使用正整数权重。
- 权重请求示例为 `"weights":{"1":2,"2":1}`；JSON 对象键是字符串，服务端转为数字成员 ID。
- 显式传 `"status":"DRAFT"` 可保存不完整草稿；补齐后 PATCH 为 `POSTED`。
- 请求不能设置 `LOCKED` 或 `SETTLED`，`POSTED` 不能退回 `DRAFT`。

`BillDetail` 返回 `bill`、垫付人 `payer`、包含 Member 与 Stay 的 `participants`、以及即时计算的 `shares`。草稿不计算分摊。

## 分页与响应

成员、账本、Stay、账单和附件列表支持 `page`、`pageSize`：

```json
{"list":[],"total":0,"hasMore":false}
```

成功创建返回 HTTP 201 且 `code=201`；查询和修改返回 200；删除返回无响应体的 204。错误示例：

```json
{"error":{"code":"STAY_IN_USE","message":"该入住成员已参与账单，不能删除入住记录","field":"memberId"}}
```

金额使用整数分。结算建议只读取 `POSTED` 账单，不产生付款或快照。F12 路由未开放。
