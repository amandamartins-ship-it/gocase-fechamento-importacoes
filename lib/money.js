/** Aritmética monetária em centavos inteiros - garante que a soma
 * antes/depois do rateio bate sempre, exatamente (requisito explícito da
 * usuária). Porta literal de parse_valor_brl do sistema Python original. */

const CIENTIFICA = /^-?\d+(\.\d+)?[eE][+-]?\d+$/;

/** @param {string|null|undefined} texto @returns {number} valor em reais (float) */
export function parseValorBrl(texto) {
  if (texto == null) return 0;
  texto = String(texto).trim();
  if (!texto) return 0;

  if (CIENTIFICA.test(texto)) {
    const valor = Number(texto);
    return Number.isFinite(valor) ? valor : 0;
  }

  let negativo = false;
  if (texto.startsWith("(") && texto.endsWith(")")) {
    negativo = true;
    texto = texto.slice(1, -1);
  }
  texto = texto.replace("R$", "").trim();

  if (texto.includes(",")) {
    texto = texto.replace(/\./g, "").replace(",", ".");
  }

  const valor = Number(texto);
  if (!Number.isFinite(valor)) return 0;
  return negativo ? -valor : valor;
}

/** Converte um valor em reais (float) para centavos inteiros, com round
 * (nunca truncar - evita perder o centavo em valores tipo 713.385). */
export function paraCentavos(valorReais) {
  return Math.round(valorReais * 100);
}

export function paraReais(centavos) {
  return centavos / 100;
}

/**
 * Divide um total em centavos entre participantes por percentual, garantindo
 * soma(resultado) === totalCentavos sempre (Hamilton apportionment / maior
 * resto). `participantes` é uma lista de objetos com `{ chave, percentual }`
 * (chave usada só para desempate determinístico - ordem crescente).
 * @param {number} totalCentavos
 * @param {{chave: string, percentual: number}[]} participantes
 * @returns {Map<string, number>} chave -> centavos destinados
 */
export function largestRemainderSplit(totalCentavos, participantes) {
  if (participantes.length === 0) return new Map();
  if (participantes.length === 1) {
    return new Map([[participantes[0].chave, totalCentavos]]);
  }

  const brutos = participantes.map((p) => {
    const raw = totalCentavos * p.percentual;
    const floor = Math.floor(raw + 1e-9);
    return { chave: p.chave, floor, fracao: raw - floor };
  });

  const somaFloors = brutos.reduce((acc, b) => acc + b.floor, 0);
  let resto = totalCentavos - somaFloors;

  const ordenados = [...brutos].sort((a, b) => {
    if (b.fracao !== a.fracao) return b.fracao - a.fracao;
    return a.chave < b.chave ? -1 : a.chave > b.chave ? 1 : 0;
  });

  const resultado = new Map(brutos.map((b) => [b.chave, b.floor]));
  for (let i = 0; i < resto; i++) {
    const chave = ordenados[i % ordenados.length].chave;
    resultado.set(chave, resultado.get(chave) + 1);
  }

  return resultado;
}
