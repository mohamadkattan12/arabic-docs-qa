import pytest

from api.config import Settings


@pytest.mark.parametrize(("value", "expected"), [("", None), ("   ", None), ("sk-test", "sk-test")])
def test_empty_api_key_is_unset(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: str | None
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", value)
    key = Settings(_env_file=None).anthropic_api_key  # type: ignore[call-arg]
    assert (key.get_secret_value() if key else None) == expected
