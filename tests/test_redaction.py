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


def test_redact_cpf_com_espacos() -> None:
    out = redact("meu cpf e 123 456 789 00 ok")
    assert "[CPF]" in out and "123 456 789 00" not in out


def test_redact_chave_pix_uuid() -> None:
    out = redact("chave pix 550e8400-e29b-41d4-a716-446655440000 confirmada")
    assert "[CHAVE_PIX]" in out
    assert "550e8400-e29b-41d4-a716-446655440000" not in out


def test_redact_agencia_e_conta() -> None:
    out = redact("Ag 1234-5 conta 67890-1 para deposito")
    assert "[AGENCIA]" in out and "[CONTA]" in out
    assert "1234-5" not in out and "67890-1" not in out


def test_conta_nao_e_rotulada_como_cartao() -> None:
    # Conta de 12 digitos + DV nao deve virar [CARTAO] (CONTA vem antes).
    out = redact("conta 123456789012-3 do cliente")
    assert "[CONTA]" in out and "[CARTAO]" not in out
