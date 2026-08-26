/** Gera o lançamento contábil real de fechamento de cada processo, no
 * formato exato de importação em lote do sistema contábil da usuária
 * (CSV ";", 9 colunas). Fórmula confirmada batendo os números de dois
 * lançamentos reais já feitos manualmente:
 *
 * - 333308 (Frete/Serv. Importação): Débito = soma das despesas informadas.
 * - 113103 (Importações em Andamento): "carrega" o saldo já contabilizado
 *   do processo (débito−crédito do Razão, antes das despesas) - Débito se
 *   positivo, Crédito se negativo - tirando o processo do "em andamento".
 * - 334204 (Variação Cambial Ativa) ou 334107 (Variação Cambial Passiva):
 *   o resíduo que sobra depois de somar os dois acima, no lado que fecha a
 *   conta (Crédito = Ativa/ganho, Débito = Passiva/perda). Pode ser um
 *   valor grande de propósito - é a usuária quem decide fechar o processo
 *   assim, não uma tolerância de arredondamento. */

const CONTA_DESPESA = "333308";
const CONTA_IMPORTACOES_EM_ANDAMENTO = "113103";
const CONTA_VARIACAO_CAMBIAL_ATIVA = "334204";
const CONTA_VARIACAO_CAMBIAL_PASSIVA = "334107";
const SIGLA_UNIDADE = "50001";
const SIGLA_CENTRO_RESULTADO = "0301";

const CABECALHO_CSV = [
  "Data Lançamento",
  "Conta Contábil",
  "Sigla Unidade",
  "Sigla Centro de Resultado",
  "Valor do Lançamento",
  "Indicativo D/C",
  "Código do Terceiro",
  "Histórico",
  "Código Agrupador",
];

function ultimoDiaDoMes(ano, mes) {
  return new Date(ano, mes, 0).getDate();
}

function formatarDataIso(ano, mes, dia) {
  return `${ano}-${String(mes).padStart(2, "0")}-${String(dia).padStart(2, "0")}`;
}

function formatarDataHistorico(ano, mes, dia) {
  return `${String(dia).padStart(2, "0")}.${String(mes).padStart(2, "0")}.${ano}`;
}

/**
 * @param {{processo:string, debitoContabilizadoCentavos:number, creditoContabilizadoCentavos:number, totalInformadoCentavos:number}[]} processos
 * @param {string} mesReferenciaChave - "YYYY-MM"
 * @returns {object[]} linhas do lançamento (uma por conta movimentada)
 */
export function montarLinhasFechamentoContabil(processos, mesReferenciaChave) {
  const [ano, mes] = mesReferenciaChave.split("-").map(Number);
  const dia = ultimoDiaDoMes(ano, mes);
  const dataIso = formatarDataIso(ano, mes, dia);
  const dataHistorico = formatarDataHistorico(ano, mes, dia);

  const linhas = [];
  let agrupador = 1;

  for (const p of processos) {
    const saldoContabilizadoAntesCentavos = p.debitoContabilizadoCentavos - p.creditoContabilizadoCentavos;
    const saldoFinalCentavos = saldoContabilizadoAntesCentavos + p.totalInformadoCentavos;
    const historico = `FECHAMENTO DE PROCESSO ${p.processo} - ${dataHistorico}`;
    const agrupadorDoProcesso = agrupador++;

    const linhaBase = {
      data: dataIso,
      unidade: SIGLA_UNIDADE,
      centroResultado: SIGLA_CENTRO_RESULTADO,
      terceiro: "",
      historico,
      agrupador: agrupadorDoProcesso,
    };

    if (p.totalInformadoCentavos !== 0) {
      linhas.push({ ...linhaBase, conta: CONTA_DESPESA, valorCentavos: p.totalInformadoCentavos, indicador: "D" });
    }

    if (saldoContabilizadoAntesCentavos > 0) {
      linhas.push({ ...linhaBase, conta: CONTA_IMPORTACOES_EM_ANDAMENTO, valorCentavos: saldoContabilizadoAntesCentavos, indicador: "D" });
    } else if (saldoContabilizadoAntesCentavos < 0) {
      linhas.push({ ...linhaBase, conta: CONTA_IMPORTACOES_EM_ANDAMENTO, valorCentavos: -saldoContabilizadoAntesCentavos, indicador: "C" });
    }

    if (saldoFinalCentavos > 0) {
      linhas.push({ ...linhaBase, conta: CONTA_VARIACAO_CAMBIAL_ATIVA, valorCentavos: saldoFinalCentavos, indicador: "C" });
    } else if (saldoFinalCentavos < 0) {
      linhas.push({ ...linhaBase, conta: CONTA_VARIACAO_CAMBIAL_PASSIVA, valorCentavos: -saldoFinalCentavos, indicador: "D" });
    }
  }

  return linhas;
}

/** @param {object[]} linhas @returns {string} texto do CSV (";", CRLF) */
export function construirCsvFechamento(linhas) {
  const partes = [CABECALHO_CSV.join(";")];
  for (const l of linhas) {
    partes.push(
      [l.data, l.conta, l.unidade, l.centroResultado, (l.valorCentavos / 100).toFixed(2), l.indicador, l.terceiro, l.historico, l.agrupador].join(";")
    );
  }
  return partes.join("\r\n");
}
