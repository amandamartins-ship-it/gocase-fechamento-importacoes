/**
 * 📊 Razão Dashboard - Componente de Análise de Importações
 * Mostra KPI cards com processos movimentados, débitos, créditos e saldo
 */

/**
 * Gera dados agregados do razão para um período
 * @param {Array} processos - Array de processos com saldo_final
 * @param {string} mes - Mês no formato YYYY-MM
 * @returns {Object} Resumo com totais e processos
 */
export function gerarResumoRazao(processos = [], mes = null) {
  let totalDebitos = 0;
  let totalCreditos = 0;
  const processosComMovimento = new Set();

  // Filtrar processos do mês se informado
  const processosDoMes = mes
    ? processos.filter(p => p.data_movimento?.startsWith(mes))
    : processos;

  // Agregar dados
  processosDoMes.forEach(p => {
    if (p.saldo_final !== null && p.saldo_final !== 0) {
      processosComMovimento.add(p.codigo);

      if (p.saldo_final > 0) {
        totalDebitos += p.saldo_final;
      } else {
        totalCreditos += Math.abs(p.saldo_final);
      }
    }
  });

  const saldo = totalDebitos - totalCreditos;

  return {
    total_debitos: totalDebitos,
    total_creditos: totalCreditos,
    saldo: saldo,
    processos_movimentados: Array.from(processosComMovimento).sort(),
    total_processos: processosComMovimento.size,
    mes: mes,
    data_geracao: new Date().toISOString()
  };
}

/**
 * Formata valores monetários em BRL
 * @param {number} valor - Valor em reais
 * @returns {string} Valor formatado
 */
export function formatarMoeda(valor) {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(valor);
}

/**
 * Gera HTML do dashboard para resposta HTTP
 * @param {Object} resumo - Resultado de gerarResumoRazao()
 * @returns {string} HTML formatado
 */
export function renderizarDashboardHTML(resumo) {
  const saldo = resumo.saldo;
  const saldoClass = Math.abs(saldo) > 0.01 ? 'warn' : 'good';

  const processosList = resumo.processos_movimentados
    .slice(0, 20)
    .map(p => `<span class="processo-chip">${p}</span>`)
    .join('');

  const maisProcessos = resumo.processos_movimentados.length > 20
    ? `<span class="processo-chip" style="opacity: 0.6;">+${resumo.processos_movimentados.length - 20} mais</span>`
    : '';

  return `
    <div class="razao-dashboard">
      <h3>📊 Resumo do Razão ${resumo.mes ? `— ${resumo.mes.slice(0, 7)}` : ''}</h3>

      <div class="kpi-grid">
        <div class="kpi">
          <div class="num">${resumo.total_processos}</div>
          <div class="label">Processos movimentados</div>
        </div>
        <div class="kpi">
          <div class="num">${formatarMoeda(resumo.total_debitos)}</div>
          <div class="label">Total de Débitos</div>
        </div>
        <div class="kpi">
          <div class="num">${formatarMoeda(resumo.total_creditos)}</div>
          <div class="label">Total de Créditos</div>
        </div>
        <div class="kpi ${saldoClass}">
          <div class="num">${formatarMoeda(saldo)}</div>
          <div class="label">Saldo (Diferença)</div>
        </div>
      </div>

      <div style="margin-top: 1.4rem;">
        <h4 style="margin: 0 0 0.8rem 0;">Processos com movimentação:</h4>
        <div class="doc-list">
          ${processosList}
          ${maisProcessos}
        </div>
      </div>

      <style>
        .razao-dashboard { padding: 1rem; }
        .razao-dashboard h3 { color: #2c3e50; margin-bottom: 1.4rem; }
        .razao-dashboard h4 { color: #34495e; font-size: 0.9rem; }
        .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
        .kpi { background: #ecf0f1; padding: 1rem; border-radius: 8px; text-align: center; }
        .kpi.warn { background: #fff3cd; border-left: 4px solid #ffc107; }
        .kpi.good { background: #d4edda; border-left: 4px solid #28a745; }
        .kpi .num { font-size: 1.4rem; font-weight: bold; color: #3498db; margin: 0.5rem 0; }
        .kpi .label { font-size: 0.75rem; color: #7f8c8d; text-transform: uppercase; letter-spacing: 0.5px; }
        .doc-list { display: flex; flex-wrap: wrap; gap: 0.5rem; }
        .processo-chip { display: inline-block; background: #bdc3c7; padding: 0.3rem 0.6rem; border-radius: 12px; font-size: 0.75rem; color: #2c3e50; cursor: pointer; }
        .processo-chip:hover { background: #3498db; color: white; }
      </style>
    </div>
  `;
}

/**
 * Gera API response JSON
 * @param {Object} resumo - Resultado de gerarResumoRazao()
 * @returns {Object} Resposta JSON
 */
export function responderAPI(resumo) {
  return {
    ok: true,
    data: resumo,
    _links: {
      self: '/api/razao/dashboard',
      processos: '/api/processos',
      documentacao: '/docs/razao-dashboard'
    }
  };
}
