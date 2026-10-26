import logging

import pytest

from tests.unit_tests.bedrock.anthropic_translator.helpers import convert, user


def test_conversion_warnings_use_the_project_logger(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG, logger="aidial_model_provider"):
        convert({**user("hi"), "top_k": 2, "inference_geo": "eu"})
    records = [
        record
        for record in caplog.records
        if record.name == "aidial_model_provider"
    ]
    assert any(
        record.levelno == logging.WARNING
        and "top_k, inference_geo" in record.message
        for record in records
    )
