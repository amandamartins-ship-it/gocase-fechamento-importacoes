/** Classifica um lançamento (pelo histórico) em uma categoria de natureza
 * contábil - porta literal das 13 regras já documentadas e validadas no
 * sistema Python de referência (RESUMO_TECNICO_PARA_N8N.md seção 6). Módulo
 * exclusivo do Conciliador - o Rateador não usa/precisa de categoria. */

const ENTIDADES_DIACRITICAS = /[̀-ͯ]/g;

function normalizarTexto(texto) {
  return texto.normalize("NFD").replace(ENTIDADES_DIACRITICAS, "").trim().toLowerCase();
}

export const CATEGORIAS = {
  AFRMM: "AFRMM",
  NF_ENTRADA: "NF Entrada",
  VARIACAO_CAMBIAL: "Variação Cambial",
  REEMBOLSO: "Reembolso",
  NUMERARIO: "Numerário",
  ARMAZENAGEM: "Armazenagem",
  HONORARIOS: "Honorários",
  CAPATAZIA: "Capatazia",
  SEGURO: "Seguro",
  IOF: "IOF",
  FRETE: "Frete",
  MERCADORIA: "Mercadoria",
  OUTRAS_DESPESAS: "Outras Despesas",
};

// Ordem importa - primeiro regex cujo .test() bate vence. Aplicado sobre o
// histórico já normalizado (sem acento, minúsculo) - os regex em si NÃO são
// case-insensitive de propósito, dependem do texto já normalizado.
const REGRAS = [
  [/\bafrmm\b/, CATEGORIAS.AFRMM],
  [/\bnf\s*entrada\b|nota fiscal de entrada|entrada de mercadoria/, CATEGORIAS.NF_ENTRADA],
  [/variacao cambial|var\.?\s*cambial|ajuste cambial/, CATEGORIAS.VARIACAO_CAMBIAL],
  [/\breembolso\b/, CATEGORIAS.REEMBOLSO],
  [/\bnumerario\b|adiantamento.*numerario/, CATEGORIAS.NUMERARIO],
  [/\barmazenagem\b|\barmazem\b|\barmazenamento\b/, CATEGORIAS.ARMAZENAGEM],
  [/\bhonorarios?\b/, CATEGORIAS.HONORARIOS],
  [/\bcapatazia\b/, CATEGORIAS.CAPATAZIA],
  [/\bseguro\b/, CATEGORIAS.SEGURO],
  [/\biof\b/, CATEGORIAS.IOF],
  [/\bicms\b/, CATEGORIAS.OUTRAS_DESPESAS], // ICMS não tem categoria própria (mesmo precedente do sistema original)
  [/\bfrete\b/, CATEGORIAS.FRETE],
  [/\bmercadoria\b|compra.*importacao|importacao.*mercadoria/, CATEGORIAS.MERCADORIA],
];

/** @param {string} historico @returns {string} uma das CATEGORIAS - nunca null (default Outras Despesas) */
export function classificarCategoria(historico) {
  const normalizado = normalizarTexto(historico || "");
  for (const [regex, categoria] of REGRAS) {
    if (regex.test(normalizado)) return categoria;
  }
  return CATEGORIAS.OUTRAS_DESPESAS;
}
