"""Pure seat-selection rules."""
from typing import List, Sequence, Set


def find_single_gap_violations(row_seat_ids: Sequence[int], selected: Set[int], taken: Set[int]) -> List[int]:
    """
    row_seat_ids : seat ids of ONE row, ordered by seat number
    selected     : seat ids the customer has selected (new + already locked by them)
    taken        : seat ids that are booked / locked by others / inactive

    A violation is a free seat that would be left alone between one of the customer's
    seats and another taken seat in the same row (e.g.  [mine][free][taken]).
    Returns the ids of those orphaned seats.
    """
    bad: List[int] = []
    n = len(row_seat_ids)
    for i in range(1, n - 1):
        sid = row_seat_ids[i]
        if sid in selected or sid in taken:
            continue
        left, right = row_seat_ids[i - 1], row_seat_ids[i + 1]
        if (left in selected and right in taken) or (left in taken and right in selected):
            bad.append(sid)
    return bad
