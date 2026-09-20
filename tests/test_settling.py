import pytest

from app.algorithms.settling import min_transfers


@pytest.mark.parametrize(
    ("amounts", "minimum"),
    [
        ([21666, 1667, -8333, -15000], 3),
        ([-2000, 2000], 1),
        ([0, 0, 0], 0),
        ([3000, -1000, -1000, -1000], 3),
        ([10000, 0, -10000], 1),
        ([1000, 1000, -1000, -1000], 2),
        ([5000, -5000, 0], 1),
        ([1, -1], 1),
    ],
)
def test_official_s01_to_s08(amounts: list[int], minimum: int) -> None:
    balances = [(index + 1, amount) for index, amount in enumerate(amounts)]
    transfers = min_transfers(balances)
    assert len(transfers) == minimum
    remaining = dict(balances)
    for transfer in transfers:
        remaining[transfer.from_member_id] += transfer.amount_cents
        remaining[transfer.to_member_id] -= transfer.amount_cents
    assert all(amount == 0 for amount in remaining.values())
