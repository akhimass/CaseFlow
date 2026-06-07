from case_completeness import case_completeness, completeness_crossed


def test_completeness_threshold() -> None:
    data = {
        "accident_type": "rear_end",
        "accident_date": "2026-06-01",
        "state": "CA",
        "injuries": "whiplash",
        "fault_claim": "other driver ran red light",
        "caller_name": "Maria",
        "phone": "714-555-0100",
        "location": "Orange County",
    }
    assert case_completeness(data) >= 0.7
    assert completeness_crossed(data)
