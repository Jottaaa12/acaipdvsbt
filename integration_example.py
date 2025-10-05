"""
Exemplo de integração dos sistemas de melhoria ao PDV existente.

Este arquivo mostra como integrar todos os sistemas criados:
- ErrorHandler (error_handler.py)
- Validation (validation.py)
- LoadingOverlay (ui/loading_overlay.py)
- Worker (ui/worker.py)
- BackupScheduler (backup_scheduler.py)
- RecoveryManager (recovery_manager.py)
- Build (build.py)
- Updater (updater.py)

Para usar, copie as partes relevantes para o seu main.py existente.
"""

import sys
import os
import logging
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer

# Importar os novos sistemas de melhoria
import error_handler
import validation
from ui.loading_overlay import loading_manager
from ui.worker import thread_manager
import backup_scheduler
import recovery_manager
import build
import updater
import database

class PDVApplication:
    """Classe principal da aplicação com sistemas de melhoria integrados."""

    def __init__(self, app):
        self.app = app

        # Inicializar sistemas de melhoria
        self.setup_improvement_systems()

        # ... resto da inicialização existente ...

    def setup_improvement_systems(self):
        """Configura todos os sistemas de melhoria."""

        # 1. Configurar tratamento global de erros
        error_handler.setup_global_error_handler()

        # 2. Inicializar gerenciadores
        self.recovery_manager = recovery_manager.recovery_manager
        self.backup_manager = backup_scheduler.backup_manager
        self.auto_update_manager = updater.auto_update_manager

        # 3. Conectar sinais importantes
        self.connect_signals()

        # 4. Iniciar sistemas automáticos
        self.start_automatic_systems()

    def connect_signals(self):
        """Conecta sinais dos sistemas de melhoria."""

        # Error handler - conectar a diálogos customizados se necessário
        error_handler.error_handler.critical_error_occurred.connect(
            self.on_critical_error
        )

        # Backup - conectar a notificações
        self.backup_manager.scheduler.backup_completed.connect(
            self.on_backup_completed
        )
        self.backup_manager.scheduler.backup_failed.connect(
            self.on_backup_failed
        )

        # Updates - conectar a notificações
        self.auto_update_manager.update_checker.update_available.connect(
            self.on_update_available
        )

    def start_automatic_systems(self):
        """Inicia sistemas automáticos."""

        # Iniciar recovery manager (auto-save)
        self.recovery_manager.start_auto_save()

        # Iniciar backup automático
        self.backup_manager.scheduler.start_scheduler()

        # Iniciar verificação automática de updates
        self.auto_update_manager.start_auto_check()

    def on_critical_error(self, title: str, message: str):
        """Tratamento de erro crítico."""
        # Pode adicionar lógica específica para erros críticos
        # Por exemplo, fazer backup automático antes de fechar
        logging.critical(f"Erro crítico detectado: {title} - {message}")

    def on_backup_completed(self, backup_path: str):
        """Callback quando backup é concluído."""
        filename = os.path.basename(backup_path)
        logging.info(f"Backup automático concluído: {filename}")

    def on_backup_failed(self, error_msg: str):
        """Callback quando backup falha."""
        logging.error(f"Backup automático falhou: {error_msg}")

    def on_update_available(self, version: str, description: str):
        """Callback quando atualização está disponível."""
        logging.info(f"Atualização disponível: {version}")

    def show_improvement_settings(self):
        """Mostra configurações dos sistemas de melhoria."""

        # Criar menu com opções dos novos sistemas
        from PyQt6.QtWidgets import QMenu, QAction

        menu = QMenu()

        # Configurações de backup
        backup_action = QAction("Configurações de Backup")
        backup_action.triggered.connect(backup_scheduler.show_backup_settings)
        menu.addAction(backup_action)

        # Configurações de update
        update_action = QAction("Configurações de Atualização")
        update_action.triggered.connect(updater.show_update_settings)
        menu.addAction(update_action)

        # Informações de sistema
        info_action = QAction("Informações do Sistema")
        info_action.triggered.connect(self.show_system_info)
        menu.addAction(info_action)

        # Executar menu
        menu.exec(self.mapToGlobal(self.rect().center()))

    def show_system_info(self):
        """Mostra informações dos sistemas de melhoria."""

        # Coletar informações de todos os sistemas
        info = {
            'error_handler': error_handler.error_handler.get_error_stats(),
            'recovery': recovery_manager.get_recovery_info(),
            'backup': backup_scheduler.get_backup_info(),
            'threads': thread_manager.get_thread_stats(),
            'updates': updater.get_update_status()
        }

        # Mostrar informações em diálogo
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton

        dialog = QDialog(self)
        dialog.setWindowTitle("Informações do Sistema")
        dialog.resize(600, 400)

        layout = QVBoxLayout(dialog)

        text_edit = QTextEdit()
        text_edit.setPlainText(str(info))
        layout.addWidget(text_edit)

        close_btn = QPushButton("Fechar")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def cleanup_on_exit(self):
        """Limpeza ao fechar aplicação."""

        try:
            # Parar sistemas automáticos
            self.recovery_manager.stop_auto_save()
            self.backup_manager.scheduler.stop_scheduler()
            self.auto_update_manager.stop_auto_check()

            # Forçar último salvamento
            self.recovery_manager.force_save_now()

            logging.info("Sistemas de melhoria finalizados")

        except Exception as e:
            logging.error(f"Erro na limpeza: {e}")

# Exemplo de uso melhorado do sistema de vendas
class SalesPageImproved:
    """Exemplo de como usar os novos sistemas na página de vendas."""

    def __init__(self, main_window):
        self.main_window = main_window

        # Usar error handler ao invés de QMessageBox diretamente
        self.error_handler = error_handler.error_handler

        # Usar loading manager para operações longas
        self.loading_manager = loading_manager

        # Usar thread manager para operações em background
        self.thread_manager = thread_manager

    def add_product_to_sale_improved(self, barcode: str):
        """Exemplo de adição de produto com validação e tratamento de erro."""

        # 1. Validar entrada
        is_valid, error_msg = validation.InputValidator.validate_barcode(barcode)
        if not is_valid:
            self.error_handler.handle_validation_error("Código de Barras", error_msg)
            return

        # 2. Buscar produto com cache
        try:
            product = database.get_product_by_barcode_cached(barcode)
            if not product:
                self.error_handler.show_error(
                    "Produto Não Encontrado",
                    f"Produto com código '{barcode}' não encontrado no banco de dados."
                )
                return

            # 3. Validar dados do produto
            product_data = {
                'description': product['description'],
                'price': product['price'],
                'stock': product['stock']
            }

            validation_result = validation.InputValidator.validate_product_data(product_data)
            if not validation_result.is_valid:
                error_messages = '\n'.join(validation_result.errors)
                self.error_handler.show_error(
                    "Dados do Produto Inválidos",
                    error_messages
                )
                return

            # 4. Adicionar produto com loading
            self.loading_manager.show_loading(
                "Adicionando produto à venda...",
                widget=self
            )

            # Simular processamento (em caso real, seria mais complexo)
            QTimer.singleShot(500, lambda: self._finish_add_product(product))

        except Exception as e:
            self.error_handler.show_error(
                "Erro Interno",
                "Erro ao processar produto",
                str(e)
            )

    def _finish_add_product(self, product):
        """Finaliza adição do produto."""
        self.loading_manager.hide_loading(widget=self)

        # Produto adicionado com sucesso
        QMessageBox.information(
            self,
            "Produto Adicionado",
            f"Produto '{product['description']}' adicionado à venda."
        )

    def finalize_sale_improved(self, sale_items: list, payments: list):
        """Exemplo de finalização de venda com sistemas melhorados."""

        # 1. Validar venda
        sale_data = {
            'items': sale_items,
            'payments': payments
        }

        validation_result = validation.InputValidator.validate_sale_data(sale_data)
        if not validation_result.is_valid:
            error_messages = '\n'.join(validation_result.errors)
            self.error_handler.show_error("Venda Inválida", error_messages)
            return

        # 2. Mostrar loading durante processamento
        self.loading_manager.show_loading(
            "Finalizando venda...",
            show_progress=True,
            progress_range=(0, 100),
            widget=self
        )

        # 3. Executar em thread para não travar interface
        from ui.worker import run_in_thread

        operation_id = run_in_thread(
            "finalize_sale",
            self._process_sale_in_background,
            sale_items,
            payments,
            progress_callback=True
        )

        # Conectar sinais de progresso
        # (Implementação seria conectada aos sinais do worker)

    def _process_sale_in_background(self, sale_items: list, payments: list, progress_callback=None):
        """Processa venda em background."""

        try:
            # Simular progresso
            if progress_callback:
                progress_callback(25, "Validando itens...")

            # Validar estoque
            for item in sale_items:
                # Verificar estoque disponível
                pass

            if progress_callback:
                progress_callback(50, "Registrando venda...")

            # Registrar venda no banco
            # (código existente seria usado aqui)

            if progress_callback:
                progress_callback(75, "Processando pagamentos...")

            # Processar pagamentos
            # (código existente seria usado aqui)

            if progress_callback:
                progress_callback(100, "Venda finalizada!")

            return True

        except Exception as e:
            logging.error(f"Erro no processamento da venda: {e}")
            raise

# Funções utilitárias para integração
def integrate_with_existing_main():
    """
    Guia passo-a-passo para integrar com main.py existente:

    1. Adicione os imports no topo do arquivo:
       import error_handler
       import validation
       from ui.loading_overlay import loading_manager
       from ui.worker import thread_manager
       import backup_scheduler
       import recovery_manager
       import build
       import updater

    2. Configure o error handler global:
       error_handler.setup_global_error_handler()

    3. Inicialize os sistemas na classe principal:
       self.recovery_manager = recovery_manager.recovery_manager
       self.backup_manager = backup_scheduler.backup_manager
       self.auto_update_manager = updater.auto_update_manager

    4. Inicie sistemas automáticos:
       self.recovery_manager.start_auto_save()
       self.backup_manager.scheduler.start_scheduler()
       self.auto_update_manager.start_auto_check()

    5. Substitua QMessageBox por error_handler.show_error() onde apropriado

    6. Use loading_manager para operações longas

    7. Use thread_manager para operações em background

    8. Adicione limpeza na saída:
       self.recovery_manager.stop_auto_save()
       self.backup_manager.scheduler.stop_scheduler()
       self.auto_update_manager.stop_auto_check()
    """

    print("Guia de integração disponível acima")

if __name__ == "__main__":
    # Exemplo de uso básico
    integrate_with_existing_main()
