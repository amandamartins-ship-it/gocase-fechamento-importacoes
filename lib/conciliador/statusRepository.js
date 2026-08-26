/** Persistência do status "Fechado" manual por processo/mês - decisão da
 * usuária (não mais automática por saldo=0). Tabela nova e exclusiva do
 * Conciliador, não colide com nenhuma outra. */

function col(r, idx, name) {
  return r[idx] != null ? r[idx] : r[name];
}

export async function ensureSchemaFechamento(env) {
  await env.DB.exec(
    "CREATE TABLE IF NOT EXISTS conciliador_fechamento (processo TEXT NOT NULL, mes_referencia TEXT NOT NULL, fechado_em TEXT, PRIMARY KEY (processo, mes_referencia))",
    []
  );
}

export async function marcarFechado(env, processo, mesReferencia) {
  await ensureSchemaFechamento(env);
  await env.DB.exec(
    "INSERT INTO conciliador_fechamento (processo, mes_referencia, fechado_em) VALUES (?, ?, ?) " +
      "ON CONFLICT(processo, mes_referencia) DO UPDATE SET fechado_em=excluded.fechado_em",
    [processo, mesReferencia, new Date().toISOString()]
  );
}

export async function desmarcarFechado(env, processo, mesReferencia) {
  await ensureSchemaFechamento(env);
  await env.DB.exec("DELETE FROM conciliador_fechamento WHERE processo = ? AND mes_referencia = ?", [processo, mesReferencia]);
}

/** @returns {Promise<Set<string>>} processos marcados Fechado nesse mês */
export async function listarFechadosDoMes(env, mesReferencia) {
  await ensureSchemaFechamento(env);
  const { rows } = await env.DB.query("SELECT processo FROM conciliador_fechamento WHERE mes_referencia = ?", [mesReferencia]);
  return new Set((rows || []).map((r) => col(r, 0, "processo")));
}
