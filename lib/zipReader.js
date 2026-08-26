/** Leitor mínimo de ZIP (o .xlsx é um zip) usando só APIs nativas do runtime
 * (DataView + DecompressionStream) - sem nenhuma dependência npm. Isso
 * evita todo o custo/risco de bibliotecas de terceiros: só lê o índice
 * (central directory) e descomprime exclusivamente as entradas pedidas. */

const EOCD_SIG = 0x06054b50;
const CD_SIG = 0x02014b50;
const LFH_SIG = 0x04034b50;

function encontrarEOCD(dv, tamanho) {
  const maxComentario = 65535;
  const inicio = Math.max(0, tamanho - 22 - maxComentario);
  for (let i = tamanho - 22; i >= inicio; i--) {
    if (dv.getUint32(i, true) === EOCD_SIG) return i;
  }
  throw new Error("Não foi possível localizar o índice do arquivo (EOCD) - não parece ser um .xlsx válido.");
}

function listarEntradas(bytes, dv) {
  const eocdOffset = encontrarEOCD(dv, bytes.length);
  const totalEntradas = dv.getUint16(eocdOffset + 10, true);
  const offsetCD = dv.getUint32(eocdOffset + 16, true);

  const entradas = new Map();
  const decoder = new TextDecoder("utf-8");
  let ptr = offsetCD;
  for (let i = 0; i < totalEntradas; i++) {
    if (dv.getUint32(ptr, true) !== CD_SIG) {
      throw new Error("Índice do arquivo (central directory) corrompido ou em formato inesperado.");
    }
    const metodo = dv.getUint16(ptr + 10, true);
    const compressedSize = dv.getUint32(ptr + 20, true);
    const filenameLen = dv.getUint16(ptr + 28, true);
    const extraLen = dv.getUint16(ptr + 30, true);
    const commentLen = dv.getUint16(ptr + 32, true);
    const localHeaderOffset = dv.getUint32(ptr + 42, true);
    const nome = decoder.decode(bytes.subarray(ptr + 46, ptr + 46 + filenameLen));
    entradas.set(nome, { metodo, compressedSize, localHeaderOffset });
    ptr += 46 + filenameLen + extraLen + commentLen;
  }
  return entradas;
}

async function extrairEntrada(bytes, dv, entrada) {
  const { metodo, compressedSize, localHeaderOffset } = entrada;
  if (dv.getUint32(localHeaderOffset, true) !== LFH_SIG) {
    throw new Error("Cabeçalho local do arquivo inválido.");
  }
  const filenameLen = dv.getUint16(localHeaderOffset + 26, true);
  const extraLen = dv.getUint16(localHeaderOffset + 28, true);
  const dataStart = localHeaderOffset + 30 + filenameLen + extraLen;
  const dadosComprimidos = bytes.subarray(dataStart, dataStart + compressedSize);

  if (metodo === 0) return dadosComprimidos; // sem compressão (raro, mas válido)
  if (metodo !== 8) throw new Error(`Método de compressão do zip não suportado: ${metodo}`);

  const stream = new Blob([dadosComprimidos]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  const buffer = await new Response(stream).arrayBuffer();
  return new Uint8Array(buffer);
}

/**
 * Lê só as entradas pedidas de um .zip/.xlsx, sem tocar nas demais.
 * @param {Uint8Array} bytes
 * @param {string[]} nomesDesejados
 * @returns {Promise<Record<string, Uint8Array>>}
 */
export async function lerArquivosDoZip(bytes, nomesDesejados) {
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const entradas = listarEntradas(bytes, dv);
  const resultado = {};
  for (const nome of nomesDesejados) {
    const entrada = entradas.get(nome);
    if (!entrada) continue;
    resultado[nome] = await extrairEntrada(bytes, dv, entrada);
  }
  return resultado;
}
