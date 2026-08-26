/** Gera o Excel de saída com as linhas já rateadas - 12 colunas, sem coluna
 * Status (este app só faz rateio, não fechamento). */

import * as XLSX from "xlsx";
import { paraReais } from "./money.js";

export const CABECALHO = [
  "Empresa",
  "Data",
  "Conta",
  "Numero Contabil",
  "Unidade",
  "Historico",
  "Debito",
  "Credito",
  "Movimentação",
  "Saldo Anterior",
  "Saldo Final",
  "Processo",
  "Processo Full",
  "Processo (Controle de Importação)",
];

function formatarData(data) {
  if (!data) return null;
  const dd = String(data.dia).padStart(2, "0");
  const mm = String(data.mes).padStart(2, "0");
  return `${dd}/${mm}/${data.ano}`;
}

function linhaParaRow(linha, acumulador) {
  const debito = paraReais(linha.valorDebitoCentavos);
  const credito = paraReais(linha.valorCreditoCentavos);
  const movimento = debito - credito;

  // Saldo anterior é o acumulado até agora (antes desta linha)
  const saldoAnterior = acumulador.saldoTotal;

  // Atualizar saldo acumulado para calcular saldo final desta linha
  acumulador.saldoTotal += movimento;
  const saldoFinal = acumulador.saldoTotal;

  return [
    linha.empresa,
    formatarData(linha.data),
    linha.contaContabil,
    linha.numeroContabil,
    linha.unidade,
    linha.historico,
    debito,
    credito,
    movimento,
    saldoAnterior,
    saldoFinal,
    linha.processo,
    linha.processoFull,
    linha.processoControleImportacao,
  ];
}

/** @param {object[]} linhasSaida @returns {Uint8Array} */
export function construirRazaoRateado(linhasSaida) {
  const wb = XLSX.utils.book_new();
  const acumulador = { saldoTotal: 0 };
  const dados = [CABECALHO, ...linhasSaida.map((linha) => linhaParaRow(linha, acumulador))];
  const ws = XLSX.utils.aoa_to_sheet(dados);
  XLSX.utils.book_append_sheet(wb, ws, "Razão Rateado");
  const out = XLSX.write(wb, { type: "array", bookType: "xlsx" });
  return new Uint8Array(out);
}
