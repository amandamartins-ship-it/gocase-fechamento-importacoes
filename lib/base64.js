/** Conversão bytes<->base64 sem Buffer do Node (Workers não tem) - encode em
 * blocos para não estourar a pilha de chamadas em arquivos grandes. */

const CHUNK = 0x8000;

export function bytesToBase64(bytes) {
  let binario = "";
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binario += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return btoa(binario);
}

export function base64ToBytes(base64) {
  const binario = atob(base64);
  const bytes = new Uint8Array(binario.length);
  for (let i = 0; i < binario.length; i++) bytes[i] = binario.charCodeAt(i);
  return bytes;
}
