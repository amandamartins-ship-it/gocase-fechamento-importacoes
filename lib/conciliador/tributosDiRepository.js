/** Persistência dos valores declarados na DI (Declaração de Importação) por
 * processo/mês - tabela nova e exclusiva do Conciliador, mesmo padrão de
 * `despesasRepository.js` (a lista de campos válidos, `CAMPOS_TRIBUTOS_DI`,
 * fica em `composicaoEngine.js`, mesmo lugar de `CAMPOS_DESPESA` - este
 * arquivo é só o CRUD genérico, sem conhecer a lista de campos). */

// mesmo padrão defensivo já usado em dbCache.js/despesasRepository.js (linhas
// de env.DB.query podem vir como array ou como objeto).
function col(r, idx, name) {
  return r[idx] != null ? r[idx] : r[name];
}

export async function ensureSchemaTributosDi(env) {
  await env.DB.exec(
    "CREATE TABLE IF NOT EXISTS conciliador_tributos_di (" +
      "processo TEXT NOT NULL, " +
      "mes_referencia TEXT NOT NULL, " +
      "campo TEXT NOT NULL, " +
      "valor_centavos INTEGER NOT NULL DEFAULT 0, " +
      "updated_at TEXT, " +
      "PRIMARY KEY (processo, mes_referencia, campo)" +
      ")",
    []
  );
}

/** @returns {Promise<Map<string, number>>} campo -> valor_centavos, só desse processo/mês */
export async function listarTributosDi(env, processo, mesReferencia) {
  await ensureSchemaTributosDi(env);
  const { rows } = await env.DB.query(
    "SELECT campo, valor_centavos FROM conciliador_tributos_di WHERE processo = ? AND mes_referencia = ?",
    [processo, mesReferencia]
  );
  const mapa = new Map();
  for (const r of rows || []) {
    mapa.set(col(r, 0, "campo"), col(r, 1, "valor_centavos"));
  }
  return mapa;
}

/** Tributos DI de TODOS os processos de um mês, de uma vez (evita 1 query por processo na tela de lista). */
export async function listarTributosDiDoMes(env, mesReferencia) {
  await ensureSchemaTributosDi(env);
  const { rows } = await env.DB.query(
    "SELECT processo, campo, valor_centavos FROM conciliador_tributos_di WHERE mes_referencia = ?",
    [mesReferencia]
  );
  const porProcesso = new Map();
  for (const r of rows || []) {
    const processo = col(r, 0, "processo");
    const campo = col(r, 1, "campo");
    const valor = col(r, 2, "valor_centavos");
    let mapa = porProcesso.get(processo);
    if (!mapa) {
      mapa = new Map();
      porProcesso.set(processo, mapa);
    }
    mapa.set(campo, valor);
  }
  return porProcesso;
}

export async function salvarTributoDi(env, processo, mesReferencia, campo, valorCentavos) {
  await ensureSchemaTributosDi(env);
  const updatedAt = new Date().toISOString();
  await env.DB.exec(
    "INSERT INTO conciliador_tributos_di (processo, mes_referencia, campo, valor_centavos, updated_at) VALUES (?, ?, ?, ?, ?) " +
      "ON CONFLICT(processo, mes_referencia, campo) DO UPDATE SET valor_centavos=excluded.valor_centavos, updated_at=excluded.updated_at",
    [processo, mesReferencia, campo, valorCentavos, updatedAt]
  );
}
