# PDV Moderno - Arquitetura de Integração Web e Notificações

Este documento descreve a arquitetura de integração do sistema PDV Moderno, projetada para ser robusta, escalável e de fácil manutenção. A integração é composta por dois pilares principais:

1.  **Sincronização de Dados com Supabase**: O núcleo da integração com o "site" ou plataforma web. Garante que os dados do PDV desktop estejam sempre em sincronia com um banco de dados central na nuvem.
2.  **Notificações via WhatsApp**: Um sistema de comunicação ativa que envia notificações (por exemplo, confirmações de venda) aos clientes, utilizando uma ponte com a biblioteca Baileys.

## 🏗️ Arquitetura de Alto Nível

O sistema opera com três componentes principais que se comunicam de forma assíncrona:

1.  **Aplicação PDV (Python/PyQt6)**: A aplicação desktop principal onde ocorrem as operações de venda, gestão de estoque, etc. É a fonte primária da maioria dos dados.
2.  **Backend Supabase (PostgreSQL)**: Atua como o banco de dados central na nuvem. A plataforma web ("o site") se conecta diretamente a este banco de dados. O Supabase oferece APIs, autenticação e funcionalidades em tempo real.
3.  **WhatsApp Bridge (Node.js/Baileys)**: Um serviço intermediário que conecta a aplicação PDV ao WhatsApp para enviar e receber mensagens.

O fluxo geral é o seguinte:
- Uma venda é realizada no **PDV Moderno**.
- O registro da venda é salvo no banco de dados local (SQLite) com o status `pending_create`.
- O `SyncManager` (gerenciador de sincronização) detecta a pendência e envia o novo registro para o **Backend Supabase**.
- A plataforma web agora pode visualizar esta nova venda.
- Simultaneamente, o PDV pode usar o **WhatsApp Bridge** para enviar uma notificação de confirmação da venda para o cliente.

---

## 🌐 Parte 1: Sincronização de Dados com Supabase (A Integração com o Site)

Esta é a espinha dorsal da integração web. Ela permite que o PDV desktop funcione de forma offline e sincronize os dados com a nuvem assim que uma conexão estiver disponível.

### Componentes Chave

-   **`data/sync_manager.py`**: O orquestrador da sincronização. É uma classe robusta que gerencia o fluxo de upload e download de dados.
-   **`data/api_client.py`**: Um wrapper para o cliente Supabase, que centraliza a lógica de conexão e as credenciais.
-   **`config.json`**: Arquivo de configuração que armazena as credenciais (URL e chave de API) do Supabase.
-   **`data/schema.py`**: Define a estrutura do banco de dados local (SQLite), que deve ser um espelho da estrutura do banco de dados no Supabase.

### Fluxo de Sincronização

O `SyncManager` opera em um ciclo de três etapas, executado em uma ordem de dependência para garantir a integridade referencial dos dados. A ordem é definida na constante `SYNC_ORDER`.

#### Etapa 1: Upload de Novos Registros (`_sync_pending_creates`)

1.  O `SyncManager` varre todas as tabelas do banco de dados local em busca de registros marcados com `sync_status = 'pending_create'`.
2.  Para cada registro encontrado, ele constrói um "payload" (dados a serem enviados), traduzindo chaves estrangeiras locais (ex: `group_id = 10`) para as chaves estrangeiras da web (ex: `group_id = 'uuid-do-grupo-na-web'`). Isso é feito pela função `_get_web_id`.
3.  Os dados são enviados em lote para o Supabase. Para tabelas que podem ter conflitos (ex: um produto com um código de barras já existente), o `SyncManager` utiliza o comando `upsert` do Supabase para inserir ou atualizar o registro, evitando duplicatas.
4.  Após o sucesso, o Supabase retorna os registros criados, incluindo o `id` único da web.
5.  O `SyncManager` atualiza os registros locais, salvando o `id_web` recebido e mudando o `sync_status` para `'synced'`.

#### Etapa 2: Upload de Atualizações (`_sync_pending_updates`)

1.  O processo é semelhante ao de criação, mas busca por registros com `sync_status = 'pending_update'`.
2.  Ele envia uma requisição `update` para o Supabase, usando o `id_web` do registro como chave para garantir que o item correto seja atualizado.
3.  Após o sucesso, o `sync_status` local é atualizado para `'synced'`.

#### Etapa 3: Download de Dados da Web (`_sync_web_to_local`)

1.  O `SyncManager` busca no Supabase por todos os registros que foram alterados desde a última sincronização. Isso é feito usando um timestamp (`last_sync_timestamp`).
2.  Para cada registro recebido do Supabase, ele verifica se já existe um registro correspondente no banco de dados local (usando o `id_web`).
3.  **Se existe**: Ele executa um `UPDATE` no registro local com os novos dados.
4.  **Se não existe**: Ele executa um `INSERT`, criando um novo registro no banco de dados local. Antes de inserir, ele traduz as chaves estrangeiras da web para as chaves locais correspondentes usando a função `_get_local_id`.
5.  Ao final de todo o ciclo, o `last_sync_timestamp` é atualizado, preparando para a próxima sincronização.

### Configuração para Desenvolvedores

1.  **Credenciais**: Adicione a URL e a chave de API `anon` do seu projeto Supabase ao arquivo `config.json`:
    ```json
    {
      "supabase": {
        "url": "https://SEU_PROJETO.supabase.co",
        "key": "SUA_CHAVE_ANON_AQUI"
      }
    }
    ```
2.  **Schema do Banco**: Garanta que as tabelas e colunas no seu banco de dados Supabase correspondam exatamente ao que está definido em `data/schema.py`. Qualquer divergência causará erros de sincronização.

---

## 📱 Parte 2: Integração com WhatsApp

Este módulo permite o envio de notificações e a interação com clientes via WhatsApp. Ele é projetado para ser resiliente, com sistemas de retry, cache e tratamento de erros.

> **Nota**: Para uma documentação exaustiva e detalhada sobre este módulo, consulte o arquivo `README_WHATSAPP_INTEGRATION.md`.

### Componentes Chave

-   **`integrations/whatsapp_manager.py`**: A classe principal que gerencia a ponte com o Node.js. É um singleton que controla a conexão, o envio de mensagens e o estado da integração.
-   **`wa_bridge.js`**: O script Node.js que utiliza a biblioteca `@whiskeysockets/baileys` para se comunicar com o WhatsApp. Ele é iniciado e controlado pelo `WhatsAppManager`.
-   **`integrations/whatsapp_config.py`**: Carrega as configurações do `whatsapp_config.json`, que define limites de taxa, templates de mensagem, etc.
-   **`integrations/whatsapp_command_handler.py`**: Processa comandos recebidos via WhatsApp (ex: `!saldo`, `!status`), permitindo que administradores interajam com o PDV remotamente.

### Fluxo de Notificação

1.  Uma ação no PDV (ex: `finalizar_venda`) chama o método `WhatsAppManager.get_instance().send_message(...)`.
2.  A mensagem é validada (número, conteúdo, limite de taxa) e colocada em uma fila de envio no `WhatsAppWorker`.
3.  O `WhatsAppWorker` envia a mensagem para o processo `wa_bridge.js` através do `stdin`.
4.  O `wa_bridge.js` utiliza o Baileys para enviar a mensagem para o destinatário via WhatsApp.
5.  O resultado (sucesso ou falha) é comunicado de volta para o `WhatsAppManager` através do `stdout`, que então atualiza o histórico e os logs.

### Configuração para Desenvolvedores

1.  **Instale as dependências do Node.js**:
    ```bash
    npm install @whiskeysockets/baileys pino
    ```
2.  **Configure o WhatsApp**: As configurações detalhadas, como templates de mensagem e limites, estão no arquivo `whatsapp_config.json`.

---

## 🚀 Executando o Ambiente Completo

Para um desenvolvedor configurar e executar o projeto localmente:

1.  **Configure o Supabase**: Preencha as credenciais do Supabase em `config.json`.
2.  **Configure o WhatsApp**: Revise e ajuste as configurações em `whatsapp_config.json` conforme necessário.
3.  **Instale as Dependências Python**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Instale as Dependências Node.js**:
    ```bash
    npm install
    ```
5.  **Execute a Aplicação Principal**:
    ```bash
    python main.py
    ```
    A aplicação se encarregará de iniciar a conexão com o WhatsApp e preparar o gerenciador de sincronização. A primeira conexão com o WhatsApp exigirá a leitura de um QR Code.

