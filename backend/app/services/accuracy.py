from typing import List, Optional


def aggregate_accuracy_meters(acc_list: List[Optional[float]]) -> Optional[float]:
    vals = [a for a in acc_list if a is not None]
    if not vals:
        return None
    return float(sum(vals))

