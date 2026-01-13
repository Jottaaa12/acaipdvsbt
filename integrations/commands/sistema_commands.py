# integrations/commands/sistema_commands.py
from .base_command import BaseCommand, ManagerCommand
from typing import List, Any, Dict
import os
import json
from datetime import datetime
from integrations.whatsapp_config import get_whatsapp_config

class StatusCommand(ManagerCommand):
    """Lida com o comando /status"""
    def execute(self) -> str:
        try:
            health = self.manager.get_health_status()

            # Ícones de status
            status_icon = "🟢" if health['connected'] else "🔴"
            worker_icon = "🟢" if health['worker_running'] else "🔴"

            # Alertas visuais
            alerts = []
            if health['worker_running'] and not health['connected']:
                alerts.append("⚠️ *ALERTA:* Worker ativo mas desconectado!")
            if health['cache_size'] > 1000:
                alerts.append("📊 Cache de números muito grande")
            if health['message_history_count'] > 5000:
                alerts.append("📜 Histórico de mensagens extenso")

            # Formatação de tempo
            duration_seconds = health['connection_duration']
            if duration_seconds > 0:
                minutes, seconds = divmod(duration_seconds, 60)
                hours, minutes = divmod(minutes, 60)
                duration_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
            else:
                duration_str = "Nunca conectado"

            # Último health check
            last_check_str = "Nunca"
            if health.get('last_health_check'):
                try:
                    from datetime import datetime
                    last_check = datetime.fromisoformat(health['last_health_check'])
                    now = datetime.now()
                    diff_minutes = (now - last_check).total_seconds() / 60
                    if diff_minutes < 60:
                        last_check_str = f"{int(diff_minutes)}min atrás"
                    else:
                        last_check_str = last_check.strftime('%H:%M:%S')
                except (ValueError, TypeError):
                    last_check_str = "Erro na formatação"

            # Estatísticas adicionais se disponíveis
            extra_stats = ""
            if hasattr(self.manager, '_worker_thread') and self.manager._worker_thread:
                worker = self.manager._worker_thread
                if hasattr(worker, '_messages_sent'):
                    extra_stats += f"📤 *Mensagens Enviadas:* `{worker._messages_sent}`\n"
                if hasattr(worker, '_messages_failed'):
                    extra_stats += f"📥 *Mensagens Falhadas:* `{worker._messages_failed}`\n"
                if hasattr(worker, '_connection_attempts'):
                    extra_stats += f"🔄 *Tentativas de Conexão:* `{worker._connection_attempts}`\n"

            # Construir resposta organizada
            response = "🩺 *STATUS DA INTEGRAÇÃO WHATSAPP*\n\n"

            # Seção de Status Principal
            response += "📊 *STATUS PRINCIPAL*\n"
            response += f"{status_icon} *Conectado:* `{str(health['connected'])}`\n"
            response += f"{worker_icon} *Serviço Ativo:* `{str(health['worker_running'])}`\n"
            response += f"⏱️ *Tempo de Conexão:* `{duration_str}`\n"
            response += f"🔍 *Último Health Check:* `{last_check_str}`\n\n"

            # Seção de Estatísticas
            response += "📈 *ESTATÍSTICAS*\n"
            response += f"💾 *Cache de Números:* `{health['cache_size']}`\n"
            response += f"📜 *Histórico de Mensagens:* `{health['message_history_count']}`\n"
            if extra_stats:
                response += extra_stats

            # Alertas
            if alerts:
                response += "\n🚨 *ALERTAS*\n"
                for alert in alerts:
                    response += f"{alert}\n"

            return response.strip()

        except Exception as e:
            self.logging.error(f"Erro ao obter status da integração: {e}", exc_info=True)
            return "❌ Não foi possível obter o status da integração."

class LogsCommand(ManagerCommand):
    """Lida com o comando /logs com filtros avançados e paginação"""
    def execute(self) -> str:
        try:
            # Parsing avançado dos argumentos
            # Uso: /logs [nível] [linhas] [página] [busca] [data_inicio] [data_fim]
            # Ou: /logs stats (para estatísticas)

            if self.args and self.args[0].lower() == 'stats':
                return self._get_log_statistics()

            # Parâmetros com valores padrão
            level_filter = None
            num_lines = 10
            page = 1
            search_text = None
            date_start = None
            date_end = None

            # Parsing dos argumentos
            args = self.args[:] if self.args else []
            i = 0

            # Primeiro argumento: nível ou 'stats'
            if i < len(args) and args[i].upper() in ['ERROR', 'WARNING', 'INFO', 'DEBUG', 'CONNECTION', 'MESSAGE', 'AUDIT']:
                level_filter = args[i].upper()
                i += 1

            # Segundo argumento: número de linhas
            if i < len(args):
                try:
                    num_lines = int(args[i])
                    if num_lines < 1 or num_lines > 50:
                        num_lines = 10
                    i += 1
                except ValueError:
                    pass

            # Terceiro argumento: página
            if i < len(args):
                try:
                    page = int(args[i])
                    if page < 1:
                        page = 1
                    i += 1
                except ValueError:
                    pass

            # Quarto argumento: texto de busca
            if i < len(args):
                search_text = args[i]
                i += 1

            # Quinto e sexto: datas (formato HH:MM ou YYYY-MM-DD)
            if i < len(args):
                date_start = args[i]
                i += 1
            if i < len(args):
                date_end = args[i]

            return self._get_logs_with_filters(level_filter, num_lines, page, search_text, date_start, date_end)

        except Exception as e:
            self.logging.error(f"Erro ao processar comando /logs: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao processar os logs."

    def _get_logs_with_filters(self, level_filter, num_lines, page, search_text, date_start, date_end):
        """Busca logs com filtros aplicados"""
        log_file_path = self.manager.logger.log_file

        if not os.path.exists(log_file_path):
            return "❌ Arquivo de log não encontrado."

        # Ler todas as linhas do log
        all_entries = []
        with open(log_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    all_entries.append(entry)
                except (json.JSONDecodeError, AttributeError):
                    continue

        if not all_entries:
            return "ℹ️ O arquivo de log está vazio."

        # Aplicar filtros
        filtered_entries = self._apply_filters(all_entries, level_filter, search_text, date_start, date_end)

        # Paginação
        total_entries = len(filtered_entries)
        start_idx = (page - 1) * num_lines
        end_idx = start_idx + num_lines

        if start_idx >= total_entries:
            return f"ℹ️ Página {page} não existe. Total de entradas filtradas: {total_entries}"

        page_entries = filtered_entries[start_idx:end_idx]
        total_pages = (total_entries + num_lines - 1) // num_lines

        # Construir resposta
        filter_desc = self._build_filter_description(level_filter, search_text, date_start, date_end)

        response = f"📜 *LOGS WHATSAPP* {filter_desc}\n"
        response += f"📄 Página {page}/{total_pages} | Total: {total_entries} entradas\n\n"

        for entry in page_entries:
            timestamp = datetime.fromisoformat(entry['timestamp'])
            time_str = timestamp.strftime('%H:%M:%S')
            date_str = timestamp.strftime('%d/%m')

            level = entry.get('level', 'N/A')
            message = entry.get('message', 'Mensagem não encontrada')
            module = entry.get('module', 'unknown')
            function = entry.get('function', 'unknown')

            # Ícones por nível
            icon = {
                "ERROR": "🔴", "WARNING": "🟡", "INFO": "🔵",
                "DEBUG": "⚪", "CONNECTION": "🔗", "MESSAGE": "💬", "AUDIT": "📋"
            }.get(level, "⚪")

            # Preview da mensagem
            message_preview = message if len(message) < 80 else message[:80] + '...'

            # Formatação melhorada
            response += f"`{date_str} {time_str}` {icon} *{level}*\n"
            response += f"📍 `{module}.{function}`\n"
            response += f"💬 {message_preview}\n\n"

        # Navegação de páginas
        if total_pages > 1:
            nav_hint = "💡 Use `/logs"
            if level_filter:
                nav_hint += f" {level_filter}"
            nav_hint += f" {num_lines} [página]` para navegar"
            response += f"{nav_hint}\n"

        return response.strip()

    def _apply_filters(self, entries, level_filter, search_text, date_start, date_end):
        """Aplica todos os filtros às entradas de log"""
        filtered = entries

        # Filtro por nível
        if level_filter:
            filtered = [e for e in filtered if e.get('level') == level_filter]

        # Filtro por texto
        if search_text:
            search_lower = search_text.lower()
            filtered = [e for e in filtered if search_lower in e.get('message', '').lower()]

        # Filtro por data
        if date_start or date_end:
            filtered = self._filter_by_date(filtered, date_start, date_end)

        # Ordenar por timestamp (mais recente primeiro)
        filtered.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        return filtered

    def _filter_by_date(self, entries, date_start, date_end):
        """Filtra entradas por intervalo de datas"""
        filtered = []

        for entry in entries:
            try:
                entry_time = datetime.fromisoformat(entry.get('timestamp', ''))

                # Converter parâmetros de data para datetime
                start_time = None
                end_time = None

                if date_start:
                    if len(date_start) == 5:  # HH:MM
                        today = datetime.now().date()
                        start_time = datetime.combine(today, datetime.strptime(date_start, '%H:%M').time())
                    else:  # YYYY-MM-DD
                        start_time = datetime.fromisoformat(date_start)

                if date_end:
                    if len(date_end) == 5:  # HH:MM
                        today = datetime.now().date()
                        end_time = datetime.combine(today, datetime.strptime(date_end, '%H:%M').time())
                    else:  # YYYY-MM-DD
                        end_time = datetime.fromisoformat(date_end)

                # Verificar se está no intervalo
                if start_time and entry_time < start_time:
                    continue
                if end_time and entry_time > end_time:
                    continue

                filtered.append(entry)

            except (ValueError, KeyError):
                # Se não conseguir parsear a data, incluir a entrada
                filtered.append(entry)

        return filtered

    def _build_filter_description(self, level_filter, search_text, date_start, date_end):
        """Constrói descrição dos filtros aplicados"""
        desc_parts = []

        if level_filter:
            desc_parts.append(f"Nível: {level_filter}")
        if search_text:
            desc_parts.append(f"Busca: '{search_text}'")
        if date_start:
            desc_parts.append(f"De: {date_start}")
        if date_end:
            desc_parts.append(f"Até: {date_end}")

        if desc_parts:
            return f"({', '.join(desc_parts)})"
        return "(Todos)"

    def _get_log_statistics(self):
        """Retorna estatísticas resumidas dos logs"""
        log_file_path = self.manager.logger.log_file

        if not os.path.exists(log_file_path):
            return "❌ Arquivo de log não encontrado."

        # Contadores
        level_counts = {}
        error_types = {}
        hourly_distribution = {}
        recent_errors = []

        with open(log_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    level = entry.get('level', 'UNKNOWN')
                    timestamp = entry.get('timestamp', '')

                    # Contagem por nível
                    level_counts[level] = level_counts.get(level, 0) + 1

                    # Tipos de erro
                    if level == 'ERROR':
                        error_type = entry.get('error_type', 'unknown')
                        error_types[error_type] = error_types.get(error_type, 0) + 1
                        recent_errors.append(entry)

                    # Distribuição horária
                    if timestamp:
                        try:
                            hour = datetime.fromisoformat(timestamp).hour
                            hourly_distribution[hour] = hourly_distribution.get(hour, 0) + 1
                        except (ValueError, TypeError):
                            pass  # Ignora timestamps inválidos

                except (json.JSONDecodeError, AttributeError):
                    continue

        # Construir resposta
        response = "📊 *ESTATÍSTICAS DOS LOGS WHATSAPP*\n\n"

        # Contagem por nível
        response += "📈 *CONTAGEM POR NÍVEL*\n"
        total_logs = sum(level_counts.values())
        for level, count in sorted(level_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_logs * 100) if total_logs > 0 else 0
            icon = {
                "ERROR": "🔴", "WARNING": "🟡", "INFO": "🔵",
                "DEBUG": "⚪", "CONNECTION": "🔗", "MESSAGE": "💬", "AUDIT": "📋"
            }.get(level, "⚪")
            response += f"{icon} *{level}:* {count} ({percentage:.1f}%)\n"

        # Tipos de erro mais comuns
        if error_types:
            response += "\n🚨 *TIPOS DE ERRO MAIS COMUNS*\n"
            for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:5]:
                response += f"• {error_type}: {count}\n"

        # Distribuição horária
        if hourly_distribution:
            response += "\n🕐 *ATIVIDADE POR HORA*\n"
            peak_hour = max(hourly_distribution.items(), key=lambda x: x[1])
            response += f"🏆 Pico: {peak_hour[0]:02d}:00h ({peak_hour[1]} logs)\n"

            # Mostrar últimas 24 horas
            hours = sorted(hourly_distribution.keys())
            if hours:
                response += "📊 Distribuição: "
                for hour in range(24):
                    count = hourly_distribution.get(hour, 0)
                    if count > 0:
                        response += f"{hour:02d}h({count}) "
                response += "\n"

        # Erros recentes
        if recent_errors:
            response += "\n🔥 *ÚLTIMOS ERROS*\n"
            for error in recent_errors[-3:]:  # Últimos 3 erros
                timestamp = datetime.fromisoformat(error.get('timestamp', '')).strftime('%H:%M:%S')
                message = error.get('message', '')[:60] + '...' if len(error.get('message', '')) > 60 else error.get('message', '')
                response += f"`{timestamp}` {message}\n"

        response += f"\n📊 *TOTAL:* {total_logs} entradas de log"
        return response.strip()

class SistemaCommand(ManagerCommand):
    """Lida com o comando /sistema"""
    def execute(self) -> str:
        if not self.args:
            return "Uso: /sistema [limpar_sessao | set_group]"

        subcommand = self.args[0].lower()
        if subcommand == 'limpar_sessao':
            try:
                self.manager.disconnect(cleanup_session=True)
                return "✅ Sessão do WhatsApp limpa. Por favor, reinicie a conexão no PDV para gerar um novo QR Code."
            except Exception as e:
                self.logging.error(f"Erro ao limpar sessão via comando: {e}", exc_info=True)
                return "❌ Ocorreu um erro ao tentar limpar a sessão."
        
        elif subcommand == 'set_group':
            try:
                # self.chat_id está disponível graças à mudança na classe base
                group_id = self.chat_id
                if not group_id or not group_id.endswith('@g.us'):
                    return "❌ Este comando só pode ser usado dentro de um grupo do WhatsApp."

                wa_config = get_whatsapp_config()
                wa_config.set('advanced.GROUP_NOTIFICATION_ID', group_id)
                wa_config.save_config()
                
                return f"✅ Sucesso! Este grupo foi definido para receber as notificações do sistema."
            except Exception as e:
                self.logging.error(f"Erro ao definir grupo de notificação via comando: {e}", exc_info=True)
                return "❌ Ocorreu um erro ao tentar definir este grupo para notificações."
        
        else:
            return f"Subcomando '/sistema {subcommand}' não reconhecido."

class DbStatusCommand(BaseCommand):
    """
    Retorna estatísticas vitais do banco de dados (tamanho, contagens).
    """
    def execute(self) -> str:
        try:
            self.logging.info("Executando /db_status...")
            stats = self.db.get_db_statistics()

            response = "🗃️ *Status do Banco de Dados (pdv.db)*\n\n"
            response += f"  - *Tamanho do Arquivo:* `{stats['file_size_mb']:.2f} MB`\n"
            response += f"  - *Vendas (Hoje):* `{stats['today_sales_count']}`\n"
            response += f"  - *Vendas (Total):* `{stats['total_sales_count']}`\n"
            response += f"  - *Produtos Cadastrados:* `{stats['total_products_count']}`\n"
            response += f"  - *Clientes Cadastrados:* `{stats['total_customers_count']}`"

            return response

        except Exception as e:
            self.logging.error(f"Erro ao gerar /db_status: {e}", exc_info=True)
            return "❌ Erro ao consultar as estatísticas do banco de dados."
