/** Leitor mínimo de xlsx para o Controle de Importações (~9,4MB / ~30 abas).
 * O SheetJS (mesmo com a opção `sheets: ['Controle PIs']`) ainda precisa
 * descompactar o zip inteiro e montar o modelo de objetos de todas as
 * strings compartilhadas do workbook - isso sozinho já estourou o limite de
 * memória do worker no teste real. Esta versão usa `fflate` só para
 * descompactar os 3 arquivos XML de que realmente precisamos (workbook.xml,
 * seus rels, o sheetN.xml certo e sharedStrings.xml) e faz o parsing por
 * regex direto no texto, sem nenhum modelo de objetos intermediário. */

import { lerArquivosDoZip } from "./zipReader.js";

const ENTIDADES = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'" };

function decodificarEntidades(texto) {
  return texto.replace(/&(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);/g, (m, cod) => {
    if (cod in ENTIDADES) return ENTIDADES[cod];
    if (cod[0] === "#") {
      const codePoint = cod[1] === "x" || cod[1] === "X" ? parseInt(cod.slice(2), 16) : parseInt(cod.slice(1), 10);
      return String.fromCodePoint(codePoint);
    }
    return m;
  });
}

/** Converte letras de coluna Excel (A, G, AV...) para índice 0-based. */
export function colLetrasParaIndice(letras) {
  let valor = 0;
  for (const c of letras) valor = valor * 26 + (c.charCodeAt(0) - 64);
  return valor - 1;
}

/** Localiza o caminho (dentro do zip) do sheetN.xml de um nome de aba,
 * cruzando xl/workbook.xml (nome -> r:id) com xl/_rels/workbook.xml.rels
 * (r:id -> Target). */
export function resolverCaminhoAba(workbookXml, relsXml, nomeAba) {
  const sheetTagRe = /<sheet\b[^>]*\/>/g;
  let rId = null;
  const todasAsTags = [];
  let m;
  while ((m = sheetTagRe.exec(workbookXml))) {
    const tag = m[0];
    todasAsTags.push(tag);
    const nomeMatch = /\bname="([^"]*)"/.exec(tag);
    if (!nomeMatch || decodificarEntidades(nomeMatch[1]) !== nomeAba) continue;
    const idMatch = /\br:id="([^"]*)"/.exec(tag);
    if (idMatch) {
      rId = idMatch[1];
      break;
    }
  }
  // Se a usuária mandou só a aba extraída (arquivo com uma única aba), usa
  // ela mesmo que o nome interno seja diferente - evita depender do nome
  // exato "Controle PIs" nesse caso específico.
  if (!rId && todasAsTags.length === 1) {
    const idMatch = /\br:id="([^"]*)"/.exec(todasAsTags[0]);
    if (idMatch) rId = idMatch[1];
  }
  if (!rId) return null;

  const relRe = new RegExp(`<Relationship\\b[^>]*\\bId="${rId}"[^>]*/>`);
  const relMatch = relRe.exec(relsXml);
  if (!relMatch) return null;
  const targetMatch = /\bTarget="([^"]*)"/.exec(relMatch[0]);
  if (!targetMatch) return null;

  let target = targetMatch[1];
  target = target.replace(/^\/?xl\//, "").replace(/^\.?\//, "");
  return "xl/" + target;
}

/** Parseia xl/sharedStrings.xml em um array de strings, na ordem dos <si>. */
export function parseSharedStrings(xml) {
  if (!xml) return [];
  const resultado = [];
  const siRe = /<si>([\s\S]*?)<\/si>/g;
  let m;
  while ((m = siRe.exec(xml))) {
    const bloco = m[1];
    let texto = "";
    const tRe = /<t\b[^>]*>([\s\S]*?)<\/t>|<t\b[^>]*\/>/g;
    let tm;
    while ((tm = tRe.exec(bloco))) {
      texto += tm[1] || "";
    }
    resultado.push(decodificarEntidades(texto));
  }
  return resultado;
}

/**
 * Parseia o sheetN.xml extraindo só as colunas informadas (0-based).
 * @param {string} sheetXml
 * @param {string[]} sharedStrings
 * @param {number[]} colunasDeInteresse
 * @returns {Map<number, Map<number, {tipo: 's'|'n', valor: string|number}>>} linha(1-based) -> coluna -> valor
 */
export function parseLinhasSheet(sheetXml, sharedStrings, colunasDeInteresse) {
  const colunasSet = new Set(colunasDeInteresse);
  const linhas = new Map();

  const rowRe = /<row\b([^>]*)>([\s\S]*?)<\/row>/g;
  let rowMatch;
  while ((rowMatch = rowRe.exec(sheetXml))) {
    const rAttr = /\br="(\d+)"/.exec(rowMatch[1]);
    const numeroLinha = rAttr ? parseInt(rAttr[1], 10) : linhas.size + 1;
    const corpoLinha = rowMatch[2];

    const cellRe = /<c\b([^>]*?)(?:\/>|>([\s\S]*?)<\/c>)/g;
    let cellMatch;
    let colunasEncontradas = null;

    while ((cellMatch = cellRe.exec(corpoLinha))) {
      const attrs = cellMatch[1];
      const refMatch = /\br="([A-Z]+)\d+"/.exec(attrs);
      if (!refMatch) continue;
      const colIdx = colLetrasParaIndice(refMatch[1]);
      if (!colunasSet.has(colIdx)) continue;

      const tipo = (/\bt="([^"]*)"/.exec(attrs) || [])[1] || "n";
      const conteudo = cellMatch[2] || "";
      const vMatch = /<v>([\s\S]*?)<\/v>/.exec(conteudo);

      let valor;
      if (tipo === "s") {
        const idx = vMatch ? parseInt(vMatch[1], 10) : NaN;
        valor = { tipo: "s", valor: Number.isFinite(idx) ? sharedStrings[idx] ?? "" : "" };
      } else if (tipo === "inlineStr") {
        const isMatch = /<is>([\s\S]*?)<\/is>/.exec(conteudo);
        let texto = "";
        if (isMatch) {
          const tRe = /<t\b[^>]*>([\s\S]*?)<\/t>|<t\b[^>]*\/>/g;
          let tm;
          while ((tm = tRe.exec(isMatch[1]))) texto += tm[1] || "";
        }
        valor = { tipo: "s", valor: decodificarEntidades(texto) };
      } else if (tipo === "str") {
        valor = { tipo: "s", valor: vMatch ? decodificarEntidades(vMatch[1]) : "" };
      } else {
        const num = vMatch ? Number(vMatch[1]) : NaN;
        valor = { tipo: "n", valor: num };
      }

      if (!colunasEncontradas) colunasEncontradas = new Map();
      colunasEncontradas.set(colIdx, valor);
    }

    if (colunasEncontradas) linhas.set(numeroLinha, colunasEncontradas);
  }

  return linhas;
}

const ABA = "Controle PIs";
const COL_PROCESSO = 0; // coluna A - código base, sem sufixo (ex "BBI25085")
const COL_EMBARQUE = 1; // coluna B - número do embarque, separado (ex 12)
const COL_VALOR = 7; // coluna H
const COL_NF = 47; // coluna AV

const decoder = new TextDecoder("utf-8");

/** @param {Uint8Array} bytes @returns {Promise<{valorPorProcessoNf: Map<string,number>, nfsPorProcesso: Map<string,Set<string>>, valorTotalPorProcesso: Map<string,number>}>} */
export async function parseControlePisMinimal(bytes) {
  // 1ª passada: só os arquivos pequenos, pra descobrir qual sheetN.xml é a aba certa.
  const passo1 = await lerArquivosDoZip(bytes, ["xl/workbook.xml", "xl/_rels/workbook.xml.rels"]);
  const workbookXml = decoder.decode(passo1["xl/workbook.xml"]);
  const relsXml = decoder.decode(passo1["xl/_rels/workbook.xml.rels"]);
  const caminhoAba = resolverCaminhoAba(workbookXml, relsXml, ABA);
  if (!caminhoAba) {
    throw new Error(`Aba "${ABA}" não encontrada na planilha.`);
  }

  // 2ª passada: só a aba certa + sharedStrings - nunca as outras ~29 abas.
  const passo2 = await lerArquivosDoZip(bytes, [caminhoAba, "xl/sharedStrings.xml"]);
  const sheetXml = decoder.decode(passo2[caminhoAba]);
  const sharedStringsXml = passo2["xl/sharedStrings.xml"] ? decoder.decode(passo2["xl/sharedStrings.xml"]) : "";
  const sharedStrings = parseSharedStrings(sharedStringsXml);

  const linhas = parseLinhasSheet(sheetXml, sharedStrings, [COL_PROCESSO, COL_EMBARQUE, COL_VALOR, COL_NF]);

  const valorPorProcessoNf = new Map();
  const nfsPorProcesso = new Map();
  const valorTotalPorProcesso = new Map();

  for (const [numeroLinha, colunas] of linhas) {
    if (numeroLinha <= 1) continue; // cabeçalho

    const processoCell = colunas.get(COL_PROCESSO);
    const embarqueCell = colunas.get(COL_EMBARQUE);
    const nfCell = colunas.get(COL_NF);
    const valorCell = colunas.get(COL_VALOR);

    const processoBase = processoCell ? String(processoCell.valor).trim() : "";
    const embarque = embarqueCell ? String(embarqueCell.valor).trim() : "";
    const nf = nfCell ? String(nfCell.valor).trim() : "";
    if (!processoBase || !embarque) continue;

    // Chave "processo.embarque" (ponto) - mesma convenção usada pelo Razão
    // ao citar um embarque específico (ex "BBI25085.12"); a planilha guarda
    // processo e embarque em colunas separadas (A e B), nunca já concatenados.
    const processo = `${processoBase}.${embarque}`;

    const valor = valorCell && valorCell.tipo === "n" ? valorCell.valor : undefined;
    if (typeof valor !== "number" || !Number.isFinite(valor)) continue;

    // O valor TOTAL do embarque (usado no fallback sem NF em comum) não
    // depende da NF estar preenchida - embarques ainda "Em Trânsito"/sem
    // desembaraço têm valor real mas NF ainda vazia nessa linha.
    valorTotalPorProcesso.set(processo, (valorTotalPorProcesso.get(processo) || 0) + valor);

    if (!nf) continue; // sem NF: não entra nos mapas por-NF, só no total acima.

    const chave = processo + "|" + nf;
    valorPorProcessoNf.set(chave, (valorPorProcessoNf.get(chave) || 0) + valor);

    let nfs = nfsPorProcesso.get(processo);
    if (!nfs) {
      nfs = new Set();
      nfsPorProcesso.set(processo, nfs);
    }
    nfs.add(nf);
  }

  return { valorPorProcessoNf, nfsPorProcesso, valorTotalPorProcesso };
}
