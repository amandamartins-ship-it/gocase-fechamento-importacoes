# Assistente de Fechamento Contábil de Importações — Especificação Técnica

> Documento de referência para reconstruir/orquestrar este processo como workflows no **n8n**. Todas as regras abaixo foram extraídas literalmente do sistema Python já implementado e validado (173 testes automatizados passando) em `C:\Users\Notebook\projetos\gocase-fechamento-importacoes\`. Nada aqui é hipotético — é o comportamento real do sistema em produção local.

---

## 1. Visão geral

Automatiza o fechamento contábil mensal dos processos de importação da GOCASE (embarques com código `BBIxxxxx` ou `GOCxxxxx`). Hoje isso é feito manualmente: alguém abre o Google Drive, procura os documentos de cada processo, confere valores, faz rateio manual de pagamentos compartilhados entre processos, e monta duas planilhas ("Importações em Andamento" e "Processos Fechados").

**Pipeline macro:**

```
Google Drive (documentos)  ──┐
                              ├──> Classificação de documentos
Razão Contábil (CSV/upload) ─┤         │
                              │         ▼
                              ├──> Motor de Rateio (divide pagamentos
                              │     compartilhados entre processos)
                              │         │
                              │         ▼
                              ├──> Composição Contábil por processo
                              │     (contabilizado × documentado)
                              │         │
                              │         ▼
                              └──> Motor de Fechamento
                                    (Fechado / Pendente / Bloqueado)
                                        │
                                        ▼
                          2 Excel de saída (Razão Atualizado,
                              Processos Fechados)
```

Todo o pipeline é **disparado por ação do usuário** (nunca em background/cron): sincronizar Drive, subir o Razão do mês, aplicar rateio, processar fechamento, extrair valores de documento. Isso mapeia bem para workflows n8n disparados manualmente ou por webhook — não há necessidade de nenhum agendamento automático.

**Princípio inegociável em todo o sistema: nunca inventar valor.** Qualquer situação ambígua (documento não encontrado, rateio sem NF em comum, valor não extraído de um PDF) vira uma **pendência explícita com motivo**, nunca um número chutado ou um "provavelmente está certo".

---

## 2. Estrutura de pastas no Google Drive

```
Importações/
  <ano, ex "2026">/
    <empresa, ex "GO COMERCIO" | "BB INDUSTRIA">/
      <PROCESSO - descrição - fornecedor>/        ex: "GOC25129 - Bag Charm (Linha Charms) - Newcom"
        <embarque, ex "GOC25129.1 - WMFIA261430">/
          DI - <num>.pdf
          <proc>.1 - PL.pdf
          <proc>.1 - CI.pdf
          GLME - GO.pdf
          HAWB.pdf
          NF <num> PROCESSO <proc>.pdf
          NUMERARIO <proc>.pdf
          RELATÓRIO DE ITENS.pdf
          ICMS.pdf
          INSTRUÇÃO DE DESEMBARAÇO - <proc>.xlsx
          PROTOCOLO DI.pdf
          RASCUNHO DE NOTA FISCAL DE ENTRADA.pdf
          COMPROVANTE DE IMPORTAÇÃO.pdf
          <NF-e solto>.xml
          <Trading> - FATURAMENTO FINAL (<proc>)/     ← pasta pré-categorizada pela trading
            1 - FRETE INTERNACIONAL.pdf
            2 - ICMS.pdf
            3 - ARMAZENAGEM.pdf
            4 - FRETE ENTREGA.pdf
            5 - HONORÁRIOS.pdf
            6 - NUMERÁRIO.pdf
            7 - PRESTAÇÃO DE CONTAS.pdf
            8 - DEVOLUÇÃO DO SALDO.pdf
Importações/Controle de Importações.xlsx    ← planilha mestre (~30 abas), usada pelo motor de rateio
```

A pasta `FATURAMENTO FINAL` é "ouro": os 8 arquivos já vêm numerados/categorizados pela trading, então o mapeamento arquivo→categoria contábil é direto, sem precisar adivinhar por conteúdo.

---

## 3. Regras de descoberta de processos/embarques

```
FOLDER_MIME = "application/vnd.google-apps.folder"
PROCESSO_REGEX = ^((?:BBI|GOC)\d{5})\b(.*)$
EMBARQUE_REGEX = ^((?:BBI|GOC)\d{5}\.\d+)\b(.*)$
```

**Ignorar pastas "OLD"**: qualquer pasta cujo nome, após `.strip().lower()`, seja exatamente `"old"` (comparação exata, não substring) é ignorada em qualquer nível de profundidade da árvore.

**Algoritmo de varredura (`listar_processos`):**
1. Localizar a pasta `Importações` na raiz do Drive (query: `name = 'Importações' and mimeType = 'application/vnd.google-apps.folder' and trashed = false`).
2. Dentro dela, só entram subpastas cujo nome bate `\d{4}` (ano) — outras são ignoradas.
3. Dentro de cada pasta de ano, toda subpasta é tratada como "empresa" (sem filtro de nome).
4. Dentro de cada pasta de empresa: pastas que batem `PROCESSO_REGEX` viram um Processo (`codigo, resto = match.groups()`; `descricao = resto.lstrip(" -").strip()`; `empresa_codigo = codigo[:3]`); pastas que não batem (ex "FIRST - IMP-02 12737") são ignoradas.
   - `fornecedor` = último segmento de `descricao` split por `" - "`, se houver.
5. Dentro da pasta do processo: subpastas que batem `EMBARQUE_REGEX` viram um Embarque de verdade; as demais (não-ignoradas, não-embarque) são "pastas soltas".
   - `referencia_trading` do embarque = texto após o primeiro `" - "` no nome da subpasta, se houver.
6. **Embarque implícito**: qualquer arquivo solto direto na pasta do processo, OU dentro de uma "pasta solta", é agrupado num Embarque sintético cujo `codigo` = o próprio código do processo (garante que nenhum documento se perca, mesmo em processos sem subpasta de embarque dedicada — ex. processos de "Serviço").
7. Classificação de cada arquivo encontrado via o classificador de documentos (seção 4).

---

## 4. Classificação de documentos

Decide primeiro se o caminho do arquivo indica a pasta `FATURAMENTO FINAL` (`/faturamento\s*final/i` no caminho completo); se sim, usa a lista `FATURAMENTO_FINAL`; senão, usa `GERAL`. Em ambas, testa os regex **nesta ordem** contra o **nome do arquivo** (case-insensitive); o primeiro que bater vence; se nenhum bater → `OUTRO` (pendência explícita, nunca um chute).

**Lista `GERAL` (ordem importa):**

| # | Regex (case-insensitive) | TipoDocumento |
|---|---|---|
| 1 | `protocolo\s*di` | PROTOCOLO_DI |
| 2 | `rascunho.*nota\s*fiscal` | RASCUNHO_NF_ENTRADA |
| 3 | `\bcomprovante\s*de\s*importa[cç][aã]o\b` | COMPROVANTE_IMPORTACAO |
| 4 | `relat[oó]rio\s*de\s*itens` | RELATORIO_ITENS |
| 5 | `instru[cç][aã]o\s*de\s*desembara[cç]o` | INSTRUCAO_DESEMBARACO |
| 6 | `numer[aá]rio` | NUMERARIO |
| 7 | `\bicms\b` | ICMS |
| 8 | `\bduimp\b\|\bdi\s*-\|\bdi\s+\d\|^di\b` | DI |
| 9 | `\bpacking\s*list\b\|(?<![a-z])pl\s*-\|-\s*pl\b\|-\s*pl\s` | PACKING_LIST |
| 10 | `\bglme\b` | GLME |
| 11 | `\b(o?hawb\|awb\|h?bl)\b` | AWB_HAWB |
| 12 | `\.xml$` | XML_NFE |
| 13 | `\bnf\b\|\bnota\s*fiscal\b` | NOTA_FISCAL |
| 14 | `(?<![a-z])ci\s*-\|-\s*ci\b\|-\s*ci\s\|^ci-` | INVOICE_CI |
| 15 | `(?<![a-z])pi\s*-\|-\s*pi\b\|-\s*pi\s\|^pi-` | INVOICE_CI |

**Por que NUMERARIO/ICMS vêm antes de DI/DUIMP:** um recibo de numerário costuma citar no próprio nome do arquivo a DUIMP/DI a que se refere (ex: `"NUMERÁRIO - DUIMP - CAI26002364.pdf"`), mas a natureza do documento é pagamento, não a declaração de importação em si.

**Lista `FATURAMENTO_FINAL` (ordem importa; mapeia tanto pelo nome quanto pelo número do arquivo):**

| # | Regex | TipoDocumento |
|---|---|---|
| 1 | `frete\s*internacional\|^\s*1\s*-` | FRETE_INTERNACIONAL |
| 2 | `\bicms\b\|^\s*2\s*-` | ICMS |
| 3 | `armazenagem\|^\s*3\s*-` | ARMAZENAGEM |
| 4 | `frete\s*entrega\|^\s*4\s*-` | FRETE_ENTREGA |
| 5 | `honor[aá]rios\|^\s*5\s*-` | HONORARIOS |
| 6 | `numer[aá]rio\|^\s*6\s*-` | NUMERARIO |
| 7 | `presta[cç][aã]o\s*de\s*contas\|^\s*7\s*-` | PRESTACAO_CONTAS |
| 8 | `devolu[cç][aã]o.*saldo\|dev\s*saldo\|^\s*8\s*-` | DEVOLUCAO_SALDO |

Siglas específicas de trading (ex CODELI usa "-ND"/"-NF"/"-REC") **não** são mapeadas de propósito — caem em `OUTRO`, virando pendência visível em vez de um chute.

**Motor de aprendizado (opcional, mas recomendado replicar):** antes de aplicar as regras acima, uma correção manual do usuário para aquele nome de arquivo exato tem prioridade (tabela de "regras aprendidas": `padrao` = nome do arquivo, `valor_corrigido` = tipo escolhido pelo usuário).

---

## 5. Parsing do Razão Contábil

- **Encoding**: tenta `utf-8-sig`, depois `latin1`; se ambos falharem, decodifica como `latin1` com `errors="replace"`.
- **Delimitador**: detectado automaticamente nos primeiros 4096 caracteres entre `;` e `,`; se a detecção falhar, usa `;` como padrão.
- **Cabeçalho**: normaliza (remove acentos, minúsculas) e procura, para cada campo, a primeira string candidata que aparecer na linha de cabeçalho:

| Campo | Candidatos (nesta ordem) |
|---|---|
| conta_contabil | "conta" |
| numero_contabil | "numero contabil" |
| historico | "historico" |
| valor_debito | "valor a debito", "debito" |
| valor_credito | "valor a credito", "credito" |
| empresa | "empresa" |
| unidade | "unidade" |
| documento_ref | "documento" |
| data | "data" |

Campos obrigatórios: `historico`, `valor_debito`, `valor_credito` — faltando qualquer um, o parsing falha com erro explícito citando o cabeçalho lido.

- **Datas**: tenta `%d/%m/%Y`, depois `%Y-%m-%d`, depois `%d-%m-%Y`; se nenhum bater, fica `None`.
- **Linhas em branco** (todas as células vazias após strip) são ignoradas.

- **`parse_valor_brl(texto)`** — conversão de valor no formato brasileiro:
  1. `None`/vazio → `0`.
  2. Se o texto inteiro bate notação científica (`^-?\d+(\.\d+)?[eE][+-]?\d+$`) → parseia direto, ignora todo o resto das regras (cobre um caso real de exportação tipo `"1.024771826E7"`).
  3. Parênteses ao redor → valor negativo (remove os parênteses).
  4. Remove a substring literal `"R$"`.
  5. **Se houver vírgula em algum lugar**: remove todos os pontos (milhar) e troca a vírgula por ponto (decimal). **Se não houver vírgula nenhuma**, o texto é deixado como está (um valor tipo `"123.45"` sem vírgula é tratado como já-decimal, não multiplicado por mil).
  6. Qualquer erro de conversão → `0`.
  7. Aplica o sinal negativo se veio de parênteses.

- **Extração de processo(s) por lançamento**: `PROCESSO_REGEX = (?:BBI|GOC)\d{5}(?:\.\d+)?`, aplicado sobre `historico.upper()` via `findall`, deduplicado preservando a primeira ordem de aparição.

- **"Multi-processo"** = o conjunto de códigos-base (embarque removido, ex `GOC25129.1` → `GOC25129`) citados no lançamento tem **2 ou mais** elementos distintos. Só nesse caso o rateio (seção 7) entra em ação.

- **Normalização do mês de referência**: depois de parsear todas as linhas, calcula a moda estatística (par ano/mês mais frequente) entre todas as datas válidas encontradas, e **sobrescreve** o `mes_referencia` de TODAS as linhas com esse valor — tolera datas isoladas de outro mês sem quebrar o agrupamento mensal (o Razão é enviado um mês de cada vez). Se nenhuma data foi parseada, cada linha usa a data de construção original (ou o primeiro dia do mês corrente como último recurso).

---

## 6. Classificação de lançamentos (categoria contábil)

Aplicado sobre `historico` normalizado (remove acentos via NFKD + strip, minúsculas). Primeiro regex que bater vence; padrão = "Outras despesas". **Atenção: estes regex NÃO usam case-insensitive** — dependem do texto já estar normalizado/minúsculo antes de testar.

| # | Regex (sobre texto normalizado/minúsculo) | Categoria |
|---|---|---|
| 1 | `\bafrmm\b` | AFRMM |
| 2 | `\bnf\s*entrada\b\|nota fiscal de entrada\|entrada de mercadoria` | NF Entrada |
| 3 | `variacao cambial\|var\.?\s*cambial\|ajuste cambial` | Variação Cambial |
| 4 | `\breembolso\b` | Reembolso |
| 5 | `\bnumerario\b\|adiantamento.*numerario` | Numerário |
| 6 | `\barmazenagem\b\|\barmazem\b\|\barmazenamento\b` | Armazenagem |
| 7 | `\bhonorarios?\b` | Honorários |
| 8 | `\bcapatazia\b` | Capatazia |
| 9 | `\bseguro\b` | Seguro |
| 10 | `\biof\b` | IOF |
| 11 | `\bicms\b` | Outras despesas (ICMS não tem categoria própria) |
| 12 | `\bfrete\b` | Frete |
| 13 | `\bmercadoria\b\|compra.*importacao\|importacao.*mercadoria` | Mercadoria |

Categorias possíveis (enum completo): Frete, Armazenagem, Honorários, AFRMM, Seguro, Capatazia, IOF, Mercadoria, Numerário, Reembolso, NF Entrada, Variação Cambial, Outras despesas.

Motor de aprendizado (mesma ideia da seção 4): correção manual do usuário para aquele `historico` exato (não-normalizado) tem prioridade sobre a lista acima.

---

## 7. Motor de rateio (dividir pagamentos compartilhados entre processos)

**Fonte**: aba `"Controle PIs"` da planilha `Controle de Importações.xlsx`. Colunas relevantes (índice 0-based):

| Coluna | Índice | Letra Excel |
|---|---|---|
| Processo | 0 | A |
| Quantidade | 6 | G |
| NF | 47 | AV |

Ao carregar a planilha (pular linha de cabeçalho): ignora linhas mais curtas que a coluna NF, ou sem processo/NF preenchidos, ou onde quantidade não é um número (guarda contra strings tipo "SEM INFO" ou erro de fórmula). Acumula `quantidade_por_(processo, nf)` (soma se houver linhas duplicadas) e o conjunto de NFs vistas por processo.

**Algoritmo de aplicação do rateio** (`AplicarRateioUseCase`), para cada lançamento multi-processo pendente:
1. Pega os códigos-base dos processos citados.
2. Busca a interseção das NFs de cada processo (`nfs_do_processo`). Casos de erro (nunca força um rateio):
   - Interseção vazia → pendência: *"Nenhuma Nota Fiscal em comum encontrada entre os processos citados (...) no Controle de Importações."*
   - Mais de uma NF na interseção → pendência: *"Mais de uma Nota Fiscal em comum encontrada (...) entre os processos citados - ambíguo, requer revisão manual."*
3. Com a NF única encontrada: busca a quantidade de cada processo **para aquela NF especificamente**. Se qualquer processo participante não tiver quantidade válida (`<= 0` ou ausente) para essa NF → `None` → pendência: *"NF {nf} encontrada, mas sem quantidade de itens válida para todos os processos citados."*
4. **Fórmula do percentual**: `percentual = quantidade_do_processo_nessa_NF / soma_das_quantidades_de_TODOS_os_processos_citados_nessa_NF` (soma feita só entre os processos participantes daquele lançamento específico, não a quantidade "total" global da NF).
5. **Fórmula do valor destinado**: `valor_destinado = (valor_debito_original + valor_credito_original) * percentual`, calculado separadamente para débito e crédito.
6. Grava uma "memória de cálculo" (auditoria) por lançamento com: valores originais, NF usada, quantidade total de itens da NF, fonte ("Controle PIs"), a fórmula literal, e a lista de participantes com seus percentuais/valores.
7. Marca o lançamento como `rateio_aplicado = true`.

---

## 8. Composição contábil (por processo/mês)

Para cada processo e mês, soma por categoria contábil:

- **Lançamento de processo único** (não multi-processo): soma direto (débito, crédito) na categoria classificada (ou "Outras despesas" se não classificado).
- **Lançamento multi-processo, rateio ainda não aplicado**: **excluído** da composição (não soma zero, simplesmente não entra ainda) e gera uma pendência explícita: *"Lançamento '{historico}' cita múltiplos processos ({...}) mas o rateio ainda não foi aplicado - valor não incluído na composição."*
- **Lançamento multi-processo, rateio já aplicado**: usa o valor já destinado àquele processo específico (da memória de auditoria da seção 7). Se a memória não existir por algum motivo → pendência: *"...foi marcado como rateado mas não há memória de cálculo para o processo {X} - valor não incluído na composição."*

**Cruzamento com documentos (Fase 9 — extração de valor real, ver seção 10):** para cada documento do processo cuja categoria é mapeável (seção 10), soma o `valor_extraido` na mesma categoria, num bucket separado ("documentado"). O resultado final por categoria tem: `valor_contabilizado` (débito−crédito do Razão), `valor_documentos` (soma do que os documentos reais dizem), e `diferenca = valor_documentos - valor_contabilizado`. **Categorias que só existem no lado documentado** (despesa já documentada mas ainda não lançada no Razão) também aparecem, com `valor_contabilizado = 0` — esse é justamente o campo de "despesas ainda não contabilizadas".

---

## 9. Motor de fechamento (status Fechado / Pendente / Bloqueado)

**Documentos obrigatórios** (verificados pela presença de pelo menos 1 documento de cada tipo, entre TODOS os embarques do processo):
- Pelo menos 1 `DI`
- Pelo menos 1 `INVOICE_CI`
- Pelo menos 1 de `{NOTA_FISCAL, XML_NFE}`

Falta de qualquer um gera uma pendência específica (`"DI/DUIMP não localizada..."`, `"Invoice (CI/PI) não localizada..."`, `"Nota Fiscal não localizada..."`).

**Tolerância de variação cambial**: padrão **2%** (`0.02`, configurável).
- `valor_base` = soma dos valores absolutos contabilizados de todas as categorias (ou `1` se tudo for zero, para não dividir por zero).
- `dentro_da_tolerancia` = `|saldo_final| <= valor_base * tolerancia`.
- Se o saldo é não-zero mas dentro da tolerância → reportado como "variação cambial" (não é erro).
- Se o saldo é não-zero e **fora** da tolerância → pendência: *"Saldo do processo não fechou: R$ {saldo} ({percentual}% do valor contabilizado, acima da tolerância de {tolerancia*100}% de variação cambial)."*

**Árvore de decisão do status:**
```
SE faltou algum documento obrigatório           → BLOQUEADO  (prioridade máxima)
SENÃO SE há rateio pendente OU saldo fora da tolerância → PENDENTE
SENÃO                                            → FECHADO
```

---

## 10. Extração de valor de documentos (pasta FATURAMENTO FINAL)

**Escopo atual**: só os documentos dentro da pasta `FATURAMENTO FINAL` (já classificados na seção 4) — cada um pertence a exatamente 1 processo por construção (está dentro da pasta daquele processo), então o valor extraído é usado **sem nenhum rateio adicional** (o rateio da seção 7 é um conceito do Razão, não deste documento).

**Estratégia**: ler o texto real do PDF (tem camada de texto, sem necessidade de OCR nestes casos) e varrer por vários marcadores conhecidos, usando a **última ocorrência no texto inteiro** — o comprovante de pagamento bancário sempre vem depois do documento institucional original (DAI/NFS-e/fatura) e reafirma o mesmo valor de forma mais simples e confiável.

**Marcadores (nesta ordem de prioridade de checagem — mas quem decide é a posição no texto, não a ordem da lista):**

```
valor\s+total\s+da\s+nfs-?e\D{0,20}?([\d.]{1,12},\d{2})
valor\s+l[ií]quido\s+da\s+nfs-?e\D{0,20}?([\d.]{1,12},\d{2})
total\s*:\s*([\d.]{1,12},\d{2})
valor\s+total\D{0,10}?([\d.]{1,12},\d{2})
valor\s+a\s+pagar\s+([\d.]{1,12},\d{2})
valor\s+pago\D{0,10}?([\d.]{1,12},\d{2})
valor\s+r\$\s*([\d.]{1,12},\d{2})
```

Valores extraídos com `parse_valor_brl` (seção 5). Se nenhum marcador bater, ou o PDF não tem camada de texto (só imagem), retorna "sem valor" — vira pendência de revisão manual, nunca um chute. **Calibrado e validado contra 3 documentos reais** (`GOC25129.1`, pasta FATURAMENTO FINAL):

| Documento | Tipo | Valor real confirmado |
|---|---|---|
| `3 - ARMAZENAGEM.pdf` | DAI Infraero | R$ 713,39 |
| `5 - HONORÁRIOS.pdf` | NFS-e municipal | R$ 750,00 |
| `1 - FRETE INTERNACIONAL.pdf` | Fatura da trading | R$ 12.291,35 |

**Mapeamento TipoDocumento → Categoria contábil** (só os tipos da pasta FATURAMENTO FINAL têm mapeamento; os demais tipos ficam fora deste rollup):

| TipoDocumento | Categoria |
|---|---|
| FRETE_INTERNACIONAL | Frete |
| FRETE_ENTREGA | Frete |
| ARMAZENAGEM | Armazenagem |
| HONORARIOS | Honorários |
| NUMERARIO | Numerário |
| ICMS | Outras despesas (mesmo critério da seção 6) |
| PRESTACAO_CONTAS | *(fora do rollup — é conceito de acerto de saldo do numerário, não despesa)* |
| DEVOLUCAO_SALDO | *(idem)* |

**Fora do escopo desta fatia, deliberadamente**: qualquer documento fora da pasta FATURAMENTO FINAL (DI, Invoice/CI, Packing List etc.) e PDFs só-imagem (precisariam de OCR) não são lidos — não é uma falha silenciosa, simplesmente não entram no mapeamento e o valor documentado daquela categoria fica zero.

---

## 11. Modelo de dados (schema atual em Postgres — referência para desenhar o equivalente no n8n)

- **empresas**: id, codigo (único, ex "GOC"/"BBI"), nome.
- **processos**: id, empresa_id (FK), codigo (ex "GOC25129"), descricao, fornecedor, ano, drive_folder_id. Único por (empresa_id, codigo).
- **embarques**: id, processo_id (FK, cascade delete), codigo (ex "GOC25129.1"), trading, referencia_trading (ex "WMFIA261430"), drive_folder_id. Único por (processo_id, codigo).
- **documentos**: id, embarque_id (FK, cascade delete), tipo, drive_file_id, nome_arquivo, mime_type, texto_extraido, valor_extraido (numeric 18,2), status_leitura (PENDENTE/OK/SEM_TEXTO/OCR_APLICADO/ERRO).
- **razao_lancamentos**: id, mes_referencia, data, empresa, conta_contabil, numero_contabil, unidade, historico, processos_codigos (lista/JSON), documento_ref, valor_debito, valor_credito, categoria_classificada, rateio_aplicado (bool). **Sem FK para processos** — a ligação é dinâmica via `processos_codigos` + a regra de "código-base" (seção 5/7).
- **rateio_matriz**: id, processo_id (FK), nf_referencia, qtd_itens_processo, qtd_itens_total_nf, percentual (numeric 9,6), fonte (ex "Controle PIs").
- **composicao_contabil**: id, processo_id (FK), mes_referencia, categoria, valor_documentos, valor_contabilizado, valor_rateado, percentual_rateio, diferenca.
- **regras_aprendidas**: id, tipo (classificacao/rateio/natureza/composicao/documento), padrao, valor_corrigido, justificativa, criado_por, criado_em — motor de aprendizado das seções 4 e 6.
- **auditoria_calculo**: id, referencia_tipo (rateio/composicao/fechamento), referencia_id, memoria (JSON) — a "memória de cálculo" auditável de cada rateio aplicado (seção 7).
- **fechamentos**: id, processo_id (FK), mes_referencia, status (Fechado/Pendente/Bloqueado), saldo_final, variacao_cambial, motivos_pendencia (lista/JSON). Único por (processo_id, mes_referencia).

**Configuração relevante**: `tolerancia_variacao_cambial` = 2% (0.02) por padrão — deve ser um valor ajustável, não fixo no código/workflow.

---

## 12. Formato dos dois Excel de saída

Ambos usam exatamente este cabeçalho de colunas (nesta ordem):

```
Empresa | Data | Conta | Numero Contabil | Unidade | Historico | Debito | Credito | Movimentação | Processo | Processo Full | Processo (Controle de Importação) | Status
```

Onde `Movimentação = Debito - Credito`, `Processo` = código-base (sem sufixo de embarque), `Processo Full` = código completo do lançamento original, e `Processo (Controle de Importação)` = o código com `.` trocado por `-` (formato usado na planilha de controle).

- **"Razão Atualizado"**: uma aba única, com **todas** as linhas do mês (de todos os processos), já "explodidas" por processo participante quando o lançamento é rateado (ver seção 7 — uma linha por processo, com débito/crédito já divididos), cada linha com o status de fechamento calculado.
- **"Processos Fechados"**: uma aba por processo com status **Fechado** naquele mês, contendo:
  1. As mesmas linhas (formato acima) só daquele processo.
  2. Uma linha de totais (soma de Débito e soma de Crédito).
  3. Uma linha em branco.
  4. Uma linha final: `"Saldo processo"` na coluna Historico, com o valor `soma_debito - soma_credito` na coluna Movimentação.
  - Nomes de aba são truncados em 31 caracteres (limite do Excel) com sufixo numérico em caso de colisão (`_2`, `_3`...).
  - Se nenhum processo fechou no mês, gera uma única aba "Nenhum processo fechado".

---

## 13. Nota final

O sistema de referência (Python/FastAPI/PostgreSQL/React, Clean Architecture, Docker Compose) está **implementado e testado por completo** — 173 testes automatizados, todas as 9 fases descritas acima com cobertura de teste — em:

```
C:\Users\Notebook\projetos\gocase-fechamento-importacoes\
```

Ele continua disponível para rodar localmente (`docker compose up --build`, ver `README.md` daquele projeto) como referência de comparação/fallback enquanto os workflows equivalentes forem montados no n8n. Nenhuma regra deste documento foi inventada para esta especificação — todas foram copiadas literalmente do código-fonte já validado.
