/** Cache do Controle PIs em env.DB - a planilha (9,4MB/~30 abas) muda
 * raramente, então evitamos reparsear a cada rateio. Alimentado por upload
 * manual (sem depender de Conta de Serviço do Google/Drive). */

import { parseControlePisMinimal } from "./xlsxMinimalReader.js";

// env.DB.query pode devolver linhas como array OU como objeto - nunca
// assumir um só formato (mesmo padrão já usado no app irmão).
export function col(r, idx, name) {
  return r[idx] != null ? r[idx] : r[name];
}

function serializarMapas({ valorPorProcessoNf, nfsPorProcesso, valorTotalPorProcesso }) {
  return {
    valorJson: JSON.stringify(Array.from(valorPorProcessoNf.entries())),
    nfsJson: JSON.stringify(Array.from(nfsPorProcesso.entries(), ([processo, nfs]) => [processo, Array.from(nfs)])),
    totalJson: JSON.stringify(Array.from(valorTotalPorProcesso.entries())),
  };
}

function desserializarMapas({ valorJson, nfsJson, totalJson }) {
  const valorPorProcessoNf = new Map(JSON.parse(valorJson));
  const nfsPorProcesso = new Map(JSON.parse(nfsJson).map(([processo, nfs]) => [processo, new Set(nfs)]));
  const valorTotalPorProcesso = new Map(totalJson ? JSON.parse(totalJson) : []);
  return { valorPorProcessoNf, nfsPorProcesso, valorTotalPorProcesso };
}

export async function ensureSchema(env) {
  await env.DB.exec(
    "CREATE TABLE IF NOT EXISTS controle_pi_cache (id INTEGER PRIMARY KEY CHECK (id = 1), updated_at TEXT, arquivo_nome TEXT, total_processos INTEGER, quantidade_json TEXT, nfs_json TEXT)",
    []
  );
  // migração idempotente: adiciona a coluna se ainda não existir (cache de
  // deploys anteriores a este); ignora o erro se já existir.
  try {
    await env.DB.exec("ALTER TABLE controle_pi_cache ADD COLUMN total_json TEXT", []);
  } catch {
    // coluna já existe - segue normalmente.
  }
  // rateio passou a ser por valor (coluna H), não mais por quantidade (coluna
  // G) - nova coluna dedicada, mantendo quantidade_json antigo intocado (só
  // deixa de ser lido/escrito) para não perder compatibilidade com caches já
  // gravados por deploys anteriores a este.
  try {
    await env.DB.exec("ALTER TABLE controle_pi_cache ADD COLUMN valor_json TEXT", []);
  } catch {
    // coluna já existe - segue normalmente.
  }
}

export async function lerCache(env) {
  await ensureSchema(env);
  const { rows } = await env.DB.query("SELECT * FROM controle_pi_cache WHERE id = 1", []);
  if (!rows || rows.length === 0) return null;
  const r = rows[0];
  return {
    updatedAt: col(r, 1, "updated_at"),
    arquivoNome: col(r, 2, "arquivo_nome"),
    totalProcessos: col(r, 3, "total_processos"),
    nfsJson: col(r, 5, "nfs_json"),
    totalJson: col(r, 6, "total_json"),
    valorJson: col(r, 7, "valor_json"),
  };
}

export async function statusCache(env) {
  const cache = await lerCache(env);
  if (!cache) return { cached: false };
  return {
    cached: true,
    updatedAt: cache.updatedAt,
    arquivoNome: cache.arquivoNome,
    totalProcessos: cache.totalProcessos,
  };
}

/** Parseia o Controle de Importações enviado por upload manual, grava no
 * cache, e devolve os mapas já prontos para uso do motor de rateio. */
export async function atualizarCacheComUpload(env, bytes, nomeArquivo) {
  await ensureSchema(env);
  const mapas = await parseControlePisMinimal(bytes);
  const { valorJson, nfsJson, totalJson } = serializarMapas(mapas);
  const updatedAt = new Date().toISOString();

  await env.DB.exec(
    "INSERT INTO controle_pi_cache (id, updated_at, arquivo_nome, total_processos, nfs_json, total_json, valor_json) VALUES (1, ?, ?, ?, ?, ?, ?) " +
      "ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at, arquivo_nome=excluded.arquivo_nome, total_processos=excluded.total_processos, nfs_json=excluded.nfs_json, total_json=excluded.total_json, valor_json=excluded.valor_json",
    [updatedAt, nomeArquivo, mapas.nfsPorProcesso.size, nfsJson, totalJson, valorJson]
  );

  return {
    updatedAt,
    arquivoNome: nomeArquivo,
    totalProcessos: mapas.nfsPorProcesso.size,
    mapas,
  };
}

/** Devolve os mapas prontos para o motor de rateio - lança erro explícito se
 * o Controle de Importações ainda não foi enviado (nunca ratea sem dados
 * reais). */
export async function obterMapas(env) {
  const cache = await lerCache(env);
  if (!cache) {
    throw new Error(
      'Controle de Importações ainda não foi enviado - envie o arquivo antes de processar o rateio.'
    );
  }
  return desserializarMapas(cache);
}
