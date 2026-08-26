/** Parser do Excel "Importações em Andamento" para extrair histórico.
 * Lê a aba "Base 2026" (ou "antiga") e transforma em array de linhas. */

import * as XLSX from "xlsx";
import { parseValorBrl, paraCentavos } from "./money.js";

export function parseImportacoesEmAndamento(bytes) {
  const workbook = XLSX.read(bytes, { type: "array" });

  // Tentar ler a aba "Base 2026" primeiro, depois fallback para "antiga"
  let sheetName = "Base 2026  "; // nota: espaços no final (como no arquivo)
  if (!workbook.SheetNames.includes(sheetName)) {
    sheetName = "Base 2026";
  }
  if (!workbook.SheetNames.includes(sheetName)) {
    sheetName = "antiga";
  }
  if (!workbook.SheetNames.includes(sheetName)) {
    throw new Error(
      `Nenhuma aba encontrada. Abas disponíveis: ${workbook.SheetNames.join(", ")}`
    );
  }

  const worksheet = workbook.Sheets[sheetName];
  const dados = XLSX.utils.sheet_to_json(worksheet, { defval: "" });

  const linhas = [];

  for (const row of dados) {
    // Extrair valores, convertendo tipo conforme necessário
    const empresa = String(row.Empresa || "").trim();
    const dataStr = row.Data ? String(row.Data).trim() : "";
    const conta = row.Conta ? String(row.Conta).trim() : "";
    const numeroContabil = row["Numero Contabil"] ? String(row["Numero Contabil"]).trim() : "";
    const unidade = row.Unidade ? String(row.Unidade).trim() : "";
    const historico = row.Historico ? String(row.Historico).trim() : "";
    const debitoStr = row.Debito ? String(row.Debito).trim() : "0";
    const creditoStr = row.Credito ? String(row.Credito).trim() : "0";

    // Obter valor bruto de movimentação (pode ser número, data, nulo)
    const movimentacaoRaw = row["Movimentação"] || row["Movimenta"] || null;
    // Converter para String ANTES de chamar .replace() — trata números, datas, nulos
    const movimentacaoStr = String(movimentacaoRaw ?? '').replace(/[^\d.-]/g, "") ||
      (parseFloat(debitoStr.replace(/[^\d.-]/g, "")) - parseFloat(creditoStr.replace(/[^\d.-]/g, ""))) || "0";

    const saldoStr = row.Saldo ? String(row.Saldo).trim() : "0";
    const processo = row.Processo ? String(row.Processo).trim() : "";
    const processoFull = row["Processo Full"] ? String(row["Processo Full"]).trim() : "";
    const processoControle = row["Processo (Controle de Importação)"] || row["Processo (Controle de Importação)"] || "";
    const dataPgtoFinal = row["DATA DE PGTO FINAL"] ? String(row["DATA DE PGTO FINAL"]).trim() : "";
    const status = row.Status ? String(row.Status).trim() : "";
    const observacao = row["Observação"] || row["Observação"] || "";
    const fornecedor = row.Fornecedor ? String(row.Fornecedor).trim() : "";

    // Validar: ignorar linhas em branco ou sem dados importantes
    if (!empresa && !historico && !debitoStr && !creditoStr) {
      continue;
    }

    // Parsear data (pode vir como texto "2022-07-25" ou como timestamp)
    let data = null;
    if (dataStr) {
      // Se for timestamp Excel, converter
      if (!isNaN(dataStr)) {
        const excel_epoch = new Date(1899, 11, 30);
        const days = parseInt(dataStr);
        data = new Date(excel_epoch.getTime() + days * 24 * 60 * 60 * 1000);
        data = data.toISOString().split("T")[0];
      } else {
        // Tentar parsear como string de data
        data = dataStr.split(" ")[0]; // pegar só a data, ignorar hora
      }
    }

    linhas.push({
      empresa: empresa || null,
      data: data || null,
      conta: conta || null,
      numero_contabil: numeroContabil || null,
      unidade: unidade || null,
      historico: historico || null,
      debito: parseFloat(debitoStr.replace(/[^\d.-]/g, "")) || 0,
      credito: parseFloat(creditoStr.replace(/[^\d.-]/g, "")) || 0,
      saldo: parseFloat(saldoStr.replace(/[^\d.-]/g, "")) || 0,
      movimentacao: parseFloat(movimentacaoStr.replace(/[^\d.-]/g, "")) || 0,
      processo: processo || null,
      processo_full: processoFull || null,
      processo_controle: processoControle || null,
      data_pgto_final: dataPgtoFinal || null,
      status: status || null,
      observacao: observacao || null,
      fornecedor: fornecedor || null,
    });
  }

  if (linhas.length === 0) {
    throw new Error("Nenhuma linha válida encontrada no arquivo.");
  }

  // Extrair mês de referência da última data válida
  const datasValidas = linhas.filter((l) => l.data).map((l) => l.data);
  let mesReferencia = null;
  if (datasValidas.length > 0) {
    const ultimaData = datasValidas[datasValidas.length - 1];
    const [ano, mes] = ultimaData.split("-");
    mesReferencia = `${ano}-${mes}`;
  }

  return { linhas, mesReferencia, totalLinhas: linhas.length };
}
