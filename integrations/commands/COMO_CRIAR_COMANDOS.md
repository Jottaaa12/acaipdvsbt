# 🚀 Como Criar Novos Comandos do WhatsApp

Este guia é o "manual de fábrica" para adicionar novas funcionalidades de comando ao bot do WhatsApp do PDV.

A arquitetura usa o **Padrão *Command***, o que significa que cada comando é uma classe separada. Adicionar um novo comando é um processo simples de 3 passos:

1.  **Escolher** o template de comando (Básico ou Avançado).
2.  **Criar** o arquivo da classe e escrever a lógica.
3.  **Registrar** a nova classe no "despachante" principal.

---

## Passo 1: Escolher o Tipo de Comando

Existem dois tipos de comandos. Escolha o mais simples que atenda sua necessidade:

### 1. `BaseCommand` (Padrão)
Use este quando seu comando **NÃO** precisa saber o status da conexão do WhatsApp, acessar logs da integração ou reiniciar o worker.

* **Ideal para:** Consultas de banco de dados, relatórios, lógica de negócios.
* **Exemplos:** `/vendas`, `/fiado`, `/estoque`, `/produto`.
* **Acesso:** `self.args`, `self.db`, `self.logging`.

### 2. `ManagerCommand` (Avançado)
Use este **APENAS** se o seu comando precisar interagir com o `WhatsAppManager`.

* **Ideal para:** Comandos de sistema/diagnóstico.
* **Exemplos:** `/status`, `/logs`, `/sistema limpar_sessao`.
* **Acesso:** `self.args`, `self.db`, `self.logging`, e `self.manager`.

---

## Passo 2: Criar o Arquivo do Comando

Crie um novo arquivo `.py` dentro deste diretório (`integrations/commands/`). Por exemplo: `meu_novo_comando.py`.

Use um dos templates abaixo como ponto de partida.

### Template 1: `BaseCommand` (Padrão)
*Para comandos de lógica de negócios (ex: /relatorio_lucro)*

```python
# integrations/commands/lucro_command.py
from .base_command import BaseCommand
from typing import List

class LucroCommand(BaseCommand):
    """
    (Descreva o que seu comando faz aqui)
    Ex: Gera um relatório de lucratividade do dia.
    """
    def __init__(self, args: List[str]):
        super().__init__(args)
    
    def execute(self) -> str:
        """
        Esta é a única função que você precisa implementar.
        Ela deve retornar uma string (a resposta para o usuário).
        """
        try:
            # self.args -> contém a lista de argumentos (ex: ['hoje'])
            # self.db -> permite acesso ao banco de dados (ex: self.db.get_sales_report(...))
            # self.logging -> permite logar erros (ex: self.logging.error(...))

            # --- SUA LÓGICA AQUI ---
            # Exemplo de lógica:
            if not self.args:
                periodo = 'hoje'
            else:
                periodo = self.args[0]

            # (Lógica de busca no banco de dados)
            lucro = 150.00 # self.db.get_profit(periodo)
            
            response = f"📈 Relatório de Lucro ({periodo}):\n\n"
            response += f"Lucro Bruto: R$ {lucro:.2f}"
            
            return response
            
        except Exception as e:
            self.logging.error(f"Erro ao gerar relatório de lucro: {e}", exc_info=True)
            return "❌ Ocorreu um erro ao gerar o relatório de lucro."

```

### Template 2: `ManagerCommand` (Avançado)
*Para comandos de sistema (ex: /reiniciar_conexao)*

```python
# integrations/commands/conexao_command.py
from .base_command import ManagerCommand
from typing import List

# Importe o 'manager' type-hinting
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from integrations.whatsapp_manager import WhatsAppManager

class ReiniciarConexaoCommand(ManagerCommand):
    """
    (Descreva o que seu comando faz aqui)
    Ex: Força a desconexão e reconexão do worker do WhatsApp.
    """
    def __init__(self, args: List[str], manager: 'WhatsAppManager'):
        super().__init__(args, manager)
    
    def execute(self) -> str:
        """
        Esta é a única função que você precisa implementar.
        Ela deve retornar uma string (a resposta para o usuário).
        """
        try:
            # self.manager -> permite acesso ao manager (ex: self.manager.disconnect(...))
            
            # --- SUA LÓGICA AQUI ---
            self.logging.warning("Comando /reiniciar_conexao recebido. Iniciando reconexão.")
            
            # Exemplo de uso do manager:
            self.manager.disconnect(cleanup_session=False) 
            self.manager.connect(force_reconnect=True)
            
            return "🔄 Serviço do WhatsApp está sendo reiniciado..."
            
        except Exception as e:
            self.logging.error(f"Erro ao reiniciar conexão: {e}", exc_info=True)
            return "❌ Ocorreu um erro ao tentar reiniciar a conexão."
```

---

## Passo 3: Registrar o Comando (Obrigatório)

Seu comando não funcionará até ser registrado.

1.  Abra o arquivo: `integrations/whatsapp_command_handler.py`.

2.  **Importe sua classe** no topo do arquivo (junto com os outros imports de comandos):

    ```python
    # ... (outros imports)
    from .commands.lucro_command import LucroCommand 
    ```

3.  **Adicione sua classe ao `self.command_map`** dentro do `__init__`:

    ```python
    class CommandHandler:
        def __init__(self):
            # ... (código existente)
            
            # O novo Command Map mapeia strings para CLASSES
            self.command_map: Dict[str, Type[BaseCommand]] = {
                '/ajuda': HelpCommand,
                '/vendas': SalesReportCommand,
                '/caixa': CaixaCommand,
                # ... (comandos existentes)
                
                # --- ADICIONE SEU NOVO COMANDO AQUI ---
                '/lucro': LucroCommand,
                '/lucro_do_dia': LucroCommand, # Você pode adicionar apelidos (aliases)
                # -------------------------------------
            }
    ```

---

## ✅ Checklist Final

- [ ] **Passo 1:** Eu escolhi o tipo correto (`BaseCommand` ou `ManagerCommand`)?
- [ ] **Passo 2:** Eu criei meu arquivo `.py` (ex: `lucro_command.py`) em `integrations/commands/`?
- [ ] **Passo 2:** Minha classe herda da classe base correta?
- [ ] **Passo 2:** Minha função `execute()` sempre retorna uma `str`?
- [ ] **Passo 2:** Eu usei `try...except` para capturar erros e retornar uma mensagem amigável?
- [ ] **Passo 3:** Eu importei minha nova classe no `whatsapp_command_handler.py`?
- [ ] **Passo 3:** Eu adicionei meu comando (ex: `'/lucro': LucroCommand`) ao `self.command_map`?
- [ ] **Teste:** Eu reiniciei o PDV e testei o comando pelo WhatsApp?
