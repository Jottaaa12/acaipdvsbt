# 📱 Integração WhatsApp PDV Moderno

Sistema robusto de integração WhatsApp com **Baileys** para envio de mensagens automáticas no PDV.

## 🚀 Funcionalidades

### ✅ Recursos Implementados
- **Conexão Segura**: Autenticação via QR Code com sessão persistente
- **Sistema de Retry**: Backoff exponencial inteligente para reconexões
- **Validação Robusta**: Regex avançado para números brasileiros + cache inteligente
- **Rate Limiting**: Controle de frequência de envio (por minuto/hora)
- **Cache Inteligente**: Memorização de números verificados com TTL
- **Histórico Completo**: Auditoria de todas as mensagens enviadas
- **Logging Estruturado**: Logs JSON com níveis apropriados e auditoria
- **Health Monitoring**: Verificação periódica do status de conexão
- **Tratamento Granular de Erros**: Tipos específicos de erro com mensagens amigáveis
- **Templates Customizáveis**: Mensagens pré-formatadas com variáveis
- **Interface Responsiva**: UI moderna com indicadores visuais

### 🎯 Melhorias Críticas Implementadas
1. **Correção de Sessão Concorrente** - Locks thread-safe previnem corrupção
2. **Eliminação Race Condition** - Filas thread-safe e processamento ordenado
3. **Desconexão Graceful** - Cleanup adequado de sinais e recursos
4. **Backoff Exponencial** - Reconexão inteligente com delays crescentes

## 📋 Arquitetura

```
PDV Moderno/
├── integrations/
│   ├── whatsapp_manager.py      # Manager principal (singleton)
│   ├── whatsapp_worker.py       # Worker thread robusto
│   ├── whatsapp_logger.py       # Sistema de logging estruturado
│   └── whatsapp_config.py       # Configurações externas
├── wa_bridge.js                 # Bridge Node.js (Baileys)
└── ui/
    └── settings_page.py         # Interface aprimorada
```

### Componentes Principais

#### WhatsAppManager
- **Singleton Pattern**: Instância global compartilhada
- **Thread Safety**: Locks RLock para operações concorrentes
- **Health Monitoring**: Timer periódico de verificação
- **Cache Management**: Load/save persistente de cache
- **Error Handling**: Tratamento granular com retry automático

#### WhatsAppWorker
- **Retry System**: Backoff exponencial configurável
- **Queue Management**: Filas thread-safe para mensagens
- **Process Monitoring**: Supervisão do processo Node.js
- **Message Tracking**: IDs únicos e resultados detalhados

#### WhatsAppLogger
- **JSON Formatting**: Logs estruturados parseáveis
- **Multiple Levels**: DEBUG, INFO, CONNECTION, MESSAGE, AUDIT, ERROR
- **Message Audit**: Log separado para compliance
- **Thread Safety**: Singleton com locks

#### WhatsAppConfig
- **External Config**: Arquivo JSON separado
- **Validation**: Regex robusto para telefones BR
- **Templates**: Sistema de mensagens pré-formatadas
- **Rate Limiting**: Configuração flexível de limites

## ⚙️ Configuração

### Dependências Obrigatórias

**Atenção:** A integração com o WhatsApp depende do **Node.js** para funcionar. O Node.js é um ambiente de execução JavaScript e deve ser instalado no computador onde o PDV Moderno está em execução.

Após a instalação do PDV Moderno, é obrigatório executar o seguinte comando no diretório de instalação do sistema (normalmente `C:\Program Files\PDV Moderno`):

```bash
npm install @whiskeysockets/baileys pino
```

Este comando instalará as bibliotecas necessárias para a comunicação com o WhatsApp. Sem essa etapa, a funcionalidade de envio de mensagens não funcionará.

### Arquivo `whatsapp_config.json`

```json
{
  "connection": {
    "max_reconnect_attempts": 10,
    "base_reconnect_delay": 1.0,
    "max_reconnect_delay": 300.0,
    "backoff_multiplier": 2.0,
    "connection_timeout": 30.0,
    "health_check_interval": 60.0,
    "session_expiry_days": 30
  },
  "messages": {
    "max_message_length": 4096,
    "template_variables": {
      "store_name": "{store_name}",
      "customer_name": "{customer_name}",
      "total_amount": "{total_amount}",
      "order_number": "{order_number}",
      "date": "{date}",
      "time": "{time}"
    },
    "default_templates": {
      "sale_notification": "✅ *{store_name}*\n\nPedido realizado com sucesso!\n\n📋 *Número do pedido:* {order_number}\n💰 *Valor total:* R$ {total_amount}\n📅 *Data:* {date} {time}\n\nObrigado pela preferência!",
      "payment_reminder": "💰 *{store_name}*\n\nOlá {customer_name}!\n\nLembramos que há um pagamento pendente no valor de R$ {total_amount}.\n\nPor favor, regularize sua situação.",
      "welcome_message": "👋 Olá {customer_name}!\n\nBem-vindo ao *{store_name}*!"
    }
  },
  "validation": {
    "phone_regex": "^(\\+55|55)?[\\s\\-\\.\\(\\)]?[1-9][0-9][\\)\\s\\-\\.\\.]?[9]?[0-9]{4}[\\s\\-\\.\\.]?[0-9]{4}$",
    "require_country_code": true,
    "allowed_countries": ["BR"],
    "max_phone_verification_cache": 1000,
    "phone_verification_ttl_hours": 24
  },
  "rate_limiting": {
    "max_messages_per_minute": 10,
    "max_messages_per_hour": 100,
    "burst_limit": 5,
    "enable_rate_limiting": true
  },
  "monitoring": {
    "enable_health_checks": true,
    "log_all_messages": true,
    "enable_message_history": true,
    "max_history_entries": 10000
  },
  "ui": {
    "status_update_interval": 2.0,
    "qr_code_timeout": 300,
    "show_detailed_errors": true,
    "friendly_error_messages": {
      "connection_failed": "Não foi possível conectar ao WhatsApp. Verifique sua conexão com a internet.",
      "invalid_number": "O número informado não é válido ou não existe no WhatsApp.",
      "rate_limited": "Muitas mensagens foram enviadas recentemente. Aguarde antes de tentar novamente.",
      "session_expired": "A sessão do WhatsApp expirou. É necessário escanear o QR Code novamente.",
      "message_failed": "Não foi possível enviar a mensagem. Verifique se o número está correto."
    }
  },
  "paths": {
    "session_dir": "whatsapp_session",
    "log_file": "whatsapp.log",
    "message_log_file": "whatsapp_messages.log",
    "cache_file": "whatsapp_cache.json",
    "history_file": "whatsapp_history.json"
  },
  "advanced": {
    "enable_debug_mode": false,
    "custom_user_agent": "PDV-Desktop",
    "proxy_settings": null,
    "custom_baileys_version": null
  }
}
```

### Templates de Mensagem

O sistema suporta templates customizáveis com variáveis:

```python
from integrations.whatsapp_config import get_whatsapp_config

config = get_whatsapp_config()
template = config.get_template('sale_notification')
# Retorna: "✅ *{store_name}*\n\nPedido realizado com sucesso!..."

# Uso com dados reais
message = template.format(
    store_name="Minha Loja",
    order_number="12345",
    total_amount="29.90",
    date="28/09/2025",
    time="14:30"
)
```

## 🔧 Como Usar

### 1. Instalação das Dependências Node.js

```bash
npm install @whiskeysockets/baileys pino
```

### 2. Conexão Inicial

```python
from integrations.whatsapp_manager import WhatsAppManager

# Obter instância singleton
manager = WhatsAppManager.get_instance()

# Conectar (primeira vez gera QR Code)
success = manager.connect()
if not success:
    print("Falha na conexão")

# Interface Qt conectará automaticamente aos sinais:
# - qr_code_ready: Quando QR Code estiver disponível
# - status_updated: Atualizações de status
# - error_occurred: Erros ocorridos
```

### 3. Envio de Mensagens

```python
# Método seguro com validações automáticas
result = manager.send_message(
    phone_number="5511999999999",
    message="Olá! Seu pedido está pronto.",
    bypass_cache=False  # Usar cache de validação
)

if result['success']:
    print(f"Mensagem enviada! ID: {result['message_id']}")
else:
    print(f"Erro: {result['error']}")
```

### 4. Monitoramento de Saúde

```python
# Verificar status da integração
health = manager.get_health_status()
print(f"Conectado: {health['connected']}")
print(f"Duração da conexão: {health['connection_duration']:.0f}s")
print(f"Tamanho do cache: {health['cache_size']}")
```

### 5. Histórico e Auditoria

```python
# Obter histórico de mensagens
history = manager.get_message_history(limit=50, phone_filter="5511999999999")

# Limpar cache se necessário
manager.clear_cache()
```

## 🔍 Sistema de Logs

### Níveis de Log
- **CONNECTION**: Eventos de conexão/desconexão
- **MESSAGE**: Operações com mensagens
- **AUDIT**: Auditoria de mensagens enviadas (arquivo separado)
- **ERROR**: Erros categorizados

### Arquivos de Log
- `whatsapp.log`: Logs gerais em JSON
- `whatsapp_messages.log`: Auditoria de mensagens
- `whatsapp_cache.json`: Cache persistente
- `whatsapp_history.json`: Histórico de mensagens

### Exemplo de Log Estruturado
```json
{
  "timestamp": "2025-09-28T18:48:51.123456",
  "level": "MESSAGE",
  "logger": "whatsapp_integration",
  "module": "whatsapp_manager",
  "message": "Mensagem enfileirada com sucesso",
  "message_id": "a1b2c3d4...",
  "phone_hash": "12345abc...",
  "message_length": 25
}
```

## 🚨 Tratamento de Erros

### Tipos de Erro
- `connection_failed`: Falha na conexão inicial
- `invalid_phone`: Número inválido/formato incorreto
- `empty_message`: Mensagem vazia
- `message_too_long`: Mensagem excede limite
- `rate_limited`: Limite de taxa excedido
- `invalid_number`: Número não existe no WhatsApp
- `worker_not_running`: Serviço não está ativo
- `internal_error`: Erro interno do sistema

### Mensagens Amigáveis
Todas as mensagens de erro são traduzidas para português com explicações claras para usuários não-técnicos.

## 🔐 Segurança e Compliance

### Recursos de Segurança
- **Auditoria Completa**: Todo envio é registrado com timestamp e resultado
- **Rate Limiting**: Proteção contra abuso/spam
- **Validação Robusta**: Números verificados via WhatsApp API
- **Cache Inteligente**: Minimiza chamadas à API externa
- **Logs Estruturados**: Facilita auditoria e compliance

### Anonimização de Dados
- Números de telefone são hashados nos logs (MD5)
- Dados sensíveis são mascarados automaticamente
- Arquivo de auditoria separado para compliance

## 📈 Monitoramento e Métricas

### Health Checks
- Verificação periódica de conectividade
- Monitoramento de recursos (CPU/memória)
- Alertas automáticos para problemas

### Métricas Disponíveis
- Taxa de sucesso de envio
- Latência média de resposta
- Contadores de rate limiting
- Status de cache e histórico

## 🧪 Testes

### Testes Unitários Recomendados
```python
# Teste de validação de telefone
config = get_whatsapp_config()
result = config.validate_phone("5511999999999")
assert result['valid'] == True

# Teste de rate limiting
result1 = manager.send_message("5511999999999", "Teste 1")
result2 = manager.send_message("5511999999999", "Teste 2")  # Deve falhar se rate limited
```

### Testes de Integração
1. Conectar e desconectar
2. Enviar mensagens válidas/inválidas
3. Testar rate limiting
4. Verificar recuperação de falhas
5. Validar persistência de cache

## 🐛 Troubleshooting

### Problemas Comuns

#### "Node.js não encontrado"
```
Solução: Instale Node.js (versão >= 14) e certifique-se que está no PATH
```

#### "Dependências Node ausentes"
```
Solução: Execute `npm install @whiskeysockets/baileys pino` na raiz do projeto
```

#### "QR Code não aparece"
```
Solução: Verifique logs em whatsapp.log e certifique-se que Node.js está funcionando
```

#### "Mensagens não são enviadas"
```
Solução: Verifique rate limiting e valide o número do telefone
```

### Logs de Debug
Ative modo debug no `whatsapp_config.json`:
```json
{
  "advanced": {
    "enable_debug_mode": true
  }
}
```

## 📚 Referências

- [Baileys WhatsApp Library](https://github.com/WhiskeySockets/Baileys)
- [Pino Logger](https://github.com/pinojs/pino)
- [WhatsApp Web API](https://developers.facebook.com/docs/whatsapp/)

## 🎯 Roadmap

### Melhorias Futuras
- [ ] Suporte a mídia (imagens/videos)
- [ ] Grupos de transmissão
- [ ] Templates ricos com botões
- [ ] Webhook para eventos externos
- [ ] Dashboard de métricas
- [ ] Suporte multi-conta

---

**Última atualização:** Setembro 2025
**Versão:** 2.0.0
**Compatibilidade:** Python 3.8+ | Node.js 14+ | PyQt6
