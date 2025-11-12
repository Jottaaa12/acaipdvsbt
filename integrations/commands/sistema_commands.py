# integrations/commands/sistema_commands.py
from .base_command import ManagerCommand
from typing import List, Any, Dict
import os
import json
from datetime import datetime

class StatusCommand(ManagerCommand):
    """Lida com o comando /status"""
    def execute(self) -> str:
        try:
            health = self.manager.get_health_status()
            
            status_icon = "✅" if health['connected'] else "❌"
            worker_icon = "✅" if health['worker_running'] else "❌"
            
            duration_seconds = health['connection_duration']
            minutes, seconds = divmod(duration_seconds, 60)
            hours, minutes = divmod(minutes, 60)
            duration_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

            response = (
                f"🩺 *Status da Integração WhatsApp*\n\n"
                f"{status_icon} *Conectado:* `{str(health['connected'])}`\n"
                f"{worker_icon} *Serviço Ativo:* `{str(health['worker_running'])}`\n"
                f"⏱️ *Tempo de Conexão:* `{duration_str}`\n"
                f" caching *Cache de Números:* `{health['cache_size']}`\n"
                f"📜 *Histórico de Msgs:* `{health['message_history_count']}`"
            )
            return response
        except Exception as e:
            self.logging.error(f"Erro ao obter status da integração: {e}", exc_info=True)
            return "❌ Não foi possível obter o status da integração."

class LogsCommand(ManagerCommand):
    """Lida com o comando /logs"""
    def execute(self) -> str:
        try:
            log_level_filter = self.args[0].upper() if self.args else None
            num_lines = int(self.args[1]) if len(self.args) > 1 else 5

            log_file_path = self.manager.logger.log_file
            
            if not os.path.exists(log_file_path):
                return "❌ Arquivo de log não encontrado."

            relevant_lines: List[Dict[str, Any]] = []
            with open(log_file_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()

            for line in reversed(all_lines):
                if len(relevant_lines) >= num_lines:
                    break
                try:
                    log_entry = json.loads(line.strip())
                    if log_level_filter:
                        if log_entry.get('level') == log_level_filter:
                            relevant_lines.append(log_entry)
                    else:
                        relevant_lines.append(log_entry)
                except (json.JSONDecodeError, AttributeError):
                    continue

            if not relevant_lines:
                return f"ℹ️ Nenhum log encontrado para o nível '{log_level_filter}'." if log_level_filter else "ℹ️ O arquivo de log está vazio."

            relevant_lines.reverse()

            response = f"📜 *Últimos {len(relevant_lines)} Logs ({log_level_filter or 'Todos'})*\n\n"
            for entry in relevant_lines:
                timestamp = datetime.fromisoformat(entry['timestamp']).strftime('%H:%M:%S')
                level = entry.get('level', 'N/A')
                message = entry.get('message', 'Mensagem não encontrada')
                
                icon = "🔴" if level == "ERROR" else "🟡" if level == "WARNING" else "🔵" if level == "CONNECTION" else "⚪"
                
                message_preview = message if len(message) < 100 else message[:100] + '...'
                response += f"`{timestamp}` {icon} *{level}* - {message_preview}\n"
            
            return response.strip()

        except ValueError:
            return "❌ Uso inválido. O número de linhas deve ser um número. Ex: `/logs ERROR 10`"
        except Exception as e:
            self.logging.error(f"Erro ao manusear comando /logs: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao processar os logs."

class SistemaCommand(ManagerCommand):
    """Lida com o comando /sistema"""
    def execute(self) -> str:
        if not self.args:
            return "Uso: /sistema [limpar_sessao]"

        subcommand = self.args[0].lower()
        if subcommand == 'limpar_sessao':
            try:
                self.manager.disconnect(cleanup_session=True)
                return "✅ Sessão do WhatsApp limpa. Por favor, reinicie a conexão no PDV para gerar um novo QR Code."
            except Exception as e:
                self.logging.error(f"Erro ao limpar sessão via comando: {e}", exc_info=True)
                return "❌ Ocorreu um erro ao tentar limpar a sessão."
        else:
            return f"Subcomando '/sistema {subcommand}' não reconhecido."
