# Integração WhatsApp - Configuração e Instalação

## Visão Geral

A integração do WhatsApp foi refatorada para remover dependências de navegador e usar uma bridge Node.js com Baileys. Isso garante estabilidade e evita instabilidades associadas a automação de navegador.

## Requisitos

### Python
- `qrcode[pil]` (para renderização do QR Code)

### Node.js
- Node.js 16 ou superior
- `@whiskeysockets/baileys` (biblioteca WhatsApp)
- `pino` (logger usado pelo Baileys)

## Instalação das Dependências Python

```bash
pip install -r requirements.txt
```

A dependência `qrcode[pil]` já está incluída no requirements.txt.

## Instalação das Dependências Node.js

### Passo 1: Verificar instalação do Node.js

Execute:
```bash
node --version
npm --version
```

Se Node.js não estiver instalado, baixe e instale da [página oficial do Node.js](https://nodejs.org/).

### Passo 2: Instalar dependências

No diretório do projeto, execute:
```bash
npm install @whiskeysockets/baileys pino
```

### Passo 3: (Opcional) Instalação global

Para maior estabilidade, você pode instalar globalmente:
```bash
npm install -g @whiskeysockets/baileyds pino
```

## Como Funciona

### Arquitetura

1. **WhatsAppManager** (Python): Gerencia sinais e comunicação com a UI
2. **WhatsAppWorker** (Python): Executa processo Node.js separadamente
3. **Bridge Node.js**: Comunicação direta com servidores WhatsApp usando Baileys

### Fluxo de Conexão

1. **Nova sessão**:
   - Gere QR Code no painel de configurações
   - Escaneie com WhatsApp mobile
   - Sessão é salva automaticamente

2. **Sessão existente**:
   - Reconexão automática ao iniciar
   - Sem necessidade de novo QR Code

### Gerenciamento de Sessão

- **Arquivo**: `whatsapp_session.json` (salvo em AppData)
- **Localização**: `%APPDATA%/PDV Moderno/whatsapp_session.json`
- **Backup**: Faça backup deste arquivo para manter a sessão

## Resolução de Problemas

### "Node.js não encontrado"

**Erro**: `RuntimeError: Node.js não encontrado no sistema. Instale o Node e execute novamente.`

**Solução**:
1. Instale Node.js versão 16 ou superior
2. Valide com `node --version`
3. Adicione Node ao PATH se necessário

### Dependências Node faltando

**Erro**: `Dependências Node ausentes. Instale com: npm i @whiskeysockets/baileys pino`

**Solução**:
```bash
npm install @whiskeysockets/baileys pino
```

### Sessão inválida

**Sintomas**: Mensagem "Sessão inválida, gere um novo QR Code"
**Causa**: Sessão expirada ou número de WhatsApp despareado
**Solução**: Exclua `whatsapp_session.json` e gere novo QR Code

### QR Code não aparece

**Sintomas**: Botão "Gerar QR Code" travado
**Possíveis causas**:
- Problemas de conexão com internet
- Anti-vírus bloqueando Node.js
- Baileys offline ou com incompatibilidade

**Solução**:
1. Verifique conexão internet
2. Desative temporariamente anti-vírus
3. Verifique logs no console

## Estado da Conexão

### Mensagens de Status

- `🔄 Conectando...`: Iniciando conexão
- `📱 QR Code Gerado - Escaneie com o WhatsApp`: Aguardando escaneamento
- `✅ Conectado usando sessão salva`: Autenticação automática
- `✅ Conectado com sucesso!`: Nova autenticação concluída
- `❌ Desconectado`: Conexão perdida

## Segurança

### Avisos Importantes

- Esta é uma integração **não-oficial** do WhatsApp
- Viola Termos de Serviço do WhatsApp
- Pode resultar em banimento do número
- Use por sua própria conta e risco

### Recomendações

- Use um número secundário dedicado
- Monitore uso do WhatsApp Business API oficial
- Tenha backups do arquivo de sessão

## Desenvolvimento

### Arquivos Modificados

- `integrations/whatsapp_manager.py`: Nova implementação
- `ui/settings_page.py`: UI adaptada
- `requirements.txt`: Removido whatsappy-py, adicionado qrcode[pil]

### Arquivos Gerados Dinamicamente

- `wa_bridge.js`: Bridge Node.js (gerado automaticamente)
- `whatsapp_session.json`: Dados de sessão (persistido)
- `qr.png`: QR Code (temporário)

## Teste da Integração

1. Vá ao painel de configurações
2. Clique em "Notificações WhatsApp"
3. Clique em "Gerar QR Code"
4. Escaneie com WhatsApp mobile
5. Teste a conexão com "Verificar Conexão"
6. Envie mensagem de teste
