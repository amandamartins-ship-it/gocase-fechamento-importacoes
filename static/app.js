const el = (id) => document.getElementById(id);

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Erro ${res.status}`);
  return data;
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const resultado = reader.result;
      const virgula = resultado.indexOf(",");
      resolve(resultado.slice(virgula + 1));
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function formatarReais(valor) {
  return valor.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatarData(data) {
  if (!data) return "—";
  const dd = String(data.dia).padStart(2, "0");
  const mm = String(data.mes).padStart(2, "0");
  return `${dd}/${mm}/${data.ano}`;
}

async function carregarStatusMaster() {
  const box = el("masterStatus");
  try {
    const status = await api("/api/master-status");
    if (!status.cached) {
      box.textContent = "Ainda não enviado - selecione o arquivo abaixo e clique em \"Enviar planilha\".";
      return;
    }
    const data = new Date(status.updatedAt);
    box.textContent = `${status.arquivoNome} — enviado em ${data.toLocaleString("pt-BR")} — ${status.totalProcessos} processos mapeados.`;
  } catch (err) {
    box.textContent = "Erro ao carregar status: " + err.message;
  }
}

el("inputControle").addEventListener("change", () => {
  el("btnEnviarControle").disabled = !el("inputControle").files.length;
  el("controleErro").textContent = "";
});

el("btnEnviarControle").addEventListener("click", async () => {
  const arquivo = el("inputControle").files[0];
  if (!arquivo) return;
  const btn = el("btnEnviarControle");
  const erroBox = el("controleErro");
  const box = el("masterStatus");
  btn.disabled = true;
  erroBox.textContent = "";
  btn.textContent = "Enviando...";
  box.textContent = "Lendo a aba \"Controle PIs\"...";
  try {
    const contentBase64 = await fileToBase64(arquivo);
    await api("/api/master-upload", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ filename: arquivo.name, contentBase64 }),
    });
    await carregarStatusMaster();
  } catch (err) {
    erroBox.textContent = err.message;
    await carregarStatusMaster();
  } finally {
    btn.disabled = !el("inputControle").files.length;
    btn.textContent = "Enviar planilha";
  }
});

let xlsxBase64Atual = null;
let nomeArquivoAtual = "Razao_Rateado.xlsx";

el("inputRazao").addEventListener("change", () => {
  el("btnProcessar").disabled = !el("inputRazao").files.length;
  el("uploadErro").textContent = "";
});

el("btnProcessar").addEventListener("click", async () => {
  const arquivo = el("inputRazao").files[0];
  if (!arquivo) return;
  const btn = el("btnProcessar");
  const erroBox = el("uploadErro");
  btn.disabled = true;
  erroBox.textContent = "";
  btn.textContent = "Processando...";
  try {
    const contentBase64 = await fileToBase64(arquivo);
    const resultado = await api("/api/process", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ filename: arquivo.name, contentBase64 }),
    });
    renderResultado(resultado);
  } catch (err) {
    erroBox.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Processar rateio";
  }
});

function renderResultado(resultado) {
  xlsxBase64Atual = resultado.xlsxBase64;
  nomeArquivoAtual = resultado.nomeArquivoSugerido || "Razao_Rateado.xlsx";

  el("cardResumo").hidden = false;
  el("cardPreview").hidden = false;

  el("statLancamentos").textContent = resultado.resumo.totalLancamentos;
  el("statRateados").textContent = resultado.resumo.totalRateados;
  el("statPendencias").textContent = resultado.resumo.totalPendencias;

  const t = resultado.totais;
  const saldoEl = el("statSaldo");
  const saldoValorEl = el("statSaldoValor");
  saldoEl.classList.remove("ok", "fail");
  if (t.saldoBate) {
    saldoEl.classList.add("ok");
    saldoValorEl.textContent = `✓ ${formatarReais(t.debitoDepoisReais)} / ${formatarReais(t.creditoDepoisReais)}`;
  } else {
    saldoEl.classList.add("fail");
    saldoValorEl.textContent = `✗ antes ${formatarReais(t.debitoAntesReais)} ≠ depois ${formatarReais(t.debitoDepoisReais)}`;
  }

  const pendenciasBox = el("pendenciasBox");
  const pendenciasList = el("pendenciasList");
  pendenciasList.innerHTML = "";
  if (resultado.pendencias.length > 0) {
    pendenciasBox.hidden = false;
    for (const p of resultado.pendencias) {
      const li = document.createElement("li");
      li.textContent = `${p.historico} — ${p.motivo}`;
      pendenciasList.appendChild(li);
    }
  } else {
    pendenciasBox.hidden = true;
  }

  const body = el("previewBody");
  body.innerHTML = "";
  for (const linha of resultado.preview) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${formatarData(linha.data)}</td>
      <td>${linha.historico}</td>
      <td class="num">${formatarReais(linha.debito)}</td>
      <td class="num">${formatarReais(linha.credito)}</td>
      <td class="num">${formatarReais(linha.debito - linha.credito)}</td>
      <td>${linha.processo ?? "—"}</td>
      <td><span class="pill ${linha.pendencia ? "pendente" : "ok"}">${linha.pendencia ? "Pendente" : linha.rateado ? "Rateado" : "OK"}</span></td>
    `;
    body.appendChild(tr);
  }
}

el("btnBaixar").addEventListener("click", () => {
  if (!xlsxBase64Atual) return;
  const binario = atob(xlsxBase64Atual);
  const bytes = new Uint8Array(binario.length);
  for (let i = 0; i < binario.length; i++) bytes[i] = binario.charCodeAt(i);
  const blob = new Blob([bytes], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nomeArquivoAtual;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

carregarStatusMaster();
