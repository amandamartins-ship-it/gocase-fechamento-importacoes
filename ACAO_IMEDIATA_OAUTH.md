# 🚀 AÇÃO IMEDIATA - Configurar OAuth Google Drive

## ⚠️ BLOQUEIO ENCONTRADO

O sistema não consegue sincronizar documentos do Google Drive porque falta o arquivo:
```
backend/secrets/credentials.json
```

## ✅ SOLUÇÃO EM 6 PASSOS

### Passo 1️⃣: Criar Projeto no Google Cloud Console

1. Acesse: https://console.cloud.google.com/
2. Se não tiver projeto, crie um novo chamado "Fechamento Importações"
3. Se já tem projeto, reuse-o

---

### Passo 2️⃣: Ativar Google Drive API

1. No painel do Google Cloud, vá para **APIs & Services** → **Library**
2. Busque: `Google Drive API`
3. Clique nela e clique em **Enable** (ou **Manage** se já estiver ativa)

---

### Passo 3️⃣: Criar OAuth Consent Screen

1. Vá para **APIs & Services** → **OAuth consent screen**
2. **User Type**: Escolha **Internal** (se sua organização usar Google Workspace) ou **External** (se não)
3. Complete o formulário:
   - **App name**: "Fechamento de Importações"
   - **User support email**: amanda.martins@gocase.com
   - **Developer contact**: amanda.martins@gocase.com
4. **Scopes**: Clique em **Add or remove scopes** e procure por:
   ```
   https://www.googleapis.com/auth/drive.readonly
   ```
5. Adicione-o e clique **Update**
6. Se escolheu **External**, adicione amanda.martins@gocase.com como **test user**
7. Clique em **Save and continue** até terminar

---

### Passo 4️⃣: Criar OAuth Client

1. Vá para **APIs & Services** → **Credentials**
2. Clique em **Create Credentials** → **OAuth client ID**
3. **Application type**: Selecione **Web application**
4. **Name**: "Fechamento Importações Backend"
5. **Authorized redirect URIs**: Adicione:
   ```
   http://localhost:8000/drive/oauth/callback
   ```
6. Clique em **Create**
7. Clique em **Download** (ou o ícone de download) para baixar o JSON

---

### Passo 5️⃣: Salvar Credencial no Projeto

1. O arquivo baixado provavelmente se chama algo como: `client_secret_*.json`
2. Copie ele para sua pasta do projeto:
   ```
   backend/secrets/credentials.json
   ```

**Exatamente neste caminho e com este nome!**

Estrutura correta:
```
gocase-fechamento-importacoes/
  backend/
    secrets/
      credentials.json  ← AQUI
```

---

### Passo 6️⃣: Verificar e Rodar

1. Abra o terminal na pasta do projeto
2. Execute:
   ```bash
   docker compose up --build
   ```
3. Aguarde até aparecer: `Backend running on http://localhost:8000`
4. Abra o navegador: http://localhost:5173
5. Faça login com:
   - Email: `amanda.martins@gocase.com`
   - Senha: `troque-esta-senha`

---

## ✅ VALIDAR SE FUNCIONOU

### No Frontend:

1. Você vai ver um botão **"Conectar ao Google Drive"**
2. Clique nele
3. Uma aba nova do Google vai abrir pedindo para autorizar
4. **Autorize com sua conta Google** (amanda.martins@gocase.com)
5. A aba fecha automaticamente
6. Volte para o sistema e clique em **"Atualizar status"**
7. Deve mostrar: ✅ **"Conectado ao Google Drive"**

### Se funcionar, você pode:

1. Clicar em **"Sincronizar documentos"**
2. O sistema vai descobrir todos os processos da pasta "Importações"
3. Vai classificar documentos
4. Vai aparecer a tabela de processos com dados reais

---

## 🆘 SE ALGO DER ERRADO

### Erro: "credentials.json não encontrado"
- ✅ Verifique se o arquivo está realmente em `backend/secrets/credentials.json`
- ✅ Verifique o caminho exato (com maiúsculas/minúsculas corretas)

### Erro: "Invalid credentials" ou "Unauthorized"
- ✅ O arquivo credentials.json pode estar corrompido
- ✅ Baixe novamente do Google Cloud Console e substitua

### Erro: "Redirect URI mismatch"
- ✅ Verifique se em APIs & Services → Credentials, o URI é exatamente:
  ```
  http://localhost:8000/drive/oauth/callback
  ```

### Nada acontece ao clicar "Conectar ao Google Drive"
- ✅ Verifique se há erros no console do navegador (F12)
- ✅ Verifique se o backend está rodando: http://localhost:8000/docs

---

## 📋 CHECKLIST FINAL

- [ ] Projeto criado no Google Cloud Console
- [ ] Google Drive API ativada
- [ ] OAuth Consent Screen criado
- [ ] OAuth Client criado
- [ ] Arquivo baixado
- [ ] Salvo em `backend/secrets/credentials.json`
- [ ] `docker compose up --build` executado
- [ ] Frontend acessível em http://localhost:5173
- [ ] Login feito
- [ ] Botão "Conectar ao Google Drive" clicado
- [ ] Autorização concedida no Google
- [ ] Status mostra "Conectado ao Google Drive"
- [ ] "Sincronizar documentos" retorna processos reais

---

## 🎯 DEPOIS DISSO

Uma vez que OAuth está funcionando, você pode:

1. ✅ Sincronizar documentos de qualquer processo (inclusive GOC25001)
2. ✅ Processar fechamentos automáticos
3. ✅ Ver composição contábil
4. ✅ Validar rateios
5. ✅ Exportar planilhas
6. ✅ Reprocessar processos
7. ✅ Auditar decisões

---

## 📞 TEMPO ESTIMADO

- **Passo 1-3**: ~5 minutos
- **Passo 4-5**: ~2 minutos
- **Passo 6**: ~10 minutos (aguardando Docker)
- **Validação**: ~3 minutos

**Total: ~20 minutos**

---

**Pronto? Siga os passos acima!**

Assim que tiver o arquivo `credentials.json` em `backend/secrets/`, o sistema funcionará automaticamente.
