# 前端响应模型设计

## 页面数据体

| 页面 | 接口 | data 模型 | 主要内容 |
| --- | --- | --- | --- |
| 成员库 | `GET /api/members` | `MemberPage` | 全局档案、入住数量、参与账单数量 |
| 成员详情 | `GET /api/members/{memberId}` | `MemberDetail` | `member`、全部 `stays`、账单统计 |
| 账本列表 | `GET /api/books` | `BookPage` | 名称、介绍、活跃时间、入住与账单数量 |
| 账本详情 | `GET /api/books/{bookId}` | `BookDetail` | `book`、包含成员档案的 `stays`、状态计数 |
| 入住管理 | `GET /api/books/{bookId}/stays` | `StayPage` | Stay 字段、`member`、账单统计 |
| 账单列表 | `GET /api/books/{bookId}/bills` | `BillPage` | 摘要、垫付人姓名、人数、附件数 |
| 账单详情 | `GET /api/books/{bookId}/bills/{billId}` | `BillDetail` | 账单、垫付人、参与人 Member+Stay、分摊 |

所有 Page 模型继承公共 `PageData`，返回 `list/total/hasMore`。列表路由使用 `page` 和 `pageSize`；账单可先用 `month=YYYY-MM` 筛选再分页。

## 账单详情

```json
{
  "code":200,
  "message":"success",
  "data":{
    "bill":{
      "id":"b_001","bookId":1,"title":"电费","amountCents":4100,
      "date":"2026-03-31","method":"BY_DAYS",
      "participants":[1,2],"payerId":1,
      "period":{"start":"2026-03-01","end":"2026-03-31"},
      "status":"POSTED","attachments":[]
    },
    "payer":{"id":1,"name":"甲","createdAt":"2026-03-01T00:00:00Z","updatedAt":"2026-03-01T00:00:00Z"},
    "participants":[
      {
        "member":{"id":1,"name":"甲","createdAt":"2026-03-01T00:00:00Z","updatedAt":"2026-03-01T00:00:00Z"},
        "stay":{"bookId":1,"memberId":1,"joinDate":"2026-03-01","leaveDate":null,"createdAt":"2026-03-01T00:00:00Z","updatedAt":"2026-03-01T00:00:00Z"}
      }
    ],
    "shares":[
      {
        "billId":"b_001","memberId":1,"shareCents":2444,
        "effectiveDays":31,"weight":null,
        "member":{"id":1,"name":"甲","createdAt":"2026-03-01T00:00:00Z","updatedAt":"2026-03-01T00:00:00Z"},
        "stay":{"bookId":1,"memberId":1,"joinDate":"2026-03-01","leaveDate":null,"createdAt":"2026-03-01T00:00:00Z","updatedAt":"2026-03-01T00:00:00Z"}
      }
    ]
  }
}
```

前端可以直接读取 `participant.member.name`、`participant.stay.joinDate` 和 `share.shareCents`，无需按成员 ID 再发请求。Member 改名后再次查询会得到新名称；Stay 日期修改后未锁定按天账单会实时重新计算。

草稿的 `payer` 可以为 `null`，`participants` 和 `shares` 可以为空。`ShareDetail` 不持久化。F12 快照确认页面不在当前范围。
