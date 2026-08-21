"""Teste de integração ponta a ponta do endpoint /razao/upload via HTTP
(login JWT real + multipart upload real), usando SQLite em memória no lugar
do Postgres - não precisa de Docker para validar a rota completa."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.db.base import Base
from app.infrastructure.db.session import get_db
from tests.unit.test_razao_parser import _csv_bytes


def _client():
    from fastapi.testclient import TestClient

    import app.main as main_module

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[get_db] = override_get_db
    return TestClient(main_module.app)


def _login(client) -> str:
    from app.core.config import get_settings

    settings = get_settings()
    resp = client.post(
        "/auth/login", json={"email": settings.admin_email, "password": settings.admin_password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_upload_razao_end_to_end_via_http():
    client = _client()
    token = _login(client)

    resp = client.post(
        "/razao/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"arquivo": ("razao.csv", _csv_bytes(), "text/csv")},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_lancamentos"] == 4
    assert body["lancamentos_multi_processo"] == 1
    assert body["lancamentos_sem_processo"] == 1
    assert set(body["processos_citados"]) == {"GOC25129", "BBI25167"}
    assert body["mes_referencia"] == "2026-06-01"


def test_upload_razao_sem_token_e_rejeitado():
    client = _client()
    resp = client.post("/razao/upload", files={"arquivo": ("razao.csv", _csv_bytes(), "text/csv")})
    assert resp.status_code == 401


def test_upload_razao_arquivo_vazio_da_erro_claro():
    client = _client()
    token = _login(client)
    resp = client.post(
        "/razao/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"arquivo": ("razao.csv", b"", "text/csv")},
    )
    assert resp.status_code == 400
    assert "vazio" in resp.json()["detail"].lower()
