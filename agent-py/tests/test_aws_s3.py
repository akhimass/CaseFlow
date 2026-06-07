from aws_s3 import artifact_key, case_prefix, s3_configured, s3_uri


def test_artifact_paths() -> None:
    assert case_prefix("case-123") == "case-123/"
    assert artifact_key("case-123", "parsed/police_report.json") == (
        "case-123/parsed/police_report.json"
    )
    assert artifact_key("case-123", "transcript.jsonl") == "case-123/transcript.jsonl"


def test_s3_uri() -> None:
    assert s3_uri("case-1/transcript.jsonl").startswith("s3://")


def test_s3_configured_false_without_env(monkeypatch) -> None:
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    assert s3_configured() is False
