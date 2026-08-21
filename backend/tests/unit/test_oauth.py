"""Testa só a lógica que não depende de rede/Google real: ausência de token
salvo em disco deve resultar em "não conectado", sem levantar exceção."""

from types import SimpleNamespace

from app.infrastructure.drive import oauth


def _settings_falso(tmp_path):
    return SimpleNamespace(
        google_oauth_credentials_path=str(tmp_path / "credentials.json"),
        google_oauth_token_path=str(tmp_path / "token.json"),
        google_oauth_redirect_uri="http://localhost:8000/drive/oauth/callback",
    )


def test_load_credentials_retorna_none_quando_arquivo_nao_existe(tmp_path, monkeypatch):
    monkeypatch.setattr(oauth, "get_settings", lambda: _settings_falso(tmp_path))
    assert oauth.load_credentials() is None


def test_has_valid_token_false_quando_sem_token(tmp_path, monkeypatch):
    monkeypatch.setattr(oauth, "get_settings", lambda: _settings_falso(tmp_path))
    assert oauth.has_valid_token() is False
