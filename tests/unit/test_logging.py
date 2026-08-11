import json
import logging

from rightjob.shared.logging import JsonFormatter


def test_json_formatter_drops_sensitive_extra_fields() -> None:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello", (), None)
    record.token = "must-not-appear"
    record.correlation_id = "correlation"

    payload = json.loads(JsonFormatter().format(record))

    assert "token" not in payload
    assert payload["correlation_id"] == "correlation"
