from bia_sentinela.security.redaction import redact, redact_obj


def test_redact_cpf_email_card() -> None:
    txt = "CPF 123.456.789-09, email joao@x.com, cartao 4111 1111 1111 1111"
    out = redact(txt)
    assert "[CPF]" in out and "[EMAIL]" in out and "[CARTAO]" in out
    assert "123.456.789-09" not in out


def test_redact_obj_recursive() -> None:
    obj = {"user": "a@b.com", "items": ["111.222.333-44", 10]}
    out = redact_obj(obj)
    assert out["user"] == "[EMAIL]"
    assert out["items"][0] == "[CPF]"
    assert out["items"][1] == 10
