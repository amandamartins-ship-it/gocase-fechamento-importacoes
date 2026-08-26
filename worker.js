import { statusCache, atualizarCacheComUpload, obterMapas } from "./lib/dbCache.js";
import { parseRazao } from "./lib/razaoParser.js";
import { aplicarRateio } from "./lib/rateioEngine.js";
import { construirRazaoRateado } from "./lib/xlsxExport.js";
import { paraReais, paraCentavos } from "./lib/money.js";
import { bytesToBase64, base64ToBytes } from "./lib/base64.js";

// --- Conciliador de Importações: módulo aditivo, não toca nas importações/rotas acima. ---
import { montarComposicaoTodosProcessos, CAMPOS_DESPESA, CAMPOS_TRIBUTOS_DI, calcularTotalInformadoCentavos } from "./lib/conciliador/composicaoEngine.js";
import { listarDespesas, listarDespesasDoMes, salvarDespesa } from "./lib/conciliador/despesasRepository.js";
import { listarTributosDi, listarTributosDiDoMes, salvarTributoDi } from "./lib/conciliador/tributosDiRepository.js";
import { parseRazaoRateado } from "./lib/conciliador/razaoRateadoXlsxParser.js";
import { marcarFechado, desmarcarFechado, listarFechadosDoMes } from "./lib/conciliador/statusRepository.js";
import { montarLinhasFechamentoContabil, construirCsvFechamento } from "./lib/conciliador/fechamentoContabilExport.js";

// --- Importações em Andamento: base histórica ---
import { obterStatus, inserirLinhas, obterHistoricoDoProcesso, obterSaldosPorMes, obterTodoHistorico } from "./lib/importacoesRepository.js";
import { parseImportacoesEmAndamento } from "./lib/importacoesParser.js";

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function bytesDoBody(body) {
  if (!body || typeof body.contentBase64 !== "string" || !body.contentBase64) {
    return null;
  }
  return base64ToBytes(body.contentBase64);
}

async function handleMasterStatus(env) {
  const status = await statusCache(env);
  return json(status);
}

async function handleMasterUpload(request, env) {
  const body = await request.json().catch(() => null);
  const bytes = bytesDoBody(body);
  if (!bytes) {
    return json({ error: "Envie { filename, contentBase64 } com o conteúdo do Controle de Importações.xlsx." }, 400);
  }
  const resultado = await atualizarCacheComUpload(env, bytes, body.filename || "Controle de Importações.xlsx");
  return json({ updatedAt: resultado.updatedAt, arquivoNome: resultado.arquivoNome, totalProcessos: resultado.totalProcessos });
}

async function handleProcess(request, env) {
  const body = await request.json().catch(() => null);
  const bytes = bytesDoBody(body);
  if (!bytes) {
    return json({ error: "Envie { filename, contentBase64 } com o conteúdo do Razão." }, 400);
  }

  const { linhas, mesReferencia } = parseRazao(bytes);
  const mapas = await obterMapas(env);
  const { linhasSaida, pendencias, totais } = aplicarRateio(linhas, mapas);

  const saldoBate = totais.debitoAntes === totais.debitoDepois && totais.creditoAntes === totais.creditoDepois;

  const xlsxBytes = construirRazaoRateado(linhasSaida);
  const xlsxBase64 = bytesToBase64(xlsxBytes);

  const totalRateados = linhasSaida.filter((l) => l.rateado).length;

  return json({
    mesReferencia,
    totais: {
      debitoAntesReais: paraReais(totais.debitoAntes),
      creditoAntesReais: paraReais(totais.creditoAntes),
      debitoDepoisReais: paraReais(totais.debitoDepois),
      creditoDepoisReais: paraReais(totais.creditoDepois),
      saldoBate,
    },
    resumo: {
      totalLancamentos: linhas.length,
      totalLinhasSaida: linhasSaida.length,
      totalRateados,
      totalPendencias: pendencias.length,
    },
    pendencias,
    preview: linhasSaida.slice(0, 200).map((l) => ({
      empresa: l.empresa,
      data: l.data,
      historico: l.historico,
      debito: paraReais(l.valorDebitoCentavos),
      credito: paraReais(l.valorCreditoCentavos),
      processo: l.processo,
      processoFull: l.processoFull,
      rateado: l.rateado,
      pendencia: l.pendencia,
    })),
    xlsxBase64,
    nomeArquivoSugerido: `Razao_Rateado_${mesReferencia ? `${String(mesReferencia.mes).padStart(2, "0")}${mesReferencia.ano}` : "sem_data"}.xlsx`,
  });
}

// --- Conciliador de Importações: handlers novos, isolados do Rateador. ---

function mesReferenciaChave(mesReferencia) {
  if (!mesReferencia) return null;
  return `${mesReferencia.ano}-${String(mesReferencia.mes).padStart(2, "0")}`;
}

function serializarLinhaAuditoria(l) {
  return {
    historico: l.historico,
    data: l.data,
    contaContabil: l.contaContabil,
    numeroContabil: l.numeroContabil,
    debito: paraReais(l.valorDebitoCentavos),
    credito: paraReais(l.valorCreditoCentavos),
    processo: l.processo,
    processoFull: l.processoFull,
    rateado: l.rateado,
    rateioInfo: l.rateioInfo || null,
  };
}

function serializarComposicao(composicao) {
  return {
    categorias: composicao.categorias.map((c) => ({
      categoria: c.categoria,
      debitoContabilizado: paraReais(c.debitoContabilizadoCentavos),
      creditoContabilizado: paraReais(c.creditoContabilizadoCentavos),
      informado: paraReais(c.informadoCentavos),
      total: paraReais(c.totalCentavos),
      linhas: c.linhas.map(serializarLinhaAuditoria),
    })),
    totais: {
      debitoContabilizado: paraReais(composicao.totais.debitoContabilizadoCentavos),
      creditoContabilizado: paraReais(composicao.totais.creditoContabilizadoCentavos),
      informado: paraReais(composicao.totais.informadoCentavos),
      saldoFinal: paraReais(composicao.totais.saldoFinalCentavos),
      diferenca: paraReais(composicao.totais.diferencaCentavos),
    },
    status: composicao.status,
    dicas: composicao.dicas,
    encontroContasDI: {
      numerarioDebito: paraReais(composicao.encontroContasDI.numerarioDebitoCentavos),
      nfEntradaCredito: paraReais(composicao.encontroContasDI.nfEntradaCreditoCentavos),
      residuo: paraReais(composicao.encontroContasDI.residuoCentavos),
      totalDeclaradoDI: paraReais(composicao.encontroContasDI.totalDeclaradoDICentavos),
      tipo: composicao.encontroContasDI.tipo,
    },
  };
}

async function handleConciliadorProcess(request, env) {
  const body = await request.json().catch(() => null);
  const bytes = bytesDoBody(body);
  if (!bytes) {
    return json({ error: "Envie { filename, contentBase64 } com o conteúdo do Razão Rateado (.xlsx)." }, 400);
  }

  // Consome diretamente o Excel já rateado (saída do próprio Rateador) - não
  // sobe o Razão bruto de novo nem roda o motor de rateio uma segunda vez.
  const { linhasSaida, pendenciasRateio, mesReferencia } = parseRazaoRateado(bytes);
  const mesChave = mesReferenciaChave(mesReferencia);
  if (!mesChave) {
    return json({ error: "Não foi possível determinar o mês de referência do arquivo enviado." }, 400);
  }

  const despesasPorProcesso = await listarDespesasDoMes(env, mesChave);
  const fechadosManualmente = await listarFechadosDoMes(env, mesChave);
  const tributosDiPorProcesso = await listarTributosDiDoMes(env, mesChave);
  const processos = montarComposicaoTodosProcessos(linhasSaida, pendenciasRateio, despesasPorProcesso, fechadosManualmente, tributosDiPorProcesso);

  return json({
    mesReferencia,
    mesReferenciaChave: mesChave,
    camposDespesa: CAMPOS_DESPESA,
    camposTributosDi: CAMPOS_TRIBUTOS_DI,
    processos: processos.map(({ processo, composicao }) => ({ processo, composicao: serializarComposicao(composicao) })),
    pendenciasRateio,
  });
}

async function handleConciliadorDespesasGet(url, env) {
  const processo = url.searchParams.get("processo");
  const mes = url.searchParams.get("mes");
  if (!processo || !mes) {
    return json({ error: "Informe processo e mes (YYYY-MM) na query." }, 400);
  }
  const despesas = await listarDespesas(env, processo, mes);
  const resultado = {};
  for (const campo of CAMPOS_DESPESA) {
    resultado[campo] = paraReais(despesas.get(campo) || 0);
  }
  return json({ processo, mes, despesas: resultado });
}

async function handleConciliadorDespesasPost(request, env) {
  const body = await request.json().catch(() => null);
  if (!body || !body.processo || !body.mesReferencia || !body.campo) {
    return json({ error: "Envie { processo, mesReferencia, campo, valorReais }." }, 400);
  }
  if (!CAMPOS_DESPESA.includes(body.campo)) {
    return json({ error: `Campo de despesa desconhecido: ${body.campo}` }, 400);
  }
  const valorCentavos = paraCentavos(Number(body.valorReais) || 0);
  await salvarDespesa(env, body.processo, body.mesReferencia, body.campo, valorCentavos);
  return json({ ok: true });
}

async function handleConciliadorTributosDiGet(url, env) {
  const processo = url.searchParams.get("processo");
  const mes = url.searchParams.get("mes");
  if (!processo || !mes) {
    return json({ error: "Informe processo e mes (YYYY-MM) na query." }, 400);
  }
  const tributosDi = await listarTributosDi(env, processo, mes);
  const resultado = {};
  for (const campo of CAMPOS_TRIBUTOS_DI) {
    resultado[campo] = paraReais(tributosDi.get(campo) || 0);
  }
  return json({ processo, mes, tributosDi: resultado });
}

async function handleConciliadorTributosDiPost(request, env) {
  const body = await request.json().catch(() => null);
  if (!body || !body.processo || !body.mesReferencia || !body.campo) {
    return json({ error: "Envie { processo, mesReferencia, campo, valorReais }." }, 400);
  }
  if (!CAMPOS_TRIBUTOS_DI.includes(body.campo)) {
    return json({ error: `Campo de tributo DI desconhecido: ${body.campo}` }, 400);
  }
  const valorCentavos = paraCentavos(Number(body.valorReais) || 0);
  await salvarTributoDi(env, body.processo, body.mesReferencia, body.campo, valorCentavos);
  return json({ ok: true });
}

async function handleConciliadorFechar(request, env) {
  const body = await request.json().catch(() => null);
  if (!body || !body.processo || !body.mesReferencia) {
    return json({ error: "Envie { processo, mesReferencia }." }, 400);
  }
  await marcarFechado(env, body.processo, body.mesReferencia);
  return json({ ok: true });
}

async function handleConciliadorReabrir(request, env) {
  const body = await request.json().catch(() => null);
  if (!body || !body.processo || !body.mesReferencia) {
    return json({ error: "Envie { processo, mesReferencia }." }, 400);
  }
  await desmarcarFechado(env, body.processo, body.mesReferencia);
  return json({ ok: true });
}

/** Relatório final de fechamento: gera o lançamento contábil real (CSV, no
 * layout de importação em lote) dos processos que a usuária marcou como
 * Fechado. O lado "despesas informadas" vem do banco (fonte autoritativa,
 * já persistida); o lado "contabilizado" (débito/crédito do Razão) só
 * existe na sessão do navegador (derivado do Razão Rateado enviado), por
 * isso vem do cliente. */
async function handleConciliadorRelatorio(request, env) {
  const body = await request.json().catch(() => null);
  if (!body || !body.mesReferencia || !Array.isArray(body.processos)) {
    return json(
      { error: "Envie { mesReferencia, processos: [{processo, debitoContabilizado, creditoContabilizado}] }." },
      400
    );
  }

  const despesasPorProcesso = await listarDespesasDoMes(env, body.mesReferencia);
  const tributosDiPorProcesso = await listarTributosDiDoMes(env, body.mesReferencia);

  const processosParaFechamento = body.processos.map((p) => {
    const despesas = despesasPorProcesso.get(p.processo) || new Map();
    const tributosDi = tributosDiPorProcesso.get(p.processo) || new Map();
    const totalInformadoCentavos = calcularTotalInformadoCentavos(despesas, tributosDi);
    return {
      processo: p.processo,
      debitoContabilizadoCentavos: paraCentavos(Number(p.debitoContabilizado) || 0),
      creditoContabilizadoCentavos: paraCentavos(Number(p.creditoContabilizado) || 0),
      totalInformadoCentavos,
    };
  });

  const linhas = montarLinhasFechamentoContabil(processosParaFechamento, body.mesReferencia);
  const csv = construirCsvFechamento(linhas);

  return json({
    linhas: linhas.map((l) => ({ ...l, valorReais: paraReais(l.valorCentavos) })),
    csv,
  });
}

// --- Importações em Andamento: handlers ---

async function handleImportacoesStatus(env) {
  const status = await obterStatus(env);
  return json(status);
}

async function handleImportacoesSeed(request, env) {
  const body = await request.json().catch(() => null);
  const bytes = bytesDoBody(body);

  if (!bytes) {
    return json({ error: "Envie { filename, contentBase64 } com o arquivo Excel 'Importações em Andamento'." }, 400);
  }

  try {
    const { linhas, mesReferencia, totalLinhas } = parseImportacoesEmAndamento(bytes);
    const resultado = await inserirLinhas(env, linhas, mesReferencia);

    return json({
      arquivo: body.filename || "Importações em Andamento.xlsx",
      mesReferencia,
      totalProcessados: resultado.totalProcessados,
      insertados: resultado.insertados,
      erros: resultado.erros,
      status: resultado.erros.length === 0 ? "sucesso" : "parcial",
    });
  } catch (err) {
    return json({ error: `Erro ao processar arquivo: ${err.message}` }, 400);
  }
}

async function handleImportacoesHistorico(url, env) {
  const mesReferencia = url.searchParams.get("mes");
  const historico = await obterTodoHistorico(env, mesReferencia);

  return json({
    total: historico.length,
    mesReferencia: mesReferencia || "todos",
    linhas: historico,
  });
}

async function handleImportacoesProcesso(codProcesso, env) {
  const linhas = await obterHistoricoDoProcesso(env, codProcesso);
  const saldosPorMes = await obterSaldosPorMes(env, codProcesso);

  // Calcular saldo total acumulado
  let saldoFinal = 0;
  let debitoTotal = 0;
  let creditoTotal = 0;

  for (const linha of linhas) {
    debitoTotal += linha.debito || 0;
    creditoTotal += linha.credito || 0;
  }

  saldoFinal = debitoTotal - creditoTotal;

  return json({
    processo: codProcesso,
    totalLinhas: linhas.length,
    resumo: {
      debitoTotal: paraReais(debitoTotal * 100),
      creditoTotal: paraReais(creditoTotal * 100),
      saldoFinal: paraReais(saldoFinal * 100),
    },
    saldosPorMes: saldosPorMes.map((s) => ({
      mes: s.mes_referencia,
      debito: paraReais(s.debito_total * 100),
      credito: paraReais(s.credito_total * 100),
      saldoFinal: paraReais(s.saldo_final * 100),
      linhas: s.quantidade_linhas,
    })),
    historico: linhas.map((l) => ({
      data: l.data,
      historico: l.historico,
      debito: paraReais(l.debito * 100),
      credito: paraReais(l.credito * 100),
      saldo: paraReais(l.saldo * 100),
      status: l.status,
      fornecedor: l.fornecedor,
    })),
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return json({ status: "ok" });
    }

    // Diagnóstico temporário: confirma se DecompressionStream (API nativa,
    // sem dependência npm) funciona neste runtime.
    if (url.pathname === "/api/diag") {
      try {
        const original = new TextEncoder().encode("teste-de-compressao-1234");
        const comprimido = await new Response(
          new Blob([original]).stream().pipeThrough(new CompressionStream("deflate-raw"))
        ).arrayBuffer();
        const descomprimido = await new Response(
          new Blob([comprimido]).stream().pipeThrough(new DecompressionStream("deflate-raw"))
        ).arrayBuffer();
        const texto = new TextDecoder().decode(descomprimido);
        return json({ ok: true, roundtripOk: texto === "teste-de-compressao-1234" });
      } catch (err) {
        return json({ ok: false, error: String(err && err.stack ? err.stack : err) }, 500);
      }
    }

    try {
      if (url.pathname === "/api/master-status" && request.method === "GET") {
        return await handleMasterStatus(env);
      }
      if (url.pathname === "/api/master-upload" && request.method === "POST") {
        return await handleMasterUpload(request, env);
      }
      if (url.pathname === "/api/process" && request.method === "POST") {
        return await handleProcess(request, env);
      }

      // --- Conciliador de Importações: rotas novas, não afetam as acima. ---
      if (url.pathname === "/api/conciliador/process" && request.method === "POST") {
        return await handleConciliadorProcess(request, env);
      }
      if (url.pathname === "/api/conciliador/despesas" && request.method === "GET") {
        return await handleConciliadorDespesasGet(url, env);
      }
      if (url.pathname === "/api/conciliador/despesas" && request.method === "POST") {
        return await handleConciliadorDespesasPost(request, env);
      }
      if (url.pathname === "/api/conciliador/tributos-di" && request.method === "GET") {
        return await handleConciliadorTributosDiGet(url, env);
      }
      if (url.pathname === "/api/conciliador/tributos-di" && request.method === "POST") {
        return await handleConciliadorTributosDiPost(request, env);
      }
      if (url.pathname === "/api/conciliador/relatorio" && request.method === "POST") {
        return await handleConciliadorRelatorio(request, env);
      }
      if (url.pathname === "/api/conciliador/fechar" && request.method === "POST") {
        return await handleConciliadorFechar(request, env);
      }
      if (url.pathname === "/api/conciliador/reabrir" && request.method === "POST") {
        return await handleConciliadorReabrir(request, env);
      }

      // --- Importações em Andamento: rotas de seed/histórico ---
      if (url.pathname === "/api/importacoes/status" && request.method === "GET") {
        return await handleImportacoesStatus(env);
      }
      if (url.pathname === "/api/importacoes/seed" && request.method === "POST") {
        return await handleImportacoesSeed(request, env);
      }
      if (url.pathname === "/api/importacoes/historico" && request.method === "GET") {
        return await handleImportacoesHistorico(url, env);
      }
      if (url.pathname.startsWith("/api/importacoes/processo/") && request.method === "GET") {
        const codProcesso = url.pathname.split("/").pop();
        return await handleImportacoesProcesso(codProcesso, env);
      }
    } catch (err) {
      return json({ error: String(err && err.message ? err.message : err) }, 500);
    }

    return new Response("not found", { status: 404 });
  },
};
