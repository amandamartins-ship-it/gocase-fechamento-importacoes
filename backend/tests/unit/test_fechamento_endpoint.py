"""Teste de integração ponta a ponta do endpoint /fechamento/processar via
HTTP (login JWT real), usando SQLite em memória no lugar do Postgres. Ao
contrário de /rateio/aplicar, este endpoint não depende do Drive - dá pra
testar o fluxo HTTP completo sem mockar nada do Google."""

from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain import entities
from app.infrastructure.db.base import Base
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.processo_repository import SqlAlchemyProcessoRepository
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


def _semear_processo_completo(SessionLocal, codigo: str) -> None:
    db = SessionLocal()
    try:
        embarque = entities.Embarque(codigo=f"{codigo}.1", drive_folder_id="f")
        for tipo in (entities.TipoDocumento.DI, entities.TipoDocumento.INVOICE_CI, entities.TipoDocumento.NOTA_FISCAL):
            embarque.documentos.append(
                entities.Documento(
                    ref=entities.DocumentoRef(drive_file_id=f"{codigo}-{tipo}", nome_arquivo="x.pdf", caminho="x"),
                    tipo=tipo,
                )
            )
        processo = entities.Processo(codigo=codigo, empresa_codigo=codigo[:3])
        processo.embarques = [embarque]
        SqlAlchemyProcessoRepository(db).salvar(processo)
    finally:
        db.close()


def _semear_lancamento(SessionLocal, processo_codigo: str, debito: str = "0", credito: str = "0") -> None:
    db = SessionLocal()
    try:
        SqlAlchemyRazaoRepository(db).salvar_lote(
            [
                entities.LancamentoRazao(
                    mes_referencia=MES,
                    historico=f"FRETE {processo_codigo}",
                    valor_debito=Decimal(debito),
                    valor_credito=Decimal(credito),
                    processos_codigos=[processo_codigo],
                    categoria_classificada=entities.CategoriaLancamento.FRETE,
                )
            ]
        )
    finally:
        db.close()


def test_processar_fechamento_end_to_end_via_http():
    client, SessionLocal = _client_e_sessionmaker()
    token = _login(client)

    _semear_processo_completo(SessionLocal, "GOC25129")
    _semear_lancamento(SessionLocal, "GOC25129", debito="0", credito="0")  # saldo zero -> Fechado

    resp = client.post(
        "/fechamento/processar",
        params={"mes_referencia": "2026-06-15"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_processos"] == 1
    assert body["processos_fechados"] == 1
    assert body["resultados"][0]["processo_codigo"] == "GOC25129"
    assert body["resultados"][0]["status"] == "Fechado"


def test_processar_fechamento_sem_token_e_rejeitado():
    client, _ = _client_e_sessionmaker()
    resp = client.post("/fechamento/processar", params={"mes_referencia": "2026-06-01"})
    assert resp.status_code == 401


def test_obter_fechamento_processo_via_http_apos_processar():
    client, SessionLocal = _client_e_sessionmaker()
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    _semear_processo_completo(SessionLocal, "GOC25129")
    _semear_lancamento(SessionLocal, "GOC25129")

    client.post("/fechamento/processar", params={"mes_referencia": "2026-06-01"}, headers=headers)

    resp = client.get("/fechamento/GOC25129", params={"mes_referencia": "2026-06-01"}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["processo_codigo"] == "GOC25129"
    assert len(resp.json()["composicao"]) >= 1


def test_obter_fechamento_processo_inexistente_da_404():
    client, _ = _client_e_sessionmaker()
    token = _login(client)
    resp = client.get(
        "/fechamento/GOC00000",
        params={"mes_referencia": "2026-06-01"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_dashboard_reflete_fechamento_processado():
    client, SessionLocal = _client_e_sessionmaker()
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    _semear_processo_completo(SessionLocal, "GOC25129")
    _semear_lancamento(SessionLocal, "GOC25129")
    client.post("/fechamento/processar", params={"mes_referencia": "2026-06-01"}, headers=headers)

    resp = client.get("/processos/dashboard", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_processos"] == 1
    assert body["processos_fechados"] == 1
    assert body["percentual_automacao"] == 100.0
