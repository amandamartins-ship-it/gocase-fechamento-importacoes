from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain import entities
from app.infrastructure.db.base import Base
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.razao_repository import SqlAlchemyRazaoRepository

MES = date(2026, 6, 1)


def _client_e_sessionmaker():
    from fastapi.testclient import TestClient

    import app.main as main_module

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[get_db] = override_get_db
    return TestClient(main_module.app), TestingSessionLocal


def _login(client) -> str:
    from app.core.config import get_settings

    settings = get_settings()
    resp = client.post("/auth/login", json={"email": settings.admin_email, "password": settings.admin_password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_corrigir_classificacao_e_listar_regras():
    client, _ = _client_e_sessionmaker()
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/aprendizado/corrigir",
        json={"tipo": "classificacao", "padrao": "TAXA XPTO", "valor_corrigido": "Honorários", "justificativa": "recorrente"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    resp = client.get("/aprendizado/regras", headers=headers)
    assert resp.status_code == 200
    regras = resp.json()
    assert len(regras) == 1
    assert regras[0]["padrao"] == "TAXA XPTO"
    assert regras[0]["criado_por"] == "amanda.martins@gocase.com"


def test_corrigir_com_valor_invalido_e_rejeitado():
    client, _ = _client_e_sessionmaker()
    token = _login(client)
    resp = client.post(
        "/aprendizado/corrigir",
        json={"tipo": "classificacao", "padrao": "X", "valor_corrigido": "Categoria Que Não Existe"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_correcao_aplicada_reflete_no_proximo_upload_do_razao():
    client, _ = _client_e_sessionmaker()
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/aprendizado/corrigir",
        json={"tipo": "classificacao", "padrao": "TAXA XPTO", "valor_corrigido": "Honorários"},
        headers=headers,
    )

    csv = (
        "Conta;Descricao da Conta;Data;Numero Contabil;Unidade;Historico;Contrapartida;Tipo;Documento;"
        "Terceiro;Nome Terceiro;Valor a Debito;Valor a Credito;Saldo;Indicador D/C;Centro de Resultado\n"
        "111301;x;15/06/2026;411001;10001;PAGAMENTO TAXA XPTO PROCESSO GOC25129;;D;NF1;1;X;100,00;0,00;100,00;D;GO"
    ).encode("latin1")

    resp = client.post(
        "/razao/upload", headers=headers, files={"arquivo": ("razao.csv", csv, "text/csv")}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["por_categoria"] == {"Honorários": 1}


def test_listar_lancamentos_do_processo():
    client, SessionLocal = _client_e_sessionmaker()
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    db = SessionLocal()
    SqlAlchemyRazaoRepository(db).salvar_lote(
        [
            entities.LancamentoRazao(
                mes_referencia=MES, historico="FRETE GOC25129", valor_debito=Decimal("100"), valor_credito=Decimal("0"),
                processos_codigos=["GOC25129"], categoria_classificada=entities.CategoriaLancamento.FRETE,
            )
        ]
    )
    db.close()

    resp = client.get("/processos/GOC25129/lancamentos", params={"mes_referencia": "2026-06-01"}, headers=headers)
    assert resp.status_code == 200, resp.text
    lancamentos = resp.json()
    assert len(lancamentos) == 1
    assert lancamentos[0]["categoria"] == "Frete"
    assert lancamentos[0]["valor_debito"] == 100.0
