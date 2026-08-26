/** Motor de composição/fechamento do Conciliador: agrupa as linhas já
 * rateadas (saída do `aplicarRateio` já existente, nunca modificado) por
 * processo e por categoria de natureza, cruza com as despesas informadas
 * manualmente, e calcula saldo/diferença/status em tempo real. Módulo
 * exclusivo do Conciliador - não compartilha estado com o Rateador, só
 * consome sua saída. */

import { classificarCategoria, CATEGORIAS } from "./categoriaClassifier.js";
import { processoBase } from "../razaoParser.js";

/** Campos de despesa editáveis manualmente (tela "Despesas da Importação").
 * AFRMM e Siscomex saíram daqui - agora são valores de referência no encontro
 * de contas da DI (ver CAMPOS_TRIBUTOS_DI), não despesa aditiva. */
export const CAMPOS_DESPESA = [
  "Frete Internacional",
  "Frete Nacional",
  "Armazenagem",
  "Honorários",
  "Seguro",
  "Capatazia",
  "IOF",
  "Taxas",
  "Outras despesas",
];

/** Campos declarados na DI (tela "Tributos e Frete Declarados na DI"),
 * digitados manualmente como referência - nunca somam direto como despesa.
 * PIS/COFINS/IPI/ICMS/Siscomex/AFRMM entram no encontro de contas Numerário
 * × NF Entrada (ver TRIBUTOS_DI_REFERENCIA_ENCONTRO); "Frete" entra no
 * confronto Frete DI × Frete Recibo, subtraindo da despesa de Frete. */
export const CAMPOS_TRIBUTOS_DI = ["PIS", "COFINS", "IPI", "ICMS", "Siscomex", "AFRMM", "Frete"];

// Campos de CAMPOS_TRIBUTOS_DI que entram na soma "Total Declarado na DI" do
// encontro de contas - "Frete" fica de fora, ele tem seu próprio confronto
// (contra o Frete pago/recibo), não contra Numerário/NF Entrada.
const TRIBUTOS_DI_REFERENCIA_ENCONTRO = ["PIS", "COFINS", "IPI", "ICMS", "Siscomex", "AFRMM"];

// Mapeia cada campo de despesa (granular, como a usuária digita) para a
// categoria contabilizada correspondente (Frete Internacional/Nacional
// somam na única categoria "Frete"; Taxas não tem categoria própria do lado
// contabilizado, mesmo precedente do ICMS/Siscomex -> Outras Despesas).
const DESPESA_PARA_CATEGORIA = {
  "Frete Internacional": CATEGORIAS.FRETE,
  "Frete Nacional": CATEGORIAS.FRETE,
  Armazenagem: CATEGORIAS.ARMAZENAGEM,
  Honorários: CATEGORIAS.HONORARIOS,
  Seguro: CATEGORIAS.SEGURO,
  Capatazia: CATEGORIAS.CAPATAZIA,
  IOF: CATEGORIAS.IOF,
  Taxas: CATEGORIAS.OUTRAS_DESPESAS,
  "Outras despesas": CATEGORIAS.OUTRAS_DESPESAS,
};

/** Única fonte da verdade do total informado (despesas aditivas menos o
 * Frete já cobrado pela DI) - usada tanto na composição em tempo real quanto
 * no relatório final de fechamento, pra nunca haver duas fórmulas
 * divergentes.
 * @param {Map<string, number>} despesasInformadas - campo (CAMPOS_DESPESA) -> centavos
 * @param {Map<string, number>} tributosDiInformados - campo (CAMPOS_TRIBUTOS_DI) -> centavos
 */
export function calcularTotalInformadoCentavos(despesasInformadas, tributosDiInformados) {
  let total = 0;
  for (const campo of CAMPOS_DESPESA) total += despesasInformadas.get(campo) || 0;
  total -= (tributosDiInformados && tributosDiInformados.get("Frete")) || 0;
  return total;
}

export const STATUS = {
  FECHADO: "Fechado",
  PENDENTE: "Pendente",
  BLOQUEADO: "Bloqueado",
};

const TOLERANCIA_VARIACAO_CAMBIAL = 0.02; // 2%, mesmo valor do sistema de referência

/** Agrupa as linhas por categoria, somando débito/crédito contabilizado, e
 * anexa as próprias linhas (auditoria: histórico, conta, valor original). */
function agruparPorCategoria(linhasDoProcesso) {
  const porCategoria = new Map();
  for (const linha of linhasDoProcesso) {
    const categoria = classificarCategoria(linha.historico);
    let bucket = porCategoria.get(categoria);
    if (!bucket) {
      bucket = { categoria, debitoContabilizadoCentavos: 0, creditoContabilizadoCentavos: 0, linhas: [] };
      porCategoria.set(categoria, bucket);
    }
    bucket.debitoContabilizadoCentavos += linha.valorDebitoCentavos;
    bucket.creditoContabilizadoCentavos += linha.valorCreditoCentavos;
    bucket.linhas.push(linha);
  }
  return porCategoria;
}

/** Agrupa as despesas informadas (por campo granular) na categoria
 * contabilizada correspondente, subtraindo da categoria Frete o valor de
 * frete já declarado na DI (confronto Frete DI × Frete Recibo - só o que
 * excede o declarado é despesa de fato). */
function agruparDespesasPorCategoria(despesasInformadas, tributosDiInformados) {
  const porCategoria = new Map();
  for (const [campo, categoria] of Object.entries(DESPESA_PARA_CATEGORIA)) {
    const valor = despesasInformadas.get(campo) || 0;
    if (valor === 0) continue;
    porCategoria.set(categoria, (porCategoria.get(categoria) || 0) + valor);
  }
  const freteDiCentavos = (tributosDiInformados && tributosDiInformados.get("Frete")) || 0;
  if (freteDiCentavos !== 0) {
    porCategoria.set(CATEGORIAS.FRETE, (porCategoria.get(CATEGORIAS.FRETE) || 0) - freteDiCentavos);
  }
  return porCategoria;
}

// Só as categorias que correspondem a um campo de despesa editável (ver
// DESPESA_PARA_CATEGORIA) entram na checagem de "não informado" - categorias
// de crédito/receita (Numerário, Reembolso, NF Entrada, Mercadoria, Variação
// Cambial) não fazem sentido nessa dica, mesmo com saldo pendente.
const CATEGORIAS_DE_DESPESA = Array.from(new Set(Object.values(DESPESA_PARA_CATEGORIA)));

function gerarDicas(categorias, saldoFinalCentavos, totalDebitoContabilizadoCentavos) {
  const dicas = [];
  if (saldoFinalCentavos === 0) return dicas;

  const porCategoria = new Map(categorias.map((c) => [c.categoria, c]));
  for (const categoriaDespesa of CATEGORIAS_DE_DESPESA) {
    const item = porCategoria.get(categoriaDespesa);
    const semNada = !item || item.debitoContabilizadoCentavos + item.informadoCentavos === 0;
    if (semNada) {
      dicas.push(`${categoriaDespesa} não informado/pendente.`);
    }
  }

  const base = totalDebitoContabilizadoCentavos || 1;
  if (Math.abs(saldoFinalCentavos) / base <= TOLERANCIA_VARIACAO_CAMBIAL) {
    dicas.push("Possível variação cambial.");
  }
  return dicas;
}

/**
 * @param {object[]} linhasDoProcesso - linhasSaida (do aplicarRateio) já filtradas para 1 processo
 * @param {Map<string, number>} despesasInformadas - campo de despesa (CAMPOS_DESPESA) -> centavos
 * @param {boolean} temPendenciaRateio - true se alguma linha deste processo ficou com `pendencia` != null
 * @param {boolean} fechadoManualmente - true se a usuária marcou este processo/mês como Fechado
 *   (decisão manual - replica o processo manual já existente; o saldo pode fechar com uma diferença
 *   real, que vira variação cambial no lançamento de fechamento, não precisa ser R$0,00 exato)
 * @param {Map<string, number>} tributosDiInformados - campo declarado na DI (CAMPOS_TRIBUTOS_DI) -> centavos
 * @returns {object} composição completa do processo
 */
export function montarComposicaoProcesso(linhasDoProcesso, despesasInformadas, temPendenciaRateio, fechadoManualmente, tributosDiInformados) {
  const tributosDi = tributosDiInformados || new Map();
  const porCategoriaContabilizado = agruparPorCategoria(linhasDoProcesso);
  const porCategoriaInformado = agruparDespesasPorCategoria(despesasInformadas, tributosDi);

  const nomesCategorias = new Set([...porCategoriaContabilizado.keys(), ...porCategoriaInformado.keys()]);

  let totalDebitoContabilizadoCentavos = 0;
  let totalCreditoContabilizadoCentavos = 0;
  let totalInformadoCentavos = 0;

  const categorias = [];
  for (const categoria of nomesCategorias) {
    const contabilizado = porCategoriaContabilizado.get(categoria);
    const informadoCentavos = porCategoriaInformado.get(categoria) || 0;
    const debitoContabilizadoCentavos = contabilizado ? contabilizado.debitoContabilizadoCentavos : 0;
    const creditoContabilizadoCentavos = contabilizado ? contabilizado.creditoContabilizadoCentavos : 0;

    totalDebitoContabilizadoCentavos += debitoContabilizadoCentavos;
    totalCreditoContabilizadoCentavos += creditoContabilizadoCentavos;
    totalInformadoCentavos += informadoCentavos;

    categorias.push({
      categoria,
      debitoContabilizadoCentavos,
      creditoContabilizadoCentavos,
      informadoCentavos,
      totalCentavos: debitoContabilizadoCentavos + informadoCentavos - creditoContabilizadoCentavos,
      linhas: contabilizado ? contabilizado.linhas : [],
    });
  }
  categorias.sort((a, b) => a.categoria.localeCompare(b.categoria, "pt-BR"));

  const saldoFinalCentavos =
    totalDebitoContabilizadoCentavos + totalInformadoCentavos - totalCreditoContabilizadoCentavos;

  let status;
  if (temPendenciaRateio) {
    status = STATUS.BLOQUEADO;
  } else if (fechadoManualmente) {
    status = STATUS.FECHADO;
  } else {
    status = STATUS.PENDENTE;
  }

  const dicas = status === STATUS.PENDENTE ? gerarDicas(categorias, saldoFinalCentavos, totalDebitoContabilizadoCentavos) : [];

  // Encontro de contas dos tributos da DI: o Numerário (adiantamento pago,
  // débito) deveria ser compensado pela NF de Entrada (crédito) - o que
  // sobra/falta é reembolsado/cobrado pelo despachante, nunca uma despesa
  // nova. PIS/COFINS/IPI/ICMS/Siscomex/AFRMM declarados servem só de
  // referência pra essa conferência (não entram em nenhuma soma de despesa).
  const numerario = porCategoriaContabilizado.get(CATEGORIAS.NUMERARIO);
  const nfEntrada = porCategoriaContabilizado.get(CATEGORIAS.NF_ENTRADA);
  const numerarioDebitoCentavos = numerario ? numerario.debitoContabilizadoCentavos : 0;
  const nfEntradaCreditoCentavos = nfEntrada ? nfEntrada.creditoContabilizadoCentavos : 0;
  const residuoCentavos = numerarioDebitoCentavos - nfEntradaCreditoCentavos;
  const totalDeclaradoDICentavos = TRIBUTOS_DI_REFERENCIA_ENCONTRO.reduce(
    (acc, campo) => acc + (tributosDi.get(campo) || 0),
    0
  );
  const encontroContasDI = {
    numerarioDebitoCentavos,
    nfEntradaCreditoCentavos,
    residuoCentavos,
    totalDeclaradoDICentavos,
    tipo: residuoCentavos > 0 ? "reembolso" : residuoCentavos < 0 ? "cobranca" : "ok",
  };

  return {
    categorias,
    totais: {
      debitoContabilizadoCentavos: totalDebitoContabilizadoCentavos,
      creditoContabilizadoCentavos: totalCreditoContabilizadoCentavos,
      informadoCentavos: totalInformadoCentavos,
      saldoFinalCentavos,
      diferencaCentavos: saldoFinalCentavos,
    },
    status,
    dicas,
    encontroContasDI,
  };
}

/**
 * Monta a composição de TODOS os processos encontrados no Razão processado.
 * @param {object[]} linhasSaida - saída completa de aplicarRateio
 * @param {{historico:string, motivo:string}[]} pendencias - saída de aplicarRateio
 * @param {Map<string, Map<string, number>>} despesasPorProcesso - de despesasRepository.listarDespesasDoMes
 * @param {Set<string>} processosFechadosManualmente - de statusRepository.listarFechadosDoMes
 * @param {Map<string, Map<string, number>>} tributosDiPorProcesso - de tributosDiRepository.listarTributosDiDoMes
 * @returns {{processo:string, composicao:object}[]}
 */
export function montarComposicaoTodosProcessos(linhasSaida, pendencias, despesasPorProcesso, processosFechadosManualmente, tributosDiPorProcesso) {
  const historicosComPendencia = new Set(pendencias.map((p) => p.historico));
  const fechados = processosFechadosManualmente || new Set();
  const tributosDi = tributosDiPorProcesso || new Map();

  const linhasPorProcesso = new Map();
  for (const linha of linhasSaida) {
    if (!linha.processo) continue; // lançamento sem processo citado - fora do escopo do Conciliador
    const base = processoBase(linha.processo);
    let lista = linhasPorProcesso.get(base);
    if (!lista) {
      lista = [];
      linhasPorProcesso.set(base, lista);
    }
    lista.push(linha);
  }

  const resultado = [];
  for (const [processo, linhas] of linhasPorProcesso) {
    const temPendencia = linhas.some((l) => l.pendencia || historicosComPendencia.has(l.historico));
    const despesas = despesasPorProcesso.get(processo) || new Map();
    const tributosDiDoProcesso = tributosDi.get(processo) || new Map();
    const composicao = montarComposicaoProcesso(linhas, despesas, temPendencia, fechados.has(processo), tributosDiDoProcesso);
    resultado.push({ processo, composicao });
  }
  resultado.sort((a, b) => a.processo.localeCompare(b.processo, "pt-BR"));
  return resultado;
}
