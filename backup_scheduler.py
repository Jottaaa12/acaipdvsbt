import os
import shutil
import logging
import time
from datetime import datetime, timedelta
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import QMessageBox, QApplication
import database as db
from typing import Optional, List, Dict, Any

class BackupScheduler(QObject):
    """
    Sistema de backup automático para o PDV.
    Executa backups periódicos e limpa backups antigos automaticamente.
    """

    # Sinais
    backup_started = pyqtSignal(str)    # mensagem
    backup_completed = pyqtSignal(str)  # caminho do backup
    backup_failed = pyqtSignal(str)     # mensagem de erro
    cleanup_completed = pyqtSignal(int) # número de backups removidos

    def __init__(self):
        super().__init__()
        self.timer = QTimer()
        self.timer.timeout.connect(self.perform_backup)

        # Configurações
        self.backup_interval_hours = 24  # Intervalo padrão: 24 horas
        self.max_backups = 30           # Manter últimos 30 backups
        self.is_enabled = True          # Backup automático habilitado

        # Estado
        self.is_running = False
        self.last_backup_time = None
        self.next_backup_time = None

        # Carregar configurações do banco de dados
        self.load_settings()

    def load_settings(self):
        """Carrega configurações do banco de dados."""
        try:
            interval = db.load_setting('backup_interval_hours', '24')
            self.backup_interval_hours = int(interval)

            max_backups = db.load_setting('backup_max_backups', '30')
            self.max_backups = int(max_backups)

            enabled = db.load_setting('backup_auto_enabled', 'true')
            self.is_enabled = enabled.lower() == 'true'

            logging.info(f"Configurações de backup carregadas: intervalo={self.backup_interval_hours}h, max={self.max_backups}, enabled={self.is_enabled}")

        except Exception as e:
            logging.error(f"Erro ao carregar configurações de backup: {e}")

    def save_settings(self):
        """Salva configurações no banco de dados."""
        try:
            db.save_setting('backup_interval_hours', str(self.backup_interval_hours))
            db.save_setting('backup_max_backups', str(self.max_backups))
            db.save_setting('backup_auto_enabled', 'true' if self.is_enabled else 'false')
            logging.info("Configurações de backup salvas")
        except Exception as e:
            logging.error(f"Erro ao salvar configurações de backup: {e}")

    def start_scheduler(self):
        """Inicia o agendador de backups."""
        if not self.is_enabled:
            logging.info("Backup automático desabilitado")
            return

        self.calculate_next_backup()
        self.timer.start(self.get_interval_ms())

        logging.info(f"Agendador de backup iniciado - próximo backup: {self.next_backup_time}")

    def stop_scheduler(self):
        """Para o agendador de backups."""
        self.timer.stop()
        logging.info("Agendador de backup parado")

    def perform_backup(self):
        """Executa backup automático."""
        if self.is_running:
            logging.warning("Backup já em execução, ignorando")
            return

        try:
            self.is_running = True
            self.backup_started.emit("Iniciando backup automático...")

            # Executar backup
            success, result = db.create_backup()

            if success:
                backup_file = result
                self.last_backup_time = datetime.now()
                self.backup_completed.emit(backup_file)

                logging.info(f"Backup automático criado: {backup_file}")

                # Limpar backups antigos
                self.cleanup_old_backups()

                # Calcular próximo backup
                self.calculate_next_backup()

            else:
                error_msg = f"Erro no backup automático: {result}"
                self.backup_failed.emit(error_msg)
                logging.error(error_msg)

        except Exception as e:
            error_msg = f"Erro inesperado no backup automático: {e}"
            self.backup_failed.emit(error_msg)
            logging.error(error_msg, exc_info=True)
        finally:
            self.is_running = False

    def cleanup_old_backups(self, max_backups: Optional[int] = None) -> int:
        """
        Remove backups antigos, mantendo apenas os mais recentes.

        Args:
            max_backups: Número máximo de backups a manter (usa configuração se None)

        Returns:
            int: Número de backups removidos
        """
        if max_backups is None:
            max_backups = self.max_backups

        try:
            # Listar backups ordenados por data (mais recentes primeiro)
            backups = db.list_backups()

            if len(backups) <= max_backups:
                return 0  # Nada para limpar

            # Selecionar backups para remoção (manter os mais recentes)
            to_remove = backups[max_backups:]

            removed_count = 0
            for backup in to_remove:
                try:
                    os.remove(backup['path'])
                    removed_count += 1
                    logging.info(f"Backup antigo removido: {backup['filename']}")
                except Exception as e:
                    logging.error(f"Erro ao remover backup {backup['filename']}: {e}")

            if removed_count > 0:
                self.cleanup_completed.emit(removed_count)
                logging.info(f"Limpeza concluída: {removed_count} backups removidos")

            return removed_count

        except Exception as e:
            logging.error(f"Erro na limpeza de backups: {e}")
            return 0

    def calculate_next_backup(self):
        """Calcula quando será o próximo backup."""
        if self.last_backup_time:
            self.next_backup_time = self.last_backup_time + timedelta(hours=self.backup_interval_hours)
        else:
            self.next_backup_time = datetime.now() + timedelta(hours=self.backup_interval_hours)

    def get_interval_ms(self) -> int:
        """Retorna intervalo em milissegundos."""
        return self.backup_interval_hours * 60 * 60 * 1000

    def force_backup(self) -> bool:
        """
        Força execução imediata de backup.

        Returns:
            bool: True se backup foi iniciado
        """
        if self.is_running:
            logging.warning("Backup já em execução")
            return False

        # Executar backup imediatamente
        QTimer.singleShot(0, self.perform_backup)
        return True

    def get_status(self) -> Dict[str, Any]:
        """
        Retorna status atual do agendador.

        Returns:
            Dict com informações de status
        """
        return {
            'is_enabled': self.is_enabled,
            'is_running': self.is_running,
            'backup_interval_hours': self.backup_interval_hours,
            'max_backups': self.max_backups,
            'last_backup_time': self.last_backup_time,
            'next_backup_time': self.next_backup_time,
            'time_until_next': (
                self.next_backup_time - datetime.now()
                if self.next_backup_time else None
            )
        }

    def set_interval_hours(self, hours: int):
        """Define novo intervalo de backup."""
        if hours < 1:
            raise ValueError("Intervalo deve ser pelo menos 1 hora")

        self.backup_interval_hours = hours
        self.save_settings()
        self.restart_scheduler()

    def set_max_backups(self, max_backups: int):
        """Define número máximo de backups."""
        if max_backups < 1:
            raise ValueError("Deve manter pelo menos 1 backup")

        self.max_backups = max_backups
        self.save_settings()

    def enable_auto_backup(self, enabled: bool = True):
        """Habilita/desabilita backup automático."""
        self.is_enabled = enabled
        self.save_settings()

        if enabled:
            self.start_scheduler()
        else:
            self.stop_scheduler()

    def restart_scheduler(self):
        """Reinicia o agendador com novas configurações."""
        self.stop_scheduler()
        self.start_scheduler()

class BackupManager(QObject):
    """
    Gerenciador completo de backups para o PDV.
    Combina backup automático com operações manuais.
    """

    def __init__(self):
        super().__init__()
        self.scheduler = BackupScheduler()

        # Conectar sinais
        self.scheduler.backup_completed.connect(self._on_backup_completed)
        self.scheduler.backup_failed.connect(self._on_backup_failed)

    def stop(self):
        """Para o agendador de backup."""
        if self.scheduler:
            self.scheduler.stop_scheduler()

    def _on_backup_completed(self, backup_path: str):
        """Callback quando backup é concluído."""
        filename = os.path.basename(backup_path)
        QMessageBox.information(
            None,
            "Backup Concluído",
            f"Backup automático criado com sucesso:\n{filename}"
        )

    def _on_backup_failed(self, error_msg: str):
        """Callback quando backup falha."""
        QMessageBox.warning(
            None,
            "Erro no Backup",
            f"Falha no backup automático:\n{error_msg}"
        )

    def create_manual_backup(self) -> Optional[str]:
        """
        Cria backup manual.

        Returns:
            str: Caminho do backup ou None se falhou
        """
        try:
            success, result = db.create_backup()
            if success:
                QMessageBox.information(
                    None,
                    "Backup Criado",
                    f"Backup criado com sucesso:\n{os.path.basename(result)}"
                )
                return result
            else:
                QMessageBox.critical(
                    None,
                    "Erro no Backup",
                    f"Falha ao criar backup:\n{result}"
                )
                return None
        except Exception as e:
            QMessageBox.critical(
                None,
                "Erro",
                f"Erro inesperado no backup:\n{str(e)}"
            )
            return None

    def restore_backup_dialog(self) -> bool:
        """
        Mostra diálogo para restaurar backup.

        Returns:
            bool: True se restauração foi iniciada
        """
        try:
            # Listar backups disponíveis
            backups = db.list_backups()

            if not backups:
                QMessageBox.information(
                    None,
                    "Sem Backups",
                    "Não há backups disponíveis para restauração."
                )
                return False

            # Criar lista de opções
            options = []
            for backup in backups:
                created_str = backup['created'].strftime('%d/%m/%Y %H:%M')
                size_mb = backup['size'] / (1024 * 1024)
                options.append(f"{backup['filename']} ({created_str} - {size_mb:.1f} MB)")

            # Mostrar diálogo de seleção
            from PyQt6.QtWidgets import QInputDialog

            choice, ok = QInputDialog.getItem(
                None,
                "Restaurar Backup",
                "Selecione o backup para restaurar:",
                options,
                0,
                False
            )

            if ok and choice:
                # Encontrar backup selecionado
                selected_backup = None
                for backup in backups:
                    created_str = backup['created'].strftime('%d/%m/%Y %H:%M')
                    size_mb = backup['size'] / (1024 * 1024)
                    option_str = f"{backup['filename']} ({created_str} - {size_mb:.1f} MB)"

                    if choice == option_str:
                        selected_backup = backup
                        break

                if selected_backup:
                    # Confirmar restauração
                    msg = QMessageBox()
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.setWindowTitle("Confirmar Restauração")
                    msg.setText("Esta operação irá substituir o banco de dados atual.")
                    msg.setInformativeText(
                        "Um backup do banco atual será criado automaticamente.\n\n"
                        f"Backup selecionado: {selected_backup['filename']}\n"
                        f"Data: {selected_backup['created'].strftime('%d/%m/%Y %H:%M')}\n\n"
                        "Deseja continuar?"
                    )

                    if msg.exec() == QMessageBox.StandardButton.Yes:
                        return self.restore_backup(selected_backup['path'])

            return False

        except Exception as e:
            QMessageBox.critical(
                None,
                "Erro",
                f"Erro ao restaurar backup:\n{str(e)}"
            )
            return False

    def restore_backup(self, backup_path: str) -> bool:
        """
        Restaura backup específico.

        Args:
            backup_path: Caminho completo do arquivo de backup

        Returns:
            bool: True se restauração foi bem-sucedida
        """
        try:
            success, result = db.restore_backup(backup_path)

            if success:
                QMessageBox.information(
                    None,
                    "Restauração Concluída",
                    "Backup restaurado com sucesso!\n\n"
                    "A aplicação será reiniciada para aplicar as alterações."
                )

                # Reiniciar aplicação
                QApplication.quit()
                return True
            else:
                QMessageBox.critical(
                    None,
                    "Erro na Restauração",
                    f"Falha ao restaurar backup:\n{result}"
                )
                return False

        except Exception as e:
            QMessageBox.critical(
                None,
                "Erro",
                f"Erro inesperado na restauração:\n{str(e)}"
            )
            return False

    def show_backup_settings(self) -> None:
        """Mostra diálogo de configurações de backup."""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                   QSpinBox, QCheckBox, QPushButton, QGroupBox)

        dialog = QDialog()
        dialog.setWindowTitle("Configurações de Backup")
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)

        # Grupo de configurações automáticas
        auto_group = QGroupBox("Backup Automático")
        auto_layout = QVBoxLayout(auto_group)

        # Checkbox para habilitar/desabilitar
        self.enable_checkbox = QCheckBox("Habilitar backup automático")
        self.enable_checkbox.setChecked(self.scheduler.is_enabled)
        auto_layout.addWidget(self.enable_checkbox)

        # Configuração de intervalo
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Intervalo (horas):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 168)  # 1 hora até 1 semana
        self.interval_spin.setValue(self.scheduler.backup_interval_hours)
        interval_layout.addWidget(self.interval_spin)
        auto_layout.addLayout(interval_layout)

        layout.addWidget(auto_group)

        # Grupo de limpeza automática
        cleanup_group = QGroupBox("Limpeza Automática")
        cleanup_layout = QVBoxLayout(cleanup_group)

        cleanup_layout2 = QHBoxLayout()
        cleanup_layout2.addWidget(QLabel("Manter últimos backups:"))
        self.max_backups_spin = QSpinBox()
        self.max_backups_spin.setRange(1, 100)
        self.max_backups_spin.setValue(self.scheduler.max_backups)
        cleanup_layout2.addWidget(self.max_backups_spin)
        cleanup_layout.addLayout(cleanup_layout2)

        layout.addWidget(cleanup_group)

        # Botões
        buttons_layout = QHBoxLayout()

        force_btn = QPushButton("Forçar Backup Agora")
        force_btn.clicked.connect(lambda: self._force_backup_from_dialog(dialog))
        buttons_layout.addWidget(force_btn)

        buttons_layout.addStretch()

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(dialog.accept)
        buttons_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(dialog.reject)
        buttons_layout.addWidget(cancel_btn)

        layout.addLayout(buttons_layout)

        # Conectar sinais
        self.enable_checkbox.toggled.connect(self.interval_spin.setEnabled)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Aplicar configurações
            self.scheduler.enable_auto_backup(self.enable_checkbox.isChecked())
            self.scheduler.set_interval_hours(self.interval_spin.value())
            self.scheduler.set_max_backups(self.max_backups_spin.value())

    def _force_backup_from_dialog(self, dialog):
        """Força backup a partir do diálogo de configurações."""
        dialog.accept()  # Fecha diálogo primeiro

        # Pequeno delay para diálogo fechar
        QTimer.singleShot(100, lambda: self.create_manual_backup())

    def get_backup_info(self) -> Dict[str, Any]:
        """Retorna informações sobre backups."""
        try:
            backups = db.list_backups()

            total_size = sum(backup['size'] for backup in backups)
            total_size_mb = total_size / (1024 * 1024)

            return {
                'total_backups': len(backups),
                'total_size_mb': round(total_size_mb, 2),
                'oldest_backup': backups[-1]['created'] if backups else None,
                'newest_backup': backups[0]['created'] if backups else None,
                'scheduler_status': self.scheduler.get_status()
            }
        except Exception as e:
            logging.error(f"Erro ao obter informações de backup: {e}")
            return {'error': str(e)}

# Instância global do BackupManager
backup_manager = BackupManager()

# Funções de conveniência
def create_backup() -> Optional[str]:
    """Cria backup manual."""
    return backup_manager.create_manual_backup()

def restore_backup_dialog() -> bool:
    """Mostra diálogo de restauração."""
    return backup_manager.restore_backup_dialog()

def show_backup_settings():
    """Mostra configurações de backup."""
    backup_manager.show_backup_settings()

def get_backup_info() -> Dict[str, Any]:
    """Obtém informações de backup."""
    return backup_manager.get_backup_info()

def force_backup() -> bool:
    """Força backup imediato."""
    return backup_manager.scheduler.force_backup()
