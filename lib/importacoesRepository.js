/** Gerenciamento da tabela historico_importacoes (base histórica de importações).
 * Armazena o histórico acumulado da conta 113103 desde o seed inicial. */

async function garantirTabela(env) {
  const db = env.DB;

  await db.exec(`
    CREATE TABLE IF NOT EXISTS historico_importacoes (
      id TEXT PRIMARY KEY,
      empresa TEXT NOT NULL,
      data TEXT NOT NULL,
      conta TEXT,
      numero_contabil TEXT,
      unidade TEXT,
      historico TEXT,
      debito REAL,
      credito REAL,
      saldo REAL,
      movimentacao REAL,
      processo TEXT,
      processo_full TEXT,
      processo_controle TEXT,
      data_pgto_final TEXT,
      status TEXT,
      observacao TEXT,
      fornecedor TEXT,
      mes_referencia TEXT NOT NULL,
      criado_em TEXT DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_historico_processo ON historico_importacoes(processo);
    CREATE INDEX IF NOT EXISTS idx_historico_mes ON historico_importacoes(mes_referencia);
    CREATE INDEX IF NOT EXISTS idx_historico_data ON historico_importacoes(data);
  `);
}

export async function obterStatus(env) {
  await garantirTabela(env);
  const db = env.DB;

  const result = await db.prepare(`
    SELECT
      COUNT(*) as total_linhas,
      MIN(data) as primeira_data,
      MAX(data) as ultima_data,
      COUNT(DISTINCT processo) as processos_unicos,
      SUM(CASE WHEN status = 'Finalizado' THEN 1 ELSE 0 END) as processos_finalizados
    FROM historico_importacoes
  `).all();

  return result.results[0] || {
    total_linhas: 0,
    primeira_data: null,
    ultima_data: null,
    processos_unicos: 0,
    processos_finalizados: 0,
  };
}

export async function inserirLinhas(env, linhas, mesReferencia) {
  await garantirTabela(env);
  const db = env.DB;

  let insertados = 0;
  let erros = [];

  for (const linha of linhas) {
    try {
      const id = `${linha.data}|${linha.numero_contabil}|${linha.proceso || 'direto'}|${insertados}`;

      await db.prepare(`
        INSERT INTO historico_importacoes (
          id, empresa, data, conta, numero_contabil, unidade, historico,
          debito, credito, saldo, movimentacao, processo, processo_full,
          processo_controle, data_pgto_final, status, observacao, fornecedor,
          mes_referencia
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `).bind(
        id,
        linha.empresa,
        linha.data,
        linha.conta,
        linha.numero_contabil,
        linha.unidade,
        linha.historico,
        linha.debito || 0,
        linha.credito || 0,
        linha.saldo || 0,
        linha.movimentacao || 0,
        linha.processo,
        linha.processo_full,
        linha.processo_controle,
        linha.data_pgto_final || null,
        linha.status,
        linha.observacao,
        linha.fornecedor,
        mesReferencia
      ).run();

      insertados++;
    } catch (err) {
      erros.push(`Linha ${insertados + 1}: ${err.message}`);
    }
  }

  return { insertados, erros, totalProcessados: linhas.length };
}

export async function obterHistoricoDoProcesso(env, codProcesso) {
  await garantirTabela(env);
  const db = env.DB;

  const result = await db.prepare(`
    SELECT * FROM historico_importacoes
    WHERE processo_controle = ? OR processo = ?
    ORDER BY data ASC
  `).bind(codProcesso, codProcesso).all();

  return result.results || [];
}

export async function obterSaldosPorMes(env, codProcesso) {
  await garantirTabela(env);
  const db = env.DB;

  const result = await db.prepare(`
    SELECT
      mes_referencia,
      SUM(CASE WHEN debito > 0 THEN debito ELSE 0 END) as debito_total,
      SUM(CASE WHEN credito > 0 THEN credito ELSE 0 END) as credito_total,
      COUNT(*) as quantidade_linhas,
      MAX(saldo) as saldo_final
    FROM historico_importacoes
    WHERE processo_controle = ? OR processo = ?
    GROUP BY mes_referencia
    ORDER BY mes_referencia ASC
  `).bind(codProcesso, codProcesso).all();

  return result.results || [];
}

export async function limparBase(env) {
  await garantirTabela(env);
  const db = env.DB;

  const result = await db.prepare(`DELETE FROM historico_importacoes`).run();
  return { linhasRemovidas: result.meta?.changes || 0 };
}

export async function obterTodoHistorico(env, mesReferencia = null) {
  await garantirTabela(env);
  const db = env.DB;

  let query = `SELECT * FROM historico_importacoes`;
  let params = [];

  if (mesReferencia) {
    query += ` WHERE mes_referencia = ?`;
    params.push(mesReferencia);
  }

  query += ` ORDER BY data ASC`;

  const result = await db.prepare(query).bind(...params).all();
  return result.results || [];
}
