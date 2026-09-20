"""Exact minimum-transfer search for at most six members."""

from functools import cache

from app.models.settlement import Transfer


def min_transfers(balances: list[tuple[int, int]]) -> list[Transfer]:
    if len(balances) > 6 or sum(amount for _, amount in balances) != 0:
        raise ValueError("Balances must sum to zero and contain at most six members")
    ids = [member_id for member_id, _ in balances]
    initial = tuple(amount for _, amount in balances)

    @cache
    def solve(state: tuple[int, ...]) -> tuple[tuple[int, int, int], ...]:
        first = next((index for index, value in enumerate(state) if value), None)
        if first is None:
            return ()
        best: tuple[tuple[int, int, int], ...] | None = None
        for partner in range(first + 1, len(state)):
            if state[first] * state[partner] >= 0:
                continue
            amount = min(abs(state[first]), abs(state[partner]))
            updated = list(state)
            if state[first] < 0:
                updated[first] += amount
                updated[partner] -= amount
                transfer = (first, partner, amount)
            else:
                updated[first] -= amount
                updated[partner] += amount
                transfer = (partner, first, amount)
            candidate = (transfer, *solve(tuple(updated)))
            if best is None or len(candidate) < len(best):
                best = candidate
        if best is None:
            raise ValueError("Unbalanced settlement state")
        return best

    return [
        Transfer(from_member_id=ids[source], to_member_id=ids[target], amount_cents=amount)
        for source, target, amount in solve(initial)
    ]
