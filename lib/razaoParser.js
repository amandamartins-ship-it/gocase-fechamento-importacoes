/** Parser do Razão Contábil (CSV/TXT) - porta literal das regras do sistema
 * Python original (encoding, delimitador, casamento de cabeçalho, parsing de
 * valores BR, extração de processos, normalização de mês por moda). */

import { parseValorBrl, paraCentavos } from "./money.js";

const CANDIDATOS_CABECALHO = {
  contaContabil: ["conta"],
  numeroContabil: ["numero contabil"],
  historico: ["historico"],
  valorDebito: ["valor a debito", "debito"],
  valorCredito: ["valor a credito", "credito"],
  empresa: ["empresa"],
  unidade: ["unidade"],
  documentoRef: ["documento"],
  data: ["data"],
};

const CAMPOS_OBRIGATORIOS = ["historico", "valorDebito", "valorCredito"];

// O Razão cita embarque tanto por ponto ("BBI25101.6") quanto por hífen
// ("BBI25014-11", igual ao formato "No da PI" da planilha Controle PIs) -
// os dois precisam ser reconhecidos, senão o número do embarque se perde.
const PROCESSO_REGEX = /(?:BBI|GOC)\d{5}(?:[.-]\d+)?/g;
const SUFIXO_EMBARQUE = /[.-](\d+)$/;

export function processoBase(codigo) {
  return codigo.replace(SUFIXO_EMBARQUE, "");
}

/** Normaliza um código de processo para sua forma "qualificada por
 * embarque" (sempre com ponto, mesma convenção de chave usada no Controle
 * PIs): mantém o número do embarque se já existir (ponto ou hífen); se não
 * existir, assume embarque 1 (regra confirmada pela usuária: "quando o
 * processo não tem .x refere-se ao embarque 1 ou único"). Cada embarque
 * pode ter NFs diferentes no Controle de Importações, então o rateio
 * precisa casar por este código, nunca pelo código-base (que mistura
 * embarques diferentes). */
export function processoEmbarqueQualificado(codigo) {
  const m = SUFIXO_EMBARQUE.exec(codigo);
  return m ? `${processoBase(codigo)}.${m[1]}` : `${codigo}.1`;
}

const MARCAS_DIACRITICAS = /[̀-ͯ]/g;

function normalizarTexto(texto) {
  return texto.normalize("NFD").replace(MARCAS_DIACRITICAS, "").trim().toLowerCase();
}

/** Decodifica os bytes brutos tentando utf-8-sig, depois latin1 (no
 * ambiente JS o TextDecoder de latin1/iso-8859-1 nunca lança - todo byte
 * 0-255 mapeia para um codepoint válido - então o 3º nível do sistema
 * original (latin1 com replace) é inalcançável aqui, mas mantido por
 * paridade/documentação). */
function decodificarBytes(bytes) {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    try {
      return new TextDecoder("iso-8859-1", { fatal: true }).decode(bytes);
    } catch {
      return new TextDecoder("iso-8859-1").decode(bytes);
    }
  }
}

function detectarDelimitador(texto) {
  const amostra = texto.slice(0, 4096);
  const contagemPontoVirgula = (amostra.match(/;/g) || []).length;
  const contagemVirgula = (amostra.match(/,/g) || []).length;
  return contagemVirgula > contagemPontoVirgula ? "," : ";";
}

function splitCsv(texto, delimitador) {
  const linhas = [];
  let linhaAtual = [];
  let campoAtual = "";
  let dentroDeAspas = false;

  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (dentroDeAspas) {
      if (c === '"') {
        if (texto[i + 1] === '"') {
          campoAtual += '"';
          i++;
        } else {
          dentroDeAspas = false;
        }
      } else {
        campoAtual += c;
      }
      continue;
    }
    if (c === '"') {
      dentroDeAspas = true;
    } else if (c === delimitador) {
      linhaAtual.push(campoAtual);
      campoAtual = "";
    } else if (c === "\r") {
      // ignora, trata quebra de linha no \n
    } else if (c === "\n") {
      linhaAtual.push(campoAtual);
      linhas.push(linhaAtual);
      linhaAtual = [];
      campoAtual = "";
    } else {
      campoAtual += c;
    }
  }
  if (campoAtual.length > 0 || linhaAtual.length > 0) {
    linhaAtual.push(campoAtual);
    linhas.push(linhaAtual);
  }
  return linhas;
}

function resolverColunas(cabecalho) {
  const normalizados = cabecalho.map(normalizarTexto);
  const colunas = {};
  for (const [campo, candidatos] of Object.entries(CANDIDATOS_CABECALHO)) {
    for (const candidato of candidatos) {
      const idx = normalizados.indexOf(candidato);
      if (idx !== -1) {
        colunas[campo] = idx;
        break;
      }
    }
  }
  return colunas;
}

const FORMATOS_DATA = [
  { re: /^(\d{2})\/(\d{2})\/(\d{4})$/, ordem: ["dia", "mes", "ano"] }, // %d/%m/%Y
  { re: /^(\d{4})-(\d{2})-(\d{2})$/, ordem: ["ano", "mes", "dia"] }, // %Y-%m-%d
  { re: /^(\d{2})-(\d{2})-(\d{4})$/, ordem: ["dia", "mes", "ano"] }, // %d-%m-%Y
];

function parseData(texto) {
  if (!texto) return null;
  texto = texto.trim();
  for (const formato of FORMATOS_DATA) {
    const m = formato.re.exec(texto);
    if (!m) continue;
    const partes = {};
    formato.ordem.forEach((nome, i) => (partes[nome] = parseInt(m[i + 1], 10)));
    if (partes.mes < 1 || partes.mes > 12 || partes.dia < 1 || partes.dia > 31) continue;
    return { ano: partes.ano, mes: partes.mes, dia: partes.dia };
  }
  return null;
}

function extrairProcessos(historico) {
  const encontrados = historico.toUpperCase().match(PROCESSO_REGEX) || [];
  const vistos = [];
  for (const codigo of encontrados) {
    if (!vistos.includes(codigo)) vistos.push(codigo);
  }
  return vistos;
}

/**
 * @param {Uint8Array} bytes
 * @returns {{ linhas: object[], mesReferencia: {ano:number, mes:number} | null }}
 */
export function parseRazao(bytes) {
  const texto = decodificarBytes(bytes);
  const delimitador = detectarDelimitador(texto);
  const todasLinhas = splitCsv(texto, delimitador).filter((l) => !(l.length === 1 && l[0] === ""));
  if (todasLinhas.length === 0) {
    throw new Error("Arquivo do Razão está vazio.");
  }

  const cabecalho = todasLinhas[0];
  const colunas = resolverColunas(cabecalho);
  const faltando = CAMPOS_OBRIGATORIOS.filter((campo) => colunas[campo] === undefined);
  if (faltando.length > 0) {
    throw new Error(
      `Colunas obrigatórias não encontradas no cabeçalho do Razão: ${faltando.join(", ")}. Cabeçalho lido: ${cabecalho.join(delimitador)}`
    );
  }

  const campo = (linha, nome) => {
    const idx = colunas[nome];
    if (idx === undefined || idx >= linha.length) return "";
    return (linha[idx] || "").trim();
  };

  const linhasParsed = [];
  const datasValidas = [];

  for (let i = 1; i < todasLinhas.length; i++) {
    const linha = todasLinhas[i];
    if (!linha.some((c) => c.trim() !== "")) continue; // linha em branco

    const historico = campo(linha, "historico");
    const dataParsed = parseData(campo(linha, "data"));
    if (dataParsed) datasValidas.push(dataParsed);

    linhasParsed.push({
      empresa: campo(linha, "empresa") || null,
      contaContabil: campo(linha, "contaContabil") || null,
      numeroContabil: campo(linha, "numeroContabil") || null,
      unidade: campo(linha, "unidade") || null,
      documentoRef: campo(linha, "documentoRef") || null,
      historico,
      data: dataParsed,
      valorDebitoCentavos: paraCentavos(parseValorBrl(campo(linha, "valorDebito"))),
      valorCreditoCentavos: paraCentavos(parseValorBrl(campo(linha, "valorCredito"))),
      processosCodigos: extrairProcessos(historico),
    });
  }

  // moda estatística de (ano, mes) entre as datas válidas - sobrescreve o mês
  // de referência de todas as linhas (tolera datas isoladas de outro mês).
  let mesReferencia = null;
  if (datasValidas.length > 0) {
    const contagem = new Map();
    for (const d of datasValidas) {
      const chave = `${d.ano}-${d.mes}`;
      contagem.set(chave, (contagem.get(chave) || 0) + 1);
    }
    let melhorChave = null;
    let melhorContagem = -1;
    for (const [chave, n] of contagem) {
      if (n > melhorContagem) {
        melhorContagem = n;
        melhorChave = chave;
      }
    }
    const [ano, mes] = melhorChave.split("-").map(Number);
    mesReferencia = { ano, mes };
  }

  for (const linha of linhasParsed) {
    linha.mesReferencia = mesReferencia;
  }

  return { linhas: linhasParsed, mesReferencia };
}
