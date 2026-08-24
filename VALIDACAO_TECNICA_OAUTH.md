# 🔍 VALIDAÇÃO TÉCNICA COMPLETA - OAUTH Google Drive

Data: 2026-08-22  
Status: INVESTIGAÇÃO EM PROGRESSO  
Objetivo: Validar 100% que a configuração OAuth está correta antes de executar

---

## 1️⃣ VALIDAÇÃO: ARQUIVO REALMENTE NECESSÁRIO

### ✅ CONFIRMADO: `backend/secrets/credentials.json` é obrigatório

**Rastreamento do código:**

```
usuario → POST /drive/oauth/login 
    ↓
backend/app/api/routers/drive.py::oauth_login() [linha 25-34]
    ↓
oauth.get_authorization_url() [backend/app/infrastructure/drive/oauth.py:34]
    ↓
Flow.from_client_secrets_file(settings.google_oauth_credentials_path) [linha 26]
    ↓
Lê: /app/secrets/credentials.json (em Docker)
    ou backend/secrets/credentials.json (local)
```

**Arquivo responsável**: `backend/app/infrastructure/drive/oauth.py`

**Bibliotecas usadas**:
- `google-auth-oauthlib` (Flow, exchange_code)
- `google.oauth2.credentials` (Credentials)
- `googleapiclient.discovery` (build service)

**Fluxo após autenticação**:
```
credentials.json (OAuth Client config)
    ↓
get_authorization_url() → URL de consentimento Google
    ↓
Usuario autoriza no Google
    ↓
exchange_code() → obtém token
    ↓
_save_credentials() → salva em backend/secrets/token.json
    ↓
load_credentials() → carrega token de token.json
    ↓
build("drive", "v3", credentials=token) → acessa Google Drive
    ↓
GoogleDriveRepository._get_service() [client.py:36-43]
    ↓
Acessa Drive: lê pastas, classifica documentos, baixa arquivos
```

---

## 2️⃣ VALIDAÇÃO: TIPO DE OAUTH CLIENT

### ✅ CONFIRMADO: Tipo "Web Application"

**Prova no código** (`backend/app/infrastructure/drive/oauth.py:26-31`):

```python
def _build_flow(state: str | None = None) -> Flow:
    settings = get_settings()
    return Flow.from_client_secrets_file(
        settings.google_oauth_credentials_path,
        scopes=SCOPES,
        redirect_uri=settings.google_oauth_redirect_uri,  # ← CRUCIAL
        state=state,
    )
```

**Razão**:
- Precisa de `redirect_uri` 
- Sistema fornece seu próprio endpoint de callback
- Isso é característica de "Web Application" OAuth, não "Desktop"

**Configuração esperada no Google Cloud**:
- Application type: **Web application** ✓
- Authorized redirect URIs: `http://localhost:8000/drive/oauth/callback` ✓

---

## 3️⃣ VALIDAÇÃO: APIS GOOGLE NECESSÁRIAS

### ✅ CONFIRMADO: Apenas Google Drive API

**Verificação no código:**

```
backend/app/infrastructure/drive/client.py:13
from googleapiclient.discovery import build
...
self._service = build("drive", "v3", credentials=creds)
```

**APIs necessárias**:
- ✅ **Google Drive API** → Obrigatória (acesso a arquivos)
- ✅ **Google Sheets API** → NÃO necessária (código não usa)
- ✅ **Google Docs API** → NÃO necessária (código não usa)

**Scopes solicitados** (linha 17 de oauth.py):
```python
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
```

✅ **Apenas LEITURA** (readonly) - Sem permissão de escrita

---

## 4️⃣ VALIDAÇÃO: QUAL CONTA GOOGLE

### ✅ CONFIRMADO: Qualquer conta com acesso à pasta "Importações"

**Configuração esperada**:
- Email: `amanda.martins@gocase.com` (ou a conta que tem acesso ao Drive)
- Acesso necessário: Pasta "Importações" no Google Drive (leitura)
- Tipo: Pessoal ou Google Workspace (não importa, contanto que tenha acesso)

**Verificação** (`backend/app/infrastructure/drive/client.py:220-235`):

```python
def _descobrir_processos_recursivo(self, folder_id: str) -> tuple[list[Processo], list[Embarque], list[Documento]]:
    # ... busca por "Importações" dinamicamente
    # ... não depende de Drive Compartilhado ou Shared Drive
```

**Conclusão**: 
- ✅ Funciona com conta pessoal
- ✅ Funciona com conta Google Workspace
- ✅ Não precisa de Shared Drive
- ✅ Apenas leitura é suficiente

---

## 5️⃣ VALIDAÇÃO: PERSISTÊNCIA DO TOKEN

### ✅ CONFIRMADO: Token é persistido em arquivo local

**Fluxo de persistência**:

```python
# backend/app/infrastructure/drive/oauth.py:54-58
def _save_credentials(creds: Credentials) -> None:
    settings = get_settings()
    os.makedirs(os.path.dirname(settings.google_oauth_token_path), exist_ok=True)
    with open(settings.google_oauth_token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
```

**Token é salvo em**: `backend/secrets/token.json`

**Carregado em**: `load_credentials()` (linha 61-71)

```python
def load_credentials() -> Credentials | None:
    settings = get_settings()
    if not os.path.exists(settings.google_oauth_token_path):
        return None  # ← Sem token, retorna None (não autorizado)
    with open(settings.google_oauth_token_path, encoding="utf-8") as f:
        data = json.load(f)
    creds = Credentials.from_authorized_user_info(data, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())  # ← Auto-refresh de tokens expirados
        _save_credentials(creds)
    return creds
```

**Persistência após restart**:
- ✅ Token salvo em arquivo
- ✅ Sobrevive ao `docker compose up`
- ✅ Sobrevive ao restart do container
- ✅ Auto-refresh funciona quando expirado

**Persistência após deploy**:
- ⚠️ DEPENDE da configuração de volumes no Docker

---

## 6️⃣ VALIDAÇÃO: DOCKER (VOLUMES E CAMINHOS)

### 🔍 INVESTIGANDO Dockerfile e docker-compose

Vou verificar como estão configurados os volumes...

