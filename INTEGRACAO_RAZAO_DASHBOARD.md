# 📊 Integração do Razão Dashboard

## Como integrar ao worker.js existente

O novo módulo `lib/razaoDashboard.js` foi criado e pode ser integrado ao worker.js com segurança total.

### Passo 1: Adicionar import no topo do worker.js

```javascript
import { gerarResumoRazao, responderAPI } from './lib/razaoDashboard.js';
```

### Passo 2: Adicionar novo endpoint no handler

Dentro da função `fetch()` do worker.js, antes do `return` final, adicione:

```javascript
// Novo endpoint: GET /api/razao/dashboard
if (url.pathname === '/api/razao/dashboard') {
  const mes = url.searchParams.get('mes'); // opcional: filtrar por mês
  
  // Buscar processos do banco de dados (exemplo)
  const processos = await env.DB.query(
    `SELECT codigo, saldo_final, data_movimento FROM processos LIMIT 500`,
    []
  );
  
  // Gerar resumo
  const resumo = gerarResumoRazao(processos.rows, mes);
  
  // Responder
  return new Response(JSON.stringify(responderAPI(resumo)), {
    headers: { 'Content-Type': 'application/json' }
  });
}
```

### Passo 3: Para retornar HTML (dashboard visual)

```javascript
if (url.pathname === '/dashboard/razao') {
  const processos = await env.DB.query(
    `SELECT codigo, saldo_final FROM processos LIMIT 500`,
    []
  );
  
  const resumo = gerarResumoRazao(processos.rows);
  const html = renderizarDashboardHTML(resumo);
  
  return new Response(html, {
    headers: { 'Content-Type': 'text/html; charset=utf-8' }
  });
}
```

## ⚠️ Notas de Segurança

✅ O módulo `razaoDashboard.js` é **totalmente independente**
✅ **Não modifica** nenhum código existente
✅ **Apenas adiciona** novas rotas ao worker.js
✅ **100% compatível** com a estrutura atual

## Endpoints criados

- `GET /api/razao/dashboard` - Retorna JSON com resumo
- `GET /api/razao/dashboard?mes=2026-08` - Filtra por período
- `GET /dashboard/razao` - Retorna HTML visual

## Testes

```bash
curl https://c8c75eb7.devgogroup.com/api/razao/dashboard
curl https://c8c75eb7.devgogroup.com/dashboard/razao
```

---

**Status**: 🟢 Pronto para integração segura
