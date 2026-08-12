from __future__ import annotations

import pytest

from settings import Settings


@pytest.mark.parametrize("field_name", ["allowed_ips", "blocked_ips", "asn_denylist", "city_whitelist"])
@pytest.mark.parametrize("line_ending", ["\r\n", "\r", "\n"])
def test_multivalue_settings_support_commas_newlines_and_comments(field_name: str, line_ending: str) -> None:
    value = line_ending.join(
        (
            " first, second ",
            "   # ignored comment",
            "",
            " third,, fourth ",
        )
    )

    settings = Settings.model_validate({field_name: value})

    assert getattr(settings, field_name) == "first,second,third,fourth"


@pytest.mark.parametrize("field_name", ["allowed_ips", "blocked_ips", "asn_denylist"])
def test_optional_multivalue_settings_normalize_comment_only_values_to_empty(field_name: str) -> None:
    settings = Settings.model_validate({field_name: "  # first comment\r\n\n\t# second comment\r"})

    assert getattr(settings, field_name) == ""


def test_multivalue_settings_do_not_treat_trailing_hash_as_inline_comment() -> None:
    settings = Settings.model_validate({"asn_denylist": "AS4134 # retained"})

    assert settings.asn_denylist == "AS4134 # retained"
