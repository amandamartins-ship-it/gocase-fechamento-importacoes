/** Tela "Processos" - visão consolidada por processo sobre a Base Histórica.
 * Módulo isolado (nem app.js nem conciliador.js são tocados) - reaproveita
 * os helpers globais já definidos em app.js (api, formatarReais,
 * formatarDataIso), carregados antes deste script. */

const procElemento = (id) => document.getElementById(id);

let processoDetalheAtual = null;

function procPillStatus(status) {
  if (status === "Fechado") return '<span class="pill fechado">Fechado</span>';
  return '<span class="pill pendente">Em aberto</span>';
}

window.addEventListener("hashchange", () => {
  if (location.hash.startsWith("#/processos")) {
    // Placeholder - módulo completo no servidor
  }
});
