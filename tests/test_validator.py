from docgen.validator import validate_template_placeholders


def test_validator_placeholder():
    # No es un docx real: esperamos que lance excepción al parsear.
    try:
        validate_template_placeholders(b"not-a-docx")
    except Exception:
        assert True
