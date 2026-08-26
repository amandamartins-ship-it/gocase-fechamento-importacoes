/** Conciliador de Importações - módulo isolado do Rateador (app.js não é
 * tocado, nenhum nome/id em comum). Faz o roteamento por hash entre as duas
 * telas e toda a lógica do novo módulo. */

const cncEl = (id) => document.getElementById(id);

// ---------- roteamento simples por hash (#/rateador, #/conciliador) ----------
function cncRouter() {
  const hash = location.hash || "#/rateador";
  const view = hash.startsWith("#/conciliador") ? "conciliador" : "rateador";
  cncEl("view-rateador").hidden = view !== "rateador";
  cncEl("view-conciliador").hidden = view !== "conciliador";
  document.querySelectorAll(".sidebar-link").forEach((a) => {
    a.classList.toggle("active", a.dataset.view === view);
  });
}
window.addEventListener("hashchange", cncRouter);
cncRouter();

// ---------- helpers ----------
function cncFileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).slice(String(reader.result).indexOf(",") + 1));
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function cncApi(path, opts = {}) {
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Erro ${res.status}`);
  return data;
}

function cncFormatarReais(valor) {
  return (valor || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function cncFormatarData(data) {
  if (!data) return "—";
  return `${String(data.dia).padStart(2, "0")}/${String(data.mes).padStart(2, "0")}/${data.ano}`;
}

function cncPillClasse(status) {
  if (status === "Fechado") return "fechado";
  if (status === "Bloqueado") return "bloqueado";
  return "pendente";
}

// ---------- constantes de negócio (mesma regra do backend, composicaoEngine.js -
// duplicado deliberadamente aqui só para o recálculo instantâneo no navegador;
// o valor persistido/oficial sempre vem do servidor) ----------
const CNC_DESPESA_PARA_CATEGORIA = {
  "Frete Internacional": "Frete",
  "Frete Nacional": "Frete",
  Armazenagem: "Armazenagem",
  Honorários: "Honorários",
  Seguro: "Seguro",
  Capatazia: "Capatazia",
  IOF: "IOF",
  Taxas: "Outras Despesas",
  "Outras despesas": "Outras Despesas",
};
const CNC_CATEGORIAS_DE_DESPESA = Array.from(new Set(Object.values(CNC_DESPESA_PARA_CATEGORIA)));
const CNC_TOLERANCIA_VARIACAO_CAMBIAL = 0.02;

// Campos declarados na DI (referência, nunca somam como despesa direta) que
// entram no encontro de contas Numerário × NF Entrada - "Frete" fica de fora
// dessa lista, ele tem seu próprio confronto (Frete DI × Frete Recibo).
const CNC_TRIBUTOS_DI_REFERENCIA_ENCONTRO = ["PIS", "COFINS", "IPI", "ICMS", "Siscomex", "AFRMM"];

function cncRecalcularComposicao(categoriasServidor, despesasAtuaisReais, tributosDiAtuaisReais) {
  const tributosDi = tributosDiAtuaisReais || new Map();

  // agrupa despesas (por campo granular) na categoria contabilizada,
  // subtraindo da categoria Frete o valor de frete já declarado na DI.
  const informadoPorCategoria = new Map();
  for (const [campo, categoria] of Object.entries(CNC_DESPESA_PARA_CATEGORIA)) {
    const valor = despesasAtuaisReais.get(campo) || 0;
    if (valor === 0) continue;
    informadoPorCategoria.set(categoria, (informadoPorCategoria.get(categoria) || 0) + valor);
  }
  const freteDi = tributosDi.get("Frete") || 0;
  if (freteDi !== 0) {
    informadoPorCategoria.set("Frete", (informadoPorCategoria.get("Frete") || 0) - freteDi);
  }

  const porCategoria = new Map(categoriasServidor.map((c) => [c.categoria, c]));
  const nomes = new Set([...porCategoria.keys(), ...informadoPorCategoria.keys()]);

  let totalDebito = 0;
  let totalCredito = 0;
  let totalInformado = 0;
  const categorias = [];
  for (const nome of nomes) {
    const original = porCategoria.get(nome);
    const debito = original ? original.debitoContabilizado : 0;
    const credito = original ? original.creditoContabilizado : 0;
    const informado = informadoPorCategoria.get(nome) || 0;
    totalDebito += debito;
    totalCredito += credito;
    totalInformado += informado;
    categorias.push({
      categoria: nome,
      debitoContabilizado: debito,
      creditoContabilizado: credito,
      informado,
      total: debito + informado - credito,
      linhas: original ? original.linhas : [],
    });
  }
  categorias.sort((a, b) => a.categoria.localeCompare(b.categoria, "pt-BR"));

  const saldoFinal = Math.round((totalDebito + totalInformado - totalCredito) * 100) / 100;

  // Encontro de contas dos tributos da DI: Numerário pago (débito) deveria
  // ser compensado pela NF de Entrada (crédito) - o resíduo é reembolsado ou
  // cobrado pelo despachante, nunca uma despesa nova.
  const numerarioItem = porCategoria.get("Numerário");
  const nfEntradaItem = porCategoria.get("NF Entrada");
  const numerarioDebito = numerarioItem ? numerarioItem.debitoContabilizado : 0;
  const nfEntradaCredito = nfEntradaItem ? nfEntradaItem.creditoContabilizado : 0;
  const residuo = Math.round((numerarioDebito - nfEntradaCredito) * 100) / 100;
  const totalDeclaradoDI = CNC_TRIBUTOS_DI_REFERENCIA_ENCONTRO.reduce((acc, campo) => acc + (tributosDi.get(campo) || 0), 0);
  const encontroContasDI = {
    numerarioDebito,
    nfEntradaCredito,
    residuo,
    totalDeclaradoDI,
    tipo: residuo > 0 ? "reembolso" : residuo < 0 ? "cobranca" : "ok",
  };

  return { categorias, totalDebito, totalCredito, totalInformado, saldoFinal, encontroContasDI };
}

function cncGerarDicas(categorias, saldoFinal, totalDebito) {
  const dicas = [];
  if (saldoFinal === 0) return dicas;
  const porCategoria = new Map(categorias.map((c) => [c.categoria, c]));
  for (const categoriaDespesa of CNC_CATEGORIAS_DE_DESPESA) {
    const item = porCategoria.get(categoriaDespesa);
    const semNada = !item || item.debitoContabilizado + item.informado === 0;
    if (semNada) dicas.push(`${categoriaDespesa} não informado/pendente.`);
  }
  const base = totalDebito || 1;
  if (Math.abs(saldoFinal) / base <= CNC_TOLERANCIA_VARIACAO_CAMBIAL) {
    dicas.push("Possível variação cambial.");
  }
  return dicas;
}

// ---------- estado em memória (a sessão de conciliação atual) ----------
let cncDadosProcessados = null; // resultado completo de /api/conciliador/process
let cncProcessoAtual = null; // {processo, composicao, despesasAtuais: Map<campo, reais>}

// ---------- 1. upload + processar ----------
cncEl("cncInputRazao").addEventListener("change", () => {
  cncEl("cncBtnProcessar").disabled = !cncEl("cncInputRazao").files.length;
  cncEl("cncUploadErro").textContent = "";
});

cncEl("cncBtnProcessar").addEventListener("click", async () => {
  const arquivo = cncEl("cncInputRazao").files[0];
  if (!arquivo) return;
  const btn = cncEl("cncBtnProcessar");
  const erroBox = cncEl("cncUploadErro");
  btn.disabled = true;
  erroBox.textContent = "";
  btn.textContent = "Processando...";
  try {
    const contentBase64 = await cncFileToBase64(arquivo);
    const resultado = await cncApi("/api/conciliador/process", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ filename: arquivo.name, contentBase64 }),
    });
    cncDadosProcessados = resultado;
    cncRenderListaProcessos();
    cncEl("cncCardProcessos").hidden = false;
    cncEl("cncCardDetalhe").hidden = true;
  } catch (err) {
    erroBox.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Processar Conciliação";
  }
});

// ---------- 2. lista de processos ----------
function cncRenderListaProcessos() {
  const body = cncEl("cncProcessosBody");
  body.innerHTML = "";
  for (const { processo, composicao } of cncDadosProcessados.processos) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="mono">${processo}</td>
      <td><span class="pill ${cncPillClasse(composicao.status)}">${composicao.status}</span></td>
      <td class="num">${cncFormatarReais(composicao.totais.debitoContabilizado)}</td>
      <td class="num">${cncFormatarReais(composicao.totais.creditoContabilizado)}</td>
      <td class="num">${cncFormatarReais(composicao.totais.informado)}</td>
      <td class="num">${cncFormatarReais(composicao.totais.saldoFinal)}</td>
      <td><button class="btn ghost cnc-ver-detalhe">Ver detalhes</button></td>
    `;
    tr.querySelector(".cnc-ver-detalhe").addEventListener("click", () => cncAbrirDetalhe(processo));
    body.appendChild(tr);
  }
}

// ---------- 3. detalhe do processo ----------
async function cncAbrirDetalhe(processo) {
  const entrada = cncDadosProcessados.processos.find((p) => p.processo === processo);
  if (!entrada) return;

  let despesasSalvas = {};
  try {
    const resp = await cncApi(
      `/api/conciliador/despesas?processo=${encodeURIComponent(processo)}&mes=${encodeURIComponent(cncDadosProcessados.mesReferenciaChave)}`
    );
    despesasSalvas = resp.despesas || {};
  } catch {
    // sem despesas salvas ainda - segue com tudo zerado, nunca bloqueia a tela.
  }

  let tributosDiSalvos = {};
  try {
    const resp = await cncApi(
      `/api/conciliador/tributos-di?processo=${encodeURIComponent(processo)}&mes=${encodeURIComponent(cncDadosProcessados.mesReferenciaChave)}`
    );
    tributosDiSalvos = resp.tributosDi || {};
  } catch {
    // sem tributos DI salvos ainda - segue com tudo zerado, nunca bloqueia a tela.
  }

  const despesasAtuais = new Map(Object.entries(despesasSalvas));
  const tributosDiAtuais = new Map(Object.entries(tributosDiSalvos));
  cncProcessoAtual = {
    processo,
    composicaoBase: entrada.composicao,
    despesasAtuais,
    tributosDiAtuais,
    sujo: false,
    fechadoManualmente: entrada.composicao.status === "Fechado",
  };
  cncEl("cncDespesasSalvarMsg").textContent = "";
  cncEl("cncTributosDiSalvarMsg").textContent = "";
  cncEl("cncFechamentoMsg").textContent = "";

  cncEl("cncDetalheTitulo").textContent = `Composição do processo ${processo}`;
  cncRenderDespesasGrid();
  cncRenderTributosDiGrid();
  cncRecalcularERenderizar();

  cncEl("cncCardProcessos").hidden = true;
  cncEl("cncCardDetalhe").hidden = false;
}

cncEl("cncBtnVoltar").addEventListener("click", () => {
  if (cncProcessoAtual && cncProcessoAtual.sujo) {
    const confirmar = confirm("Há despesas digitadas e ainda não salvas neste processo. Voltar sem salvar?");
    if (!confirmar) return;
  }
  cncEl("cncCardDetalhe").hidden = true;
  cncEl("cncCardProcessos").hidden = false;
});

function cncRenderDespesasGrid() {
  const grid = cncEl("cncDespesasGrid");
  grid.innerHTML = "";
  for (const campo of cncDadosProcessados.camposDespesa) {
    const valorAtual = cncProcessoAtual.despesasAtuais.get(campo) || 0;
    const wrap = document.createElement("div");
    wrap.className = "despesa-field";
    const inputId = `cncDespesa_${campo.replace(/\s+/g, "_")}`;
    wrap.innerHTML = `<label for="${inputId}">${campo}</label><input type="number" step="0.01" min="0" id="${inputId}" value="${valorAtual || ""}" placeholder="R$ 0,00" />`;
    const input = wrap.querySelector("input");
    input.addEventListener("input", () => {
      const valor = Number(input.value) || 0;
      cncProcessoAtual.despesasAtuais.set(campo, valor);
      cncProcessoAtual.sujo = true;
      cncEl("cncDespesasSalvarMsg").textContent = "";
      cncRecalcularERenderizar();
    });
    grid.appendChild(wrap);
  }
}

function cncRenderTributosDiGrid() {
  const grid = cncEl("cncTributosDiGrid");
  grid.innerHTML = "";
  for (const campo of cncDadosProcessados.camposTributosDi) {
    const valorAtual = cncProcessoAtual.tributosDiAtuais.get(campo) || 0;
    const wrap = document.createElement("div");
    wrap.className = "despesa-field";
    const inputId = `cncTributoDi_${campo.replace(/\s+/g, "_")}`;
    wrap.innerHTML = `<label for="${inputId}">${campo}</label><input type="number" step="0.01" min="0" id="${inputId}" value="${valorAtual || ""}" placeholder="R$ 0,00" />`;
    const input = wrap.querySelector("input");
    input.addEventListener("input", () => {
      const valor = Number(input.value) || 0;
      cncProcessoAtual.tributosDiAtuais.set(campo, valor);
      cncProcessoAtual.sujo = true;
      cncEl("cncTributosDiSalvarMsg").textContent = "";
      cncRecalcularERenderizar();
    });
    grid.appendChild(wrap);
  }
}

async function cncSalvarTributosDi() {
  for (const campo of cncDadosProcessados.camposTributosDi) {
    const valor = cncProcessoAtual.tributosDiAtuais.get(campo) || 0;
    await cncApi("/api/conciliador/tributos-di", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        processo: cncProcessoAtual.processo,
        mesReferencia: cncDadosProcessados.mesReferenciaChave,
        campo,
        valorReais: valor,
      }),
    });
  }
}

cncEl("cncBtnSalvarTributosDi").addEventListener("click", async () => {
  const btn = cncEl("cncBtnSalvarTributosDi");
  const msg = cncEl("cncTributosDiSalvarMsg");
  btn.disabled = true;
  btn.textContent = "Salvando...";
  msg.className = "muted";
  msg.textContent = "";
  try {
    await cncSalvarTributosDi();
    msg.className = "";
    msg.style.color = "var(--good)";
    msg.textContent = "Tributos DI salvos ✓";
  } catch (err) {
    msg.className = "error";
    msg.textContent = "Falha ao salvar: " + err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Salvar Tributos DI";
  }
});

cncEl("cncBtnSalvarDespesas").addEventListener("click", async () => {
  const btn = cncEl("cncBtnSalvarDespesas");
  const msg = cncEl("cncDespesasSalvarMsg");
  btn.disabled = true;
  btn.textContent = "Salvando...";
  msg.className = "muted";
  msg.textContent = "";
  try {
    for (const campo of cncDadosProcessados.camposDespesa) {
      const valor = cncProcessoAtual.despesasAtuais.get(campo) || 0;
      await cncApi("/api/conciliador/despesas", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          processo: cncProcessoAtual.processo,
          mesReferencia: cncDadosProcessados.mesReferenciaChave,
          campo,
          valorReais: valor,
        }),
      });
    }
    cncProcessoAtual.sujo = false;
    msg.className = "";
    msg.style.color = "var(--good)";
    msg.textContent = "Despesas salvas ✓";
  } catch (err) {
    msg.className = "error";
    msg.textContent = "Falha ao salvar: " + err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Salvar Despesas";
  }
});

function cncRecalcularERenderizar() {
  const { composicaoBase, despesasAtuais, tributosDiAtuais, fechadoManualmente } = cncProcessoAtual;
  const recalculo = cncRecalcularComposicao(composicaoBase.categorias, despesasAtuais, tributosDiAtuais);
  // "Fechado" é uma decisão manual (botão "Marcar como Fechado") - o saldo
  // pode fechar com uma diferença real, que vai pra variação cambial no
  // lançamento final; não exige mais saldo = R$0,00 exato.
  const temBloqueio = composicaoBase.status === "Bloqueado";
  const status = temBloqueio ? "Bloqueado" : fechadoManualmente ? "Fechado" : "Pendente";
  const dicas = status === "Pendente" ? cncGerarDicas(recalculo.categorias, recalculo.saldoFinal, recalculo.totalDebito) : [];

  cncRenderComposicaoTabela(recalculo.categorias);
  cncRenderPainel(recalculo, status, dicas);
  cncRenderEncontroContasDI(recalculo.encontroContasDI);

  // atualiza também a linha correspondente na lista (status/saldo/categorias/
  // despesas), sem reprocessar - é isso que alimenta o Relatório de
  // Lançamentos depois, com o estado mais recente de cada processo visitado.
  const entrada = cncDadosProcessados.processos.find((p) => p.processo === cncProcessoAtual.processo);
  if (entrada) {
    entrada.composicao.totais.informado = recalculo.totalInformado;
    entrada.composicao.totais.saldoFinal = recalculo.saldoFinal;
    entrada.composicao.status = status;
    entrada.composicao.categorias = recalculo.categorias;
    entrada.despesasAtuais = new Map(despesasAtuais);
  }
}

function cncRenderComposicaoTabela(categorias) {
  const body = cncEl("cncComposicaoBody");
  body.innerHTML = "";
  for (const c of categorias) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${c.categoria}</td>
      <td class="num">${c.linhas.length ? `<button class="link-valor cnc-ver-auditoria">${cncFormatarReais(c.debitoContabilizado)}</button>` : cncFormatarReais(c.debitoContabilizado)}</td>
      <td class="num">${cncFormatarReais(c.creditoContabilizado)}</td>
      <td class="num">${cncFormatarReais(c.informado)}</td>
      <td class="num">${cncFormatarReais(c.total)}</td>
    `;
    const botaoAuditoria = tr.querySelector(".cnc-ver-auditoria");
    if (botaoAuditoria) botaoAuditoria.addEventListener("click", () => cncAbrirAuditoria(c));
    body.appendChild(tr);
  }
}

function cncRenderPainel(recalculo, status, dicas) {
  cncEl("cncPainelDebito").textContent = cncFormatarReais(recalculo.totalDebito);
  cncEl("cncPainelCredito").textContent = cncFormatarReais(recalculo.totalCredito);
  cncEl("cncPainelInformado").textContent = cncFormatarReais(recalculo.totalInformado);
  cncEl("cncPainelSaldo").textContent = cncFormatarReais(recalculo.saldoFinal);
  cncEl("cncPainelStatus").textContent = status;

  const saldoBox = cncEl("cncPainelSaldoBox");
  saldoBox.classList.remove("ok", "fail", "warn");
  saldoBox.classList.add(status === "Fechado" ? "ok" : status === "Bloqueado" ? "fail" : "warn");

  const dicasBox = cncEl("cncDicasBox");
  const dicasList = cncEl("cncDicasList");
  dicasList.innerHTML = "";
  if (dicas.length > 0) {
    dicasBox.hidden = false;
    for (const dica of dicas) {
      const li = document.createElement("li");
      li.textContent = dica;
      dicasList.appendChild(li);
    }
  } else {
    dicasBox.hidden = true;
  }

  const podeFechar = status !== "Bloqueado";
  cncEl("cncBtnMarcarFechado").hidden = status !== "Pendente" || !podeFechar;
  cncEl("cncBtnReabrir").hidden = status !== "Fechado";
}

const CNC_ENCONTRO_DI_ROTULO = {
  reembolso: "Reembolso a receber do despachante",
  cobranca: "Cobrança do despachante",
  ok: "Sem resíduo",
};

function cncRenderEncontroContasDI(encontroContasDI) {
  cncEl("cncEncontroDITotalDeclarado").textContent = cncFormatarReais(encontroContasDI.totalDeclaradoDI);
  cncEl("cncEncontroDINumerario").textContent = cncFormatarReais(encontroContasDI.numerarioDebito);
  cncEl("cncEncontroDINfEntrada").textContent = cncFormatarReais(encontroContasDI.nfEntradaCredito);
  cncEl("cncEncontroDIResiduo").textContent = cncFormatarReais(Math.abs(encontroContasDI.residuo));

  const rotuloEl = cncEl("cncEncontroDIRotulo");
  rotuloEl.textContent = CNC_ENCONTRO_DI_ROTULO[encontroContasDI.tipo];
  rotuloEl.className = `pill ${encontroContasDI.tipo === "reembolso" ? "reembolso" : encontroContasDI.tipo === "cobranca" ? "cobranca" : "ok"}`;
}

cncEl("cncBtnMarcarFechado").addEventListener("click", async () => {
  const btn = cncEl("cncBtnMarcarFechado");
  const msg = cncEl("cncFechamentoMsg");
  btn.disabled = true;
  msg.className = "muted";
  msg.textContent = "Salvando despesas antes de fechar...";
  try {
    // garante que o que está na tela é exatamente o que fica persistido -
    // o lançamento final de fechamento só pode ler despesas/tributos DI já salvos.
    for (const campo of cncDadosProcessados.camposDespesa) {
      const valor = cncProcessoAtual.despesasAtuais.get(campo) || 0;
      await cncApi("/api/conciliador/despesas", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          processo: cncProcessoAtual.processo,
          mesReferencia: cncDadosProcessados.mesReferenciaChave,
          campo,
          valorReais: valor,
        }),
      });
    }
    await cncSalvarTributosDi();
    cncProcessoAtual.sujo = false;

    await cncApi("/api/conciliador/fechar", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ processo: cncProcessoAtual.processo, mesReferencia: cncDadosProcessados.mesReferenciaChave }),
    });
    cncProcessoAtual.fechadoManualmente = true;
    msg.className = "";
    msg.style.color = "var(--good)";
    msg.textContent = "Processo marcado como Fechado ✓";
    cncRecalcularERenderizar();
  } catch (err) {
    msg.className = "error";
    msg.textContent = "Falha ao fechar: " + err.message;
  } finally {
    btn.disabled = false;
  }
});

cncEl("cncBtnReabrir").addEventListener("click", async () => {
  const btn = cncEl("cncBtnReabrir");
  const msg = cncEl("cncFechamentoMsg");
  btn.disabled = true;
  try {
    await cncApi("/api/conciliador/reabrir", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ processo: cncProcessoAtual.processo, mesReferencia: cncDadosProcessados.mesReferenciaChave }),
    });
    cncProcessoAtual.fechadoManualmente = false;
    msg.className = "muted";
    msg.textContent = "Processo reaberto.";
    cncRecalcularERenderizar();
  } catch (err) {
    msg.className = "error";
    msg.textContent = "Falha ao reabrir: " + err.message;
  } finally {
    btn.disabled = false;
  }
});

// ---------- auditoria (rastreabilidade até o lançamento de origem) ----------
function cncAbrirAuditoria(categoriaItem) {
  cncEl("cncAuditoriaTitulo").textContent = `Lançamentos de origem — ${categoriaItem.categoria}`;
  const body = cncEl("cncAuditoriaBody");
  body.innerHTML = "";
  for (const l of categoriaItem.linhas) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${cncFormatarData(l.data)}</td>
      <td class="mono">${l.contaContabil ?? "—"}</td>
      <td>${l.historico}</td>
      <td class="num">${cncFormatarReais(l.debito)}</td>
      <td class="num">${cncFormatarReais(l.credito)}</td>
      <td class="mono">${l.processoFull ?? l.processo ?? "—"}</td>
    `;
    body.appendChild(tr);
  }
  cncEl("cncAuditoriaModal").hidden = false;
}

cncEl("cncAuditoriaFechar").addEventListener("click", () => {
  cncEl("cncAuditoriaModal").hidden = true;
});
cncEl("cncAuditoriaModal").addEventListener("click", (evento) => {
  if (evento.target.id === "cncAuditoriaModal") cncEl("cncAuditoriaModal").hidden = true;
});

// ---------- lançamento final de fechamento (processos marcados Fechado) ----------
let cncRelatorioCsv = null;

cncEl("cncBtnRelatorio").addEventListener("click", async () => {
  const erroBox = cncEl("cncRelatorioErro");
  erroBox.textContent = "";
  const processosFechados = cncDadosProcessados.processos
    .filter((p) => p.composicao.status === "Fechado")
    .map((p) => ({
      processo: p.processo,
      debitoContabilizado: p.composicao.totais.debitoContabilizado,
      creditoContabilizado: p.composicao.totais.creditoContabilizado,
    }));

  if (processosFechados.length === 0) {
    erroBox.textContent = "Nenhum processo está Fechado ainda - marque pelo menos um processo como Fechado antes de finalizar.";
    return;
  }

  try {
    const resultado = await cncApi("/api/conciliador/relatorio", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ mesReferencia: cncDadosProcessados.mesReferenciaChave, processos: processosFechados }),
    });
    cncRelatorioCsv = resultado.csv;
    cncRenderRelatorio(resultado.linhas, processosFechados.length);
  } catch (err) {
    erroBox.textContent = err.message;
  }
});

function cncRenderRelatorio(linhas, totalProcessosFechados) {
  cncEl("cncRelatorioResumo").textContent =
    `${totalProcessosFechados} processo(s) fechado(s) — ${linhas.length} linha(s) de lançamento contábil geradas. Confira antes de importar.`;

  const body = cncEl("cncRelatorioBody");
  body.innerHTML = "";
  for (const l of linhas) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${l.data}</td>
      <td class="mono">${l.conta}</td>
      <td class="mono">${l.unidade}</td>
      <td class="mono">${l.centroResultado}</td>
      <td class="num">${cncFormatarReais(l.valorReais)}</td>
      <td>${l.indicador}</td>
      <td>${l.historico}</td>
      <td class="mono">${l.agrupador}</td>
    `;
    body.appendChild(tr);
  }
  cncEl("cncCardRelatorio").hidden = false;
  cncEl("cncCardRelatorio").scrollIntoView({ behavior: "smooth", block: "start" });
}

cncEl("cncBtnBaixarRelatorio").addEventListener("click", () => {
  if (!cncRelatorioCsv) return;
  const blob = new Blob([cncRelatorioCsv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `Fechamento_Contabil_${cncDadosProcessados.mesReferenciaChave}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

// ---------- Carregar Histórico de Importações ----------

cncEl("cncInputHistorico").addEventListener("change", function (e) {
  const file = e.target.files[0];
  if (file) {
    cncEl("cncBtnCarregarHistorico").disabled = false;
    cncEl("cncHistoricoMsg").textContent = `Arquivo selecionado: ${file.name}`;
  }
});

cncEl("cncBtnCarregarHistorico").addEventListener("click", async () => {
  const file = cncEl("cncInputHistorico").files[0];
  if (!file) return;

  const msgEl = cncEl("cncHistoricoMsg");
  const erroEl = cncEl("cncHistoricoErro");
  const btnEl = cncEl("cncBtnCarregarHistorico");

  msgEl.textContent = "Processando... aguarde...";
  erroEl.textContent = "";
  btnEl.disabled = true;

  try {
    const base64 = await cncFileToBase64(file);
    const response = await cncApi("/api/importacoes/seed", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: file.name,
        contentBase64: base64,
      }),
    });

    if (response.status === "sucesso" || response.status === "parcial") {
      msgEl.textContent = `✓ Base carregada com sucesso! ${response.insertados} linhas processadas`;
      cncEl("cncInputHistorico").value = "";

      // Verificar status da base
      try {
        const status = await cncApi("/api/importacoes/status");
        msgEl.textContent += ` (Total na base: ${status.total_linhas} linhas, período: ${status.primeira_data} a ${status.ultima_data})`;
      } catch (err) {
        // Silencioso se não conseguir status
      }
    } else {
      erroEl.textContent = response.error || "Erro ao processar arquivo";
    }
  } catch (err) {
    erroEl.textContent = `Erro: ${err.message}`;
  } finally {
    btnEl.disabled = false;
  }
});
