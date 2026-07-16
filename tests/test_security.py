from doc_harvester.security import sanitize_text_for_logging, sanitize_url_for_logging


def test_sanitize_url_for_logging_removes_query_fragment_and_credentials():
    result = sanitize_url_for_logging(
        "https://user:password@example.com/private/file.pdf?token=secret&download=1#page"
    )

    assert result == "https://example.com/private/file.pdf"
    assert "secret" not in result
    assert "password" not in result


def test_sanitize_url_for_logging_supports_relative_and_malformed_values():
    assert sanitize_url_for_logging("/download/file.pdf?signature=secret") == "/download/file.pdf"
    assert sanitize_url_for_logging("") == ""


def test_sanitize_text_for_logging_redacts_urls_inside_exceptions():
    result = sanitize_text_for_logging(
        "request failed for https://user:password@example.com/file?token=secret#fragment"
    )

    assert result == "request failed for https://example.com/file"
    assert "secret" not in result
    assert "password" not in result
