import pytest

from comprehend_medical import extract_icd10_codes, local_icd10


@pytest.fixture(autouse=True)
def _no_aws(monkeypatch):
    """Force the deterministic local-map path (no AWS subscription needed)."""
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)


def test_local_icd10_codes_whiplash() -> None:
    codes = local_icd10(
        "Patient with acute whiplash and cervical strain after rear-end crash."
    )
    codes_by = {c["code"] for c in codes}
    assert "S13.4XXA" in codes_by
    assert all("description" in c and "severity" in c for c in codes)


@pytest.mark.asyncio
async def test_extract_uses_local_when_unconfigured() -> None:
    result = await extract_icd10_codes(
        "MRI shows a lumbar disc herniation; ongoing back pain."
    )
    assert result["source"] == "local"
    assert result["severity"] == "high"  # disc herniation rolls up to high
    assert any(c["code"] == "M51.26" for c in result["codes"])


@pytest.mark.asyncio
async def test_extract_empty_text() -> None:
    result = await extract_icd10_codes("   ")
    assert result == {"codes": [], "severity": None, "source": "none"}


@pytest.mark.asyncio
async def test_extract_no_injuries_recognized() -> None:
    result = await extract_icd10_codes(
        "Patient seen and discharged in stable condition."
    )
    assert result["source"] == "none"
    assert result["codes"] == []
