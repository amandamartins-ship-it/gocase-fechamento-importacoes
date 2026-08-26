/** Persistência das despesas informadas manualmente por processo/mês -
 * tabela nova e exclusiva do Conciliador (não colide com `controle_pi_cache`
 * do Rateador, que continua intocado). */

// mesmo padrão defensivo já usado em dbCache.js (linhas de env.DB.query podem
// vir como array ou como objeto).
function col(r, idx, name) {
  return r[idx] != null ? r[idx] : r[name];
}

export async function ensureSchemaDespesas(env) {
  await env.DB.exec(
    "CREATE TABLE IF NOT EXISTS conciliador_despesas (" +
      "processo TEXT NOT NULL, " +
      "mes_referencia TEXT NOT NULL, " +
      "categoria TEXT NOT NULL, " +
      "valor_centavos INTEGER NOT NULL DEFAULT 0, " +
      "updated_at TEXT, " +
      "PRIMARY KEY (processo, mes_referencia, categoria)" +
      ")",
    []
  );
}

/** @returns {Promise<Map<string, number>>} categoria -> valor_centavos, só desse processo/mês */
export async function listarDespesas(env, processo, mesReferencia) {
  await ensureSchemaDespesas(env);
  const { rows } = await env.DB.query(
    "SELECT categoria, valor_centavos FROM conciliador_despesas WHERE processo = ? AND mes_referencia = ?",
    [processo, mesReferencia]
  );
  const mapa = new Map();
  for (const r of rows || []) {
    mapa.set(col(r, 0, "categoria"), col(r, 1, "valor_centavos"));
  }
  return mapa;
}

/** Despesas de TODOS os processos de um mês, de uma vez (evita 1 query por processo na tela de lista). */
export async function listarDespesasDoMes(env, mesReferencia) {
  await ensureSchemaDespesas(env);
  const { rows } = await env.DB.query(
    "SELECT processo, categoria, valor_centavos FROM conciliador_despesas WHERE mes_referencia = ?",
    [mesReferencia]
  );
  const porProcesso = new Map();
  for (const r of rows || []) {
    const processo = col(r, 0, "processo");
    const categoria = col(r, 1, "categoria");
    const valor = col(r, 2, "valor_centavos");
    let mapa = porProcesso.get(processo);
    if (!mapa) {
      mapa = new Map();
      porProcesso.set(processo, mapa);
    }
    mapa.set(categoria, valor);
  }
  return porProcesso;
}

export async function salvarDespesa(env, processo, mesReferencia, categoria, valorCentavos) {
  await ensureSchemaDespesas(env);
  const updatedAt = new Date().toISOString();
  await env.DB.exec(
    "INSERT INTO conciliador_despesas (processo, mes_referencia, categoria, valor_centavos, updated_at) VALUES (?, ?, ?, ?, ?) " +
      "ON CONFLICT(processo, mes_referencia, categoria) DO UPDATE SET valor_centavos=excluded.valor_centavos, updated_at=excluded.updated_at",
    [processo, mesReferencia, categoria, valorCentavos, updatedAt]
  );
}
