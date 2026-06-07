import pytest

from post_call import build_post_call_package


@pytest.mark.asyncio
async def test_build_post_call_package_rules_only(monkeypatch) -> None:
    monkeypatch.delenv("TRUEFOUNDRY_GATEWAY_URL", raising=False)
    monkeypatch.delenv("TRUEFOUNDRY_API_KEY", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    package = await build_post_call_package(
        case_id="case-1",
        caller_id="user_1",
        case_data={
            "language": "es",
            "accident_type": "rear-end collision",
            "injuries": "whiplash",
            "location": "Orange County, CA",
        },
        transcript_lines=[
            {"speaker": "caller", "text": "Me chocaron por atrás", "language": "es", "turn": 1},
            {"speaker": "aria", "text": "Gracias por explicarme.", "language": "es", "turn": 1},
        ],
    )
    assert package["verbal_summary"]
    assert package["firm_brief"]
    assert package["intake_structured"]["accident_type"] == "rear-end collision"
    assert len(package["transcript_lines"]) == 2
