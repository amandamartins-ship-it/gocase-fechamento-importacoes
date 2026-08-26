/** Motor de rateio: para cada lançamento do Razão que cite 2+ processos,
 * divide débito/crédito proporcionalmente ao VALOR (coluna H do Controle
 * PIs) de cada processo na NF em comum. Nunca descarta uma linha - toda
 * linha-pendência sai como 1 linha não-dividida com o valor original
 * intacto, o que é o que garante a invariante "soma antes == soma depois"
 * mesmo quando não dá pra ratear.
 *
 * O casamento de NF é feito pelo código QUALIFICADO POR EMBARQUE
 * (`processoEmbarqueQualificado`), nunca pelo código-base - cada embarque de
 * um mesmo processo pode ter NFs diferentes no Controle de Importações, e
 * usar o código-base misturava as NFs de embarques diferentes, gerando
 * ambiguidade falsa (bug real encontrado pela usuária: BBI25101.6 e
 * BBI25101.7 têm NFs distintas, mas o código-base "BBI25101" via as duas).
 *
 * Quando NENHUMA NF em comum é encontrada entre os processos citados, cai
 * num fallback: soma o valor TOTAL de cada processo.embarque citado (todas
 * as NFs dele, não uma específica) e ratea pela proporção desses valores
 * totais (regra confirmada pela usuária com um caso real). Esse fallback só
 * se aplica à ausência de NF comum - ambiguidade (2+ NFs comuns) e valor
 * inválido continuam pendência, nunca inventam um número. */

import { largestRemainderSplit } from "./money.js";
import { processoBase, processoEmbarqueQualificado } from "./razaoParser.js";

function processoControleImportacao(codigo) {
  return codigo.replace(/\./g, "-");
}

/**
 * @param {object[]} linhas - saída de parseRazao().linhas
 * @param {{valorPorProcessoNf: Map<string, number>, nfsPorProcesso: Map<string, Set<string>>, valorTotalPorProcesso: Map<string, number>}} controlePi
 * @returns {{ linhasSaida: object[], pendencias: {historico: string, motivo: string}[], totais: {debitoAntes:number, creditoAntes:number, debitoDepois:number, creditoDepois:number} }}
 */
export function aplicarRateio(linhas, controlePi) {
  const linhasSaida = [];
  const pendencias = [];

  let debitoAntes = 0;
  let creditoAntes = 0;
  let debitoDepois = 0;
  let creditoDepois = 0;

  for (const linha of linhas) {
    debitoAntes += linha.valorDebitoCentavos;
    creditoAntes += linha.valorCreditoCentavos;

    const qualificadosSet = new Set(linha.processosCodigos.map(processoEmbarqueQualificado));
    const qualificados = Array.from(qualificadosSet).sort();

    if (qualificados.length <= 1) {
      const qualificado = qualificados[0] || null;
      linhasSaida.push({
        ...linha,
        processo: qualificado ? processoBase(qualificado) : null,
        processoFull: qualificado,
        processoControleImportacao: qualificado ? processoControleImportacao(qualificado) : null,
        rateado: false,
        pendencia: null,
      });
      debitoDepois += linha.valorDebitoCentavos;
      creditoDepois += linha.valorCreditoCentavos;
      continue;
    }

    const resultado = tentarRatear(qualificados, linha, controlePi);
    if (resultado.pendencia) {
      pendencias.push({ historico: linha.historico, motivo: resultado.pendencia });
      const full = qualificados.join(" + ");
      linhasSaida.push({
        ...linha,
        processo: qualificados.map(processoBase).join(" + "),
        processoFull: full,
        processoControleImportacao: processoControleImportacao(full),
        rateado: false,
        pendencia: resultado.pendencia,
      });
      debitoDepois += linha.valorDebitoCentavos;
      creditoDepois += linha.valorCreditoCentavos;
      continue;
    }

    for (const participante of resultado.participantes) {
      linhasSaida.push({
        ...linha,
        processo: processoBase(participante.processo),
        processoFull: participante.processo,
        processoControleImportacao: processoControleImportacao(participante.processo),
        valorDebitoCentavos: participante.debitoCentavos,
        valorCreditoCentavos: participante.creditoCentavos,
        rateado: true,
        pendencia: null,
        rateioInfo: {
          fonte: resultado.fonte,
          nfUtilizada: resultado.nf || null,
          valorItens: participante.valor,
          valorTotalItensNf: resultado.valorTotal,
          percentual: participante.percentual,
        },
      });
      debitoDepois += participante.debitoCentavos;
      creditoDepois += participante.creditoCentavos;
    }
  }

  return {
    linhasSaida,
    pendencias,
    totais: { debitoAntes, creditoAntes, debitoDepois, creditoDepois },
  };
}

/** Monta os participantes/split a partir de uma lista de {processo, valor}
 * já resolvida - usado tanto pelo caminho normal (valor por NF) quanto pelo
 * fallback (valor total do processo). */
function montarParticipantes(valores, linha) {
  const valorTotal = valores.reduce((acc, q) => acc + q.valor, 0);
  const percentuais = valores.map((q) => ({ chave: q.processo, percentual: q.valor / valorTotal }));

  const splitDebito = largestRemainderSplit(linha.valorDebitoCentavos, percentuais);
  const splitCredito = largestRemainderSplit(linha.valorCreditoCentavos, percentuais);

  const participantes = valores.map((q) => ({
    processo: q.processo,
    valor: q.valor,
    percentual: q.valor / valorTotal,
    debitoCentavos: splitDebito.get(q.processo) || 0,
    creditoCentavos: splitCredito.get(q.processo) || 0,
  }));

  return { participantes, valorTotal };
}

function tentarRatear(qualificados, linha, controlePi) {
  const { valorPorProcessoNf, nfsPorProcesso, valorTotalPorProcesso } = controlePi;

  let nfsComuns = null;
  for (const qualificado of qualificados) {
    const nfs = nfsPorProcesso.get(qualificado) || new Set();
    nfsComuns = nfsComuns === null ? new Set(nfs) : new Set([...nfsComuns].filter((nf) => nfs.has(nf)));
  }
  nfsComuns = nfsComuns || new Set();

  if (nfsComuns.size > 1) {
    return {
      pendencia: `Mais de uma Nota Fiscal em comum encontrada (${[...nfsComuns].join(", ")}) entre os processos citados - ambíguo, requer revisão manual.`,
    };
  }

  if (nfsComuns.size === 1) {
    const nf = [...nfsComuns][0];
    const valores = qualificados.map((qualificado) => ({
      processo: qualificado,
      valor: valorPorProcessoNf.get(qualificado + "|" + nf),
    }));
    const semValorValido = valores.some((q) => !(typeof q.valor === "number" && q.valor > 0));
    if (semValorValido) {
      return {
        pendencia: `NF ${nf} encontrada, mas sem valor válido para todos os processos citados.`,
      };
    }
    const { participantes, valorTotal } = montarParticipantes(valores, linha);
    return { participantes, nf, valorTotal, fonte: "valor_por_nf" };
  }

  // Nenhuma NF em comum: cai no fallback - soma o valor TOTAL de cada
  // processo.embarque citado (todas as NFs dele) e ratea pela proporção.
  const valoresTotais = qualificados.map((qualificado) => ({
    processo: qualificado,
    valor: valorTotalPorProcesso.get(qualificado),
  }));
  const semValorTotalValido = valoresTotais.some((q) => !(typeof q.valor === "number" && q.valor > 0));
  if (semValorTotalValido) {
    return {
      pendencia: `Nenhuma Nota Fiscal em comum encontrada entre os processos citados (${qualificados.join(", ")}) no Controle de Importações, e nem todos têm valor total válido para o rateio por fallback.`,
    };
  }

  const { participantes, valorTotal } = montarParticipantes(valoresTotais, linha);
  return { participantes, valorTotal, fonte: "valor_total_sem_nf_comum" };
}
