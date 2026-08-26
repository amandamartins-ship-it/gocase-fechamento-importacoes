/** Lê o Excel "Razão Rateado" que o próprio Rateador exporta (mesmas 12
 * colunas de `lib/xlsxExport.js`, sheet "Razão Rateado") e devolve linhas no
 * mesmo formato que `aplicarRateio` produziria - permite ao Conciliador
 * consumir diretamente o arquivo já rateado, sem subir o Razão bruto de novo
 * nem rodar o motor de rateio uma segunda vez. Arquivo pequeno (poucas
 * centenas/milhares de linhas) - usar o SheetJS aqui é seguro, o problema de
 * memória do Rateador era só com o Controle de Importações de 9,4MB. */

import * as XLSX from "xlsx";
import { paraCentavos } from "../money.js";
import { processoBase } from "../razaoParser.js";

function parseDataBr(texto) {
  if (texto == null) return null;
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(String(texto).trim());
  if (!m) return null;
  return { dia: parseInt(m[1], 10), mes: parseInt(m[2], 10), ano: parseInt(m[3], 10) };
}

/**
 * @param {Uint8Array} bytes
 * @returns {{ linhasSaida: object[], pendenciasRateio: {historico:string, motivo:string}[], mesReferencia: {ano:number,mes:number}|null }}
 */
export function parseRazaoRateado(bytes) {
  const wb = XLSX.read(bytes, { type: "array" });
  const nomeAba = wb.SheetNames.includes("Razão Rateado") ? "Razão Rateado" : wb.SheetNames[0];
  const ws = wb.Sheets[nomeAba];
  if (!ws) {
    throw new Error("Não foi possível ler nenhuma aba do arquivo enviado.");
  }
  const linhasBrutas = XLSX.utils.sheet_to_json(ws, { header: 1, defval: null });
  if (linhasBrutas.length === 0) {
    throw new Error("Arquivo vazio.");
  }

  const cabecalho = (linhasBrutas[0] || []).map((c) => String(c ?? ""));
  const idx = (nome) => cabecalho.indexOf(nome);
  const iEmpresa = idx("Empresa");
  const iData = idx("Data");
  const iConta = idx("Conta");
  const iNumeroContabil = idx("Numero Contabil");
  const iUnidade = idx("Unidade");
  const iHistorico = idx("Historico");
  const iDebito = idx("Debito");
  const iCredito = idx("Credito");
  const iProcesso = idx("Processo");
  const iProcessoFull = idx("Processo Full");

  if (iHistorico === -1 || iDebito === -1 || iCredito === -1 || iProcesso === -1) {
    throw new Error(
      'Arquivo não parece ser um "Razão Rateado" válido (colunas esperadas não encontradas - envie o Excel exportado pelo Rateador).'
    );
  }

  const linhasSaida = [];
  const pendenciasRateio = [];
  const contagemMes = new Map();

  for (let i = 1; i < linhasBrutas.length; i++) {
    const row = linhasBrutas[i];
    if (!row || row.every((c) => c == null || c === "")) continue;

    const historico = String(row[iHistorico] ?? "");
    const debitoReais = Number(row[iDebito]) || 0;
    const creditoReais = Number(row[iCredito]) || 0;
    const processoCol = String(row[iProcesso] ?? "").trim();
    const processoFullCol = String(row[iProcessoFull] ?? "").trim();
    const data = iData !== -1 ? parseDataBr(row[iData]) : null;
    if (data) {
      const chave = `${data.ano}-${data.mes}`;
      contagemMes.set(chave, (contagemMes.get(chave) || 0) + 1);
    }

    const linhaBase = {
      empresa: iEmpresa !== -1 ? row[iEmpresa] : null,
      contaContabil: iConta !== -1 ? row[iConta] : null,
      numeroContabil: iNumeroContabil !== -1 ? row[iNumeroContabil] : null,
      unidade: iUnidade !== -1 ? row[iUnidade] : null,
      historico,
      data,
    };

    // Linhas-pendência do arquivo exportado juntam os códigos citados com
    // " + " (ver rateioEngine.js) - nunca inventamos como o valor deveria
    // ter sido dividido, só sinalizamos a pendência (Bloqueado) pros
    // processos citados, sem atribuir valor a nenhum deles.
    const ehPendencia = processoCol.includes(" + ") || processoFullCol.includes(" + ");
    if (ehPendencia) {
      const codigosCitados = processoFullCol
        .split(" + ")
        .map((c) => c.trim())
        .filter(Boolean);
      const motivo = `Linha pendente de rateio no arquivo de origem (processos citados: ${codigosCitados.join(", ")}).`;
      pendenciasRateio.push({ historico, motivo });
      const basesUnicas = new Set(codigosCitados.map(processoBase));
      for (const base of basesUnicas) {
        linhasSaida.push({
          ...linhaBase,
          processo: base,
          processoFull: processoFullCol,
          valorDebitoCentavos: 0,
          valorCreditoCentavos: 0,
          rateado: false,
          pendencia: motivo,
        });
      }
      continue;
    }

    if (!processoCol) continue; // linha sem processo nenhum - fora do escopo do Conciliador

    linhasSaida.push({
      ...linhaBase,
      processo: processoCol,
      processoFull: processoFullCol || processoCol,
      valorDebitoCentavos: paraCentavos(debitoReais),
      valorCreditoCentavos: paraCentavos(creditoReais),
      rateado: processoFullCol !== processoCol,
      pendencia: null,
    });
  }

  let mesReferencia = null;
  if (contagemMes.size > 0) {
    let melhorChave = null;
    let melhorContagem = -1;
    for (const [chave, n] of contagemMes) {
      if (n > melhorContagem) {
        melhorContagem = n;
        melhorChave = chave;
      }
    }
    const [ano, mes] = melhorChave.split("-").map(Number);
    mesReferencia = { ano, mes };
  }

  return { linhasSaida, pendenciasRateio, mesReferencia };
}
