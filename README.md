# Assistente de Fechamento Contábil de Importações

Reconstrói automaticamente a composição contábil de cada processo de importação
(BBIxxxxx/GOCxxxxx) da GOCASE: documentos, rateio, composição contábil e
validação contra o Razão. Projeto local (Docker Compose), independente do
portal "Radar de Fechamento" (bancos).

## Rodando localmente

1. Copie `.env.example` para `.env` e ajuste `ADMIN_EMAIL`/`ADMIN_PASSWORD`.
2. `docker compose up --build`
3. Backend: http://localhost:8000/docs (Swagger) · Frontend: http://localhost:5173

## Rodando os testes automatizados

```bash
docker compose run --rm backend pytest
```

Ou localmente, com um venv Python (fora do Docker):

```bash
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt  # ou .venv/bin/pip no Linux/Mac
.venv/Scripts/pytest  # ou .venv/bin/pytest
```

`pytest.ini` já configura o `pythonpath`, então não precisa setar `PYTHONPATH`
manualmente. Nenhum teste depende de Postgres/Drive/Docker de verdade — Drive
e Razão são sempre mockados/fake, e a persistência é validada com SQLite em
memória (inclusive testes de integração via HTTP real, com `fastapi.testclient`).

## Status atual (Fases 1-7 concluídas)

- [x] Docker Compose (postgres + backend FastAPI + frontend React/Vite).
- [x] Modelo de dados completo (SQLAlchemy) e migração inicial (Alembic).
- [x] Login JWT simples (usuário único, via `ADMIN_EMAIL`/`ADMIN_PASSWORD`).
- [x] OAuth Google Drive (login com a própria conta) + descoberta/classificação
      de processos/embarques/documentos na pasta Importações.
- [x] Upload do Razão Contábil (`POST /razao/upload`): parser tolerante a
      variações de cabeçalho/encoding/delimitador, extrai código(s) de
      processo do histórico via regex, classifica cada lançamento por
      categoria (Frete/Armazenagem/Honorários/AFRMM/Seguro/Capatazia/IOF/
      Mercadoria/Numerário/Reembolso/NF Entrada/Variação Cambial/Outras
      despesas) e reporta quantos lançamentos citam 2+ processos (candidatos
      a rateio, aplicado de fato na Fase 4).
- [x] Matriz Mestre de Rateio (`POST /rateio/aplicar?mes_referencia=YYYY-MM-01`):
      lê `Controle de Importações.xlsx` direto do Drive (baixado via API, sem
      precisar de upload manual), usa a aba **Controle PIs** (coluna NF é
      realmente compartilhada entre processos diferentes quando uma compra é
      consolidada - confirmado com o arquivo real: 61 casos), calcula
      `percentual = quantidade_itens_do_processo / quantidade_total_itens_da_NF`
      e aplica aos lançamentos do Razão que citam 2+ processos. Nunca força um
      rateio: sem NF em comum, NF ambígua (mais de uma em comum) ou sem
      quantidade real para algum processo viram pendência explícita
      (`GET /rateio/auditoria/{lancamento_id}` expõe a memória de cálculo
      completa por trás de qualquer valor rateado).
- [x] Motor de fechamento (`POST /fechamento/processar?mes_referencia=YYYY-MM-01`):
      para cada processo citado no Razão do mês (ou já sincronizado via Drive),
      reconstrói a composição contábil por categoria (soma dos lançamentos
      atribuídos, incluindo a parte rateada quando aplicável), calcula o saldo
      (débitos − créditos) e decide o status:
      - **Bloqueado** — falta DI/DUIMP, Invoice ou Nota Fiscal entre os
        documentos descobertos do processo.
      - **Pendente** — documentos completos, mas ainda há lançamento
        multi-processo sem rateio aplicado, ou o saldo não fechou além da
        tolerância de variação cambial (`TOLERANCIA_VARIACAO_CAMBIAL`, 2% por
        padrão).
      - **Fechado** — nenhum dos dois casos acima.
      `GET /fechamento/{processo_codigo}?mes_referencia=...` devolve o
      detalhe completo (composição por categoria + motivos) para o
      drill-down. O botão "Processar Fechamento" do frontend já encadeia os
      três passos: upload do Razão → aplicar rateio → processar fechamento →
      atualizar o dashboard, numa única ação.
      **Limitação conhecida, deliberada**: comparar o valor contabilizado com
      o valor real dos documentos (Invoice/NF) exigiria extrair valores de
      PDF/XLSX, o que não foi construído (ver nota abaixo) — `valor_documentos`
      fica sempre zero, nunca um número inventado.
- [x] Frontend completo:
      - **Seletor de mês** (`type="month"`) no topo, compartilhado por toda a tela.
      - **Tabela de processos** (`ProcessoTable`) persistente — carrega do
        backend (`GET /processos`) em vez de só mostrar o resultado do último
        processamento; clicar numa linha expande os lançamentos daquele
        processo (`GET /processos/{codigo}/lancamentos`).
      - **Drill-down de rateio**: cada lançamento rateado tem um botão "Ver
        rateio" que abre um modal com a memória de cálculo completa (NF,
        participantes, percentuais, valores, fórmula) via
        `GET /rateio/auditoria/{id}`.
      - **Motor de aprendizado**: painel "Correções" onde o usuário corrige a
        categoria de um lançamento (por trecho do histórico) ou o tipo de um
        documento (por trecho do nome do arquivo) — `POST /aprendizado/corrigir`
        grava a regra, que passa a ter prioridade sobre o dicionário estático
        no próximo upload/sincronização (`LancamentoClassifierComAprendizado`/
        `DocumentClassifierComAprendizado` decoram os classificadores das
        Fases 2/3). `GET /aprendizado/regras` lista as correções já feitas.
- [x] Testes automatizados (Fase 7): **173 testes**, todos sem depender de
      Postgres/Drive/Docker reais (Drive e Razão sempre via fake/mock,
      persistência validada com SQLite em memória, incluindo testes HTTP
      ponta a ponta com `fastapi.testclient`). `pytest.ini` deixa a suíte
      rodável com um simples `pytest` (sem setar `PYTHONPATH` na mão).
      Cobertura por área: classificação de documentos e lançamentos (com os
      dicionários calibrados contra nomes reais do Drive), descoberta/Drive,
      parsing do Razão, Matriz de Rateio (inclusive contra o layout real
      confirmado de `Controle de Importações.xlsx`), motor de fechamento
      (composição, validação, orquestração do mês inteiro), motor de
      aprendizado, e os principais endpoints HTTP (auth, razão, fechamento,
      processos/dashboard, aprendizado).

## Fase 8 — replicando "Importações em Andamento" / "Processos Fechados"

A Amanda compartilhou as planilhas reais que a equipe usa hoje (manualmente)
para fechar os processos: `Importações em Andamento.xlsx` (aba "Base 2026" =
o Razão consolidado, já com uma linha por processo participante quando um
lançamento é compartilhado) e `Processos Fechados.xlsx` (uma aba por processo
fechado, com essas linhas + total + "Saldo processo"). O sistema agora gera
essa mesma estrutura automaticamente:

- **Parser do Razão estendido**: agora captura também `Data`, `Unidade`,
  `Conta` e `Numero Contabil` por lançamento (antes só uma parte disso era
  guardada) - necessário para replicar as colunas reais.
- **`GerarLinhasRazaoRateadoUseCase`**: reproduz exatamente o que a equipe
  fazia à mão - "copiar a linha original uma vez por processo participante,
  dividindo o valor pelo rateio". Cada linha final é marcada com o status de
  fechamento (Fechado/Pendente/Bloqueado) calculado pelo motor da Fase 5.
- **`GET /processos/{codigo}/linhas-rateadas`**: mostra essas linhas dentro do
  próprio sistema (com totais e saldo), no drill-down de cada processo -
  substituiu a visão anterior, mais simples.
- **Dois exports .xlsx**, com o mesmo layout de colunas das planilhas reais:
  - `GET /fechamento/exportar/razao-atualizado.xlsx` — todas as linhas do mês,
    de todos os processos, com o status calculado (equivalente a atualizar a
    aba "Base" de *Importações em Andamento* automaticamente).
  - `GET /fechamento/exportar/processos-fechados.xlsx` — uma aba por processo
    com status Fechado no mês, linhas + total + "Saldo processo" (a "memória
    de cálculo" que hoje é montada copiando/colando).
- **Fora do escopo, deliberadamente**: a seção manual "Pendências Fechamento"
  (SDA, frete pendente, variação cambial por trading) que aparece nas abas
  reais de *Processos Fechados* depende de ler valores de dentro de
  propostas comerciais/faturas - mesma limitação de extração de documento já
  registrada abaixo. Continua sendo preenchida manualmente pela equipe depois
  de baixar o Excel gerado.

## Fase 9 — extração de valores dos documentos (FATURAMENTO FINAL)

A composição contábil (Fase 5) sempre soube comparar categorias entre si, mas
o campo "quanto o documento realmente diz" (`valor_documentos`) ficava sempre
zero — não tínhamos extração de valor de PDF. Esta fase implementa a primeira
fatia disso, calibrada contra 3 documentos reais (`3 - ARMAZENAGEM.pdf`,
`5 - HONORÁRIOS.pdf`, `1 - FRETE INTERNACIONAL.pdf` de `GOC25129.1`):

- **`extrair_valor_documento` (`app/infrastructure/extractors/valor_documento.py`)**:
  lê o texto real do PDF (`pdfplumber`, sem OCR — esses documentos têm camada
  de texto) e varre por vários marcadores conhecidos ("Valor a pagar", "Valor
  Total da NFS-e", "Total:" etc.), usando a **última ocorrência no texto**
  (o comprovante de pagamento bancário, que sempre vem depois do documento
  institucional original, reafirma o mesmo valor de forma mais simples e
  confiável). Nunca inventa: sem marcador reconhecido, retorna `None` e o
  documento fica pendente de revisão manual.
- **`categoria_do_documento` (`app/domain/documento_categoria.py`)**: mapeia
  o `TipoDocumento` da pasta FATURAMENTO FINAL para a `CategoriaLancamento` da
  composição (Frete/Armazenagem/Honorários/Numerário/Outras despesas — mesmo
  precedente do classificador de lançamentos para ICMS). Documentos fora
  dessa pasta (DI, PL, CI etc.) ficam fora do escopo desta fatia.
- **`ExtrairValoresDocumentosUseCase`**: baixa cada documento pendente do
  Drive, extrai o valor e persiste (`ProcessoRepository.atualizar_valor_documento`)
  — nunca reprocessa um documento já lido. Exposto via
  `POST /processos/{codigo}/extrair-valores`.
- **`MontarComposicaoUseCase` atualizado**: agora recebe os documentos do
  processo e preenche `valor_documentos`/`diferenca` de verdade por
  categoria — inclusive quando a despesa está documentada mas **ainda não
  contabilizada** no Razão (categoria aparece com contabilizado=0), que era
  exatamente o campo que faltava na tela "Pendências Fechamento".
- **Frontend**: no drill-down de cada processo, nova seção "Composição
  contábil × documentos" com o comparativo por categoria e o botão "Extrair
  valores dos documentos".
- **Fora do escopo desta fatia, deliberadamente**: qualquer documento fora da
  pasta FATURAMENTO FINAL (DI, Invoice/CI, Packing List etc.) e PDFs
  só-imagem (sem camada de texto, precisariam de OCR) continuam sem extração
  — não é uma limitação silenciosa, o documento simplesmente não entra no
  mapeamento e o valor documentado daquela categoria permanece 0.

## Todas as 7 fases planejadas (+ Fases 8 e 9) estão concluídas

O próximo passo real é rodar `docker compose up --build` com Postgres/Drive
de verdade para validar ponta a ponta o que até agora só dava para testar com
fakes/SQLite (o handshake OAuth real, uma sincronização real do Drive, uma
rodada real do motor de rateio contra o `Controle de Importações.xlsx` real,
os dois exports .xlsx contra dados reais, e a extração de valor contra os
PDFs reais do Drive).

**Fora do escopo, deliberadamente**: extração de valor para documentos fora
da pasta FATURAMENTO FINAL (DI, Invoice/CI, Packing List — teriam que ser
calibrados um por um contra amostras reais, como foi feito para os 8 tipos da
FATURAMENTO FINAL) e OCR de documentos-imagem. Dá pra encaixar como uma
extensão da Fase 9 depois, reaproveitando o mesmo padrão de calibração
hand-rolled.

## Configurando o acesso ao Google Drive (uma vez só)

1. Acesse https://console.cloud.google.com/ e crie (ou reaproveite) um projeto.
2. **APIs & Services → Library** → busque "Google Drive API" → **Enable**.
3. **APIs & Services → OAuth consent screen** → tipo **Internal** se o Google
   Workspace da GOCASE permitir (restringe a `@gocase.com`); senão **External**
   em modo de teste, adicionando o e-mail da Amanda como *test user*. Escopo:
   `.../auth/drive.readonly`.
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   - Application type: **Web application** (não "Desktop app" — o backend já
     expõe o próprio endpoint de callback, então o tipo Web é o correto aqui).
   - Authorized redirect URIs: `http://localhost:8000/drive/oauth/callback`
     (exatamente esse valor, ou ajuste `GOOGLE_OAUTH_REDIRECT_URI` no `.env`
     se mudar a porta do backend).
5. Baixe o JSON gerado, salve como `backend/secrets/credentials.json` (a pasta
   `secrets/` já está no `.gitignore` - nunca commitar esse arquivo).
6. `docker compose up --build`, abra http://localhost:5173, faça login, clique
   **"Conectar ao Google Drive"** (abre a tela de consentimento do Google numa
   aba nova), autorize com a conta da Amanda, feche a aba, clique
   **"Atualizar status"** (deve mostrar "Conectado") e depois
   **"Sincronizar documentos"**.

## O que a descoberta de documentos reconhece

Varre `Importações/<ano>/<GO COMERCIO|BB INDUSTRIA>/<processo>/...` sem
depender de nomes fixos: extrai o código do processo (`BBIxxxxx`/`GOCxxxxx`)
por regex, reconhece sub-pastas de embarque (`<processo>.<n>`), ignora
qualquer pasta `OLD` (versões substituídas) em qualquer profundidade, e
classifica cada arquivo por um dicionário de palavras-chave auditável (nunca
"caixa preta" - documentos sem regra clara viram tipo `OUTRO`, não um chute).
Testado com fixtures que reproduzem a estrutura real de 3 processos distintos
(`backend/tests/unit/test_keyword_classifier.py`,
`backend/tests/unit/test_drive_client.py`).
