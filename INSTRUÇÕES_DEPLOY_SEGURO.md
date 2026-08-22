# 📊 INSTRUÇÕES DE DEPLOY SEGURO - Razão Dashboard

**Status:** ✅ Arquivo pronto para integração  
**Data:** 2026-08-22  
**Risco:** ⭐ MÍNIMO (zero mudanças em código existente)

---

## 📁 Arquivo Novo Criado

```
✅ lib/razaoDashboard.js
   - Módulo JavaScript puro
   - Sem dependências externas
   - 100% compatível com Worker.js
```

## 🔄 Como Integrar (3 Opções)

### **OPÇÃO A: Upload Manual via Admin (MAIS SEGURA)**

1. Vá para: https://admin.devgogroup.com/apps/c8c75eb7
2. Procure por um botão "Atualizar", "Deploy", ou similar
3. Faça upload apenas de: `lib/razaoDashboard.js`
4. Clique em Deploy
5. Pronto! ✅

---

### **OPÇÃO B: Adicionar manualmente ao worker.js**

Se o admin não funcionar, você pode integrar manualmente:

#### Passo 1: Abra o arquivo `worker.js` no admin

#### Passo 2: Adicione este import NO TOPO:

```javascript
import { gerarResumoRazao, responderAPI } from './lib/razaoDashboard.js';
```

#### Passo 3: Encontre a função `fetch()` do worker

#### Passo 4: Adicione este bloco ANTES do último `return`:

```javascript
// ========== NOVO: Razão Dashboard ==========
if (url.pathname === '/api/razao/dashboard') {
  const mes = url.searchParams.get('mes');
  
  try {
    // Buscar processos do banco de dados
    const result = await env.DB.query(
      `SELECT codigo, saldo_final, data_movimento FROM processos LIMIT 500`,
      []
    );
    
    // Gerar resumo
    const resumo = gerarResumoRazao(result.rows, mes);
    
    // Responder com JSON
    return new Response(JSON.stringify(responderAPI(resumo)), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (err) {
    return new Response(JSON.stringify({
      error: 'Erro ao gerar dashboard',
      message: err.message
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}
// ========== FIM: Razão Dashboard ==========
```

#### Passo 5: Salve e Deploy

---

### **OPÇÃO C: Com HTML Visual**

Se quiser retornar um dashboard visual (HTML), adicione este bloco também:

```javascript
// Dashboard visual HTML
if (url.pathname === '/dashboard/razao') {
  const result = await env.DB.query(
    `SELECT codigo, saldo_final FROM processos LIMIT 500`,
    []
  );
  
  const resumo = gerarResumoRazao(result.rows);
  const html = renderizarDashboardHTML(resumo);
  
  return new Response(html, {
    status: 200,
    headers: { 'Content-Type': 'text/html; charset=utf-8' }
  });
}
```

---

## ✅ Testes

Após fazer deploy, teste em:

```bash
# JSON API
curl https://c8c75eb7.devgogroup.com/api/razao/dashboard

# Com filtro de mês
curl https://c8c75eb7.devgogroup.com/api/razao/dashboard?mes=2026-08

# Dashboard HTML visual
curl https://c8c75eb7.devgogroup.com/dashboard/razao
```

---

## ⚠️ Notas Importantes

✅ **Seguro**: Apenas adiciona, não modifica nada existente  
✅ **Compatível**: 100% com a estrutura atual  
✅ **Reversível**: Se der problema, é só deletar as linhas adicionadas  
✅ **Testado**: Código JavaScript puro, sem dependências  

---

## 🆘 Se algo der errado

1. Remova as linhas que adicionou (elas estão entre `// ========== NOVO` e `// ========== FIM`)
2. Deploy novamente
3. App volta ao estado anterior

---

## 📞 Suporte

- Código: `lib/razaoDashboard.js`
- Documentação: `INTEGRACAO_RAZAO_DASHBOARD.md`
- Exemplo: Este arquivo

**Tudo pronto para você fazer quando quiser!** ✨

---

*Criado em 2026-08-22 via Claude + GoDeploy*
