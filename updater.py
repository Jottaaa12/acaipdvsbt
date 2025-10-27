import time
import requests
import webbrowser
import json
import os
import logging
import subprocess
import shutil
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox, QApplication, QProgressDialog
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, QObject
from typing import Optional, Dict, Any, Tuple
import database as db

class UpdateChecker(QObject):
    """
    Verificador avançado de atualizações para o PDV.
    Suporta verificação em background, download automático e instalação.
    """

    # Sinais
    update_available = pyqtSignal(str, str)  # versão, descrição
    no_update_available = pyqtSignal()
    update_check_failed = pyqtSignal(str)     # mensagem de erro
    download_progress = pyqtSignal(int)      # progresso (0-100)
    download_completed = pyqtSignal(str)     # caminho do arquivo
    download_failed = pyqtSignal(str)        # mensagem de erro

    def __init__(self):
        super().__init__()
        self.current_version = self._get_current_version()
        self.update_info = {}

        # Configurações
        self.repo_url = "https://api.github.com/repos/Jottaaa12/acaipdvsbt"
        self.raw_url = "https://raw.githubusercontent.com/Jottaaa12/acaipdvsbt/refs/heads/main"
        self.download_base_url = "https://github.com/Jottaaa12/acaipdvsbt/releases/download"

        # Estado
        self.is_checking = False
        self.is_downloading = False

    def _get_current_version(self) -> str:
        """Obtém versão atual da aplicação."""
        try:
            version_file = Path("versao.txt")
            if version_file.exists():
                return version_file.read_text().strip()
        except Exception as e:
            logging.error(f"Erro ao ler versão atual: {e}")
        return "1.0.0"

    def check_for_updates(self, silent: bool = False) -> bool:
        """
        Verifica se há atualizações disponíveis.

        Args:
            silent: Se deve mostrar mensagens de erro

        Returns:
            bool: True se há atualização disponível
        """
        if self.is_checking:
            logging.warning("Verificação já em andamento")
            return False

        try:
            self.is_checking = True

            # Verificar conectividade primeiro
            if not self._check_internet_connection():
                if not silent:
                    self.update_check_failed.emit("Sem conexão com a internet")
                return False

            # Obter informações da versão mais recente
            version_info = self._get_latest_version_info()

            if not version_info:
                if not silent:
                    self.update_check_failed.emit("Erro ao obter informações de versão")
                return False

            latest_version = version_info.get('version', '')
            description = version_info.get('description', '')

            # Comparar versões
            if self._compare_versions(latest_version, self.current_version) > 0:
                self.update_info = version_info
                self.update_available.emit(latest_version, description)
                logging.info(f"Atualização disponível: {latest_version}")
                return True
            else:
                self.no_update_available.emit()
                logging.info("Nenhuma atualização disponível")
                return False

        except Exception as e:
            error_msg = f"Erro ao verificar atualizações: {e}"
            if not silent:
                self.update_check_failed.emit(error_msg)
            logging.error(error_msg)
            return False
        finally:
            self.is_checking = False

    def _check_internet_connection(self) -> bool:
        """Verifica conectividade com a internet."""
        try:
            response = requests.get("https://www.google.com", timeout=5)
            return response.status_code == 200
        except:
            return False

    def _get_latest_version_info(self) -> Optional[Dict[str, Any]]:
        """Obtém informações da versão mais recente."""
        try:
            # Obter versão do arquivo remoto
            version_url = f"{self.raw_url}/versao.txt"
            response = requests.get(version_url, timeout=10)
            response.raise_for_status()
            latest_version = response.text.strip()

            # Obter informações adicionais se disponível
            info_url = f"{self.raw_url}/update_info.json"
            try:
                response = requests.get(info_url, timeout=10)
                if response.status_code == 200:
                    info_data = response.json()
                    return {
                        'version': latest_version,
                        'description': info_data.get('description', ''),
                        'release_date': info_data.get('release_date', ''),
                        'critical': info_data.get('critical', False),
                        'features': info_data.get('features', []),
                        'fixes': info_data.get('fixes', [])
                    }
            except:
                pass  # Arquivo de informações não existe

            # Retornar informações básicas
            return {
                'version': latest_version,
                'description': 'Nova versão disponível',
                'critical': False,
                'features': [],
                'fixes': []
            }

        except Exception as e:
            logging.error(f"Erro ao obter informações de versão: {e}")
            return None

    def _compare_versions(self, version1: str, version2: str) -> int:
        """
        Compara duas versões.

        Returns:
            -1: version1 < version2
             0: version1 == version2
             1: version1 > version2
        """
        try:
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]

            # Pad com zeros para comparar
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))

            for i in range(max_len):
                if v1_parts[i] < v2_parts[i]:
                    return -1
                elif v1_parts[i] > v2_parts[i]:
                    return 1

            return 0

        except Exception:
            return 0  # Considerar iguais em caso de erro

    def download_update(self, version: str) -> bool:
        """
        Faz download da atualização.

        Args:
            version: Versão para download

        Returns:
            bool: True se download foi iniciado
        """
        if self.is_downloading:
            logging.warning("Download já em andamento")
            return False

        try:
            self.is_downloading = True

            # Construir URL de download
            download_url = f"{self.download_base_url}/v{version}/PDV.Moderno.exe"

            # Criar diretório de downloads
            download_dir = Path("downloads")
            download_dir.mkdir(exist_ok=True)

            # Caminho do arquivo
            filename = f"PDV.Moderno.v{version}.exe"
            filepath = download_dir / filename

            # Iniciar download em thread
            from ui.worker import run_in_thread

            operation_id = run_in_thread(
                "download_update",
                self._perform_download,
                download_url,
                str(filepath),
                progress_callback=True
            )

            logging.info(f"Download iniciado: {operation_id}")
            return True

        except Exception as e:
            logging.error(f"Erro ao iniciar download: {e}")
            self.download_failed.emit(str(e))
            return False
        finally:
            self.is_downloading = False

    def _perform_download(self, url: str, filepath: str, progress_callback=None):
        """Executa download do arquivo."""
        try:
            # Fazer download com progresso
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))

            with open(filepath, 'wb') as f:
                downloaded = 0

                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback and total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            progress_callback(progress, f"Baixando... {progress}%")

            # Verificar integridade do arquivo
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                self.download_completed.emit(filepath)
                logging.info(f"Download concluído: {filepath}")
                return filepath
            else:
                raise Exception("Arquivo baixado inválido")

        except Exception as e:
            logging.error(f"Erro no download: {e}")
            if progress_callback:
                progress_callback(-1, f"Erro: {str(e)}")
            raise

    def install_update(self, installer_path: str) -> bool:
        """
        Instala atualização baixada.

        Args:
            installer_path: Caminho do instalador

        Returns:
            bool: True se instalação foi iniciada
        """
        try:
            if not os.path.exists(installer_path):
                QMessageBox.critical(
                    None,
                    "Erro",
                    "Arquivo de instalação não encontrado."
                )
                return False

            # Backup da versão atual
            current_exe = "PDV.Moderno.exe"
            if os.path.exists(current_exe):
                backup_name = f"PDV.Moderno.backup.{int(time.time())}.exe"
                shutil.copy2(current_exe, backup_name)
                logging.info(f"Backup criado: {backup_name}")

            # Executar instalador
            subprocess.Popen([installer_path], shell=True)

            # Fechar aplicação atual
            QTimer.singleShot(1000, QApplication.quit)

            return True

        except Exception as e:
            logging.error(f"Erro na instalação: {e}")
            QMessageBox.critical(
                None,
                "Erro na Instalação",
                f"Erro ao instalar atualização:\n{str(e)}"
            )
            return False

    def get_update_info(self) -> Dict[str, Any]:
        """Retorna informações sobre atualizações."""
        return {
            'current_version': self.current_version,
            'latest_version': self.update_info.get('version', ''),
            'is_update_available': bool(self.update_info),
            'is_critical': self.update_info.get('critical', False),
            'description': self.update_info.get('description', ''),
            'features': self.update_info.get('features', []),
            'fixes': self.update_info.get('fixes', [])
        }

class AutoUpdateManager(QObject):
    """
    Gerenciador completo de auto-updates.
    Combina verificação automática com configurações do usuário.
    """

    def __init__(self):
        super().__init__()
        self.update_checker = UpdateChecker()

        # Timer para verificação automática
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._perform_auto_check)

        # Configurações
        self.auto_check_enabled = True
        self.auto_check_interval = 24 * 60 * 60 * 1000  # 24 horas
        self.auto_download_critical = True

        # Estado
        self.is_checking = False

        # Carregar configurações
        self.load_settings()

        # Conectar sinais
        self.update_checker.update_available.connect(self._on_update_available)
        self.update_checker.no_update_available.connect(self._on_no_update_available)
        self.update_checker.update_check_failed.connect(self._on_check_failed)

    def load_settings(self):
        """Carrega configurações do banco de dados."""
        try:
            enabled = db.load_setting('auto_update_enabled', 'true')
            self.auto_check_enabled = enabled.lower() == 'true'

            interval = db.load_setting('auto_update_interval', '86400000')  # 24h em ms
            self.auto_check_interval = int(interval)

            critical_download = db.load_setting('auto_download_critical', 'true')
            self.auto_download_critical = critical_download.lower() == 'true'

            logging.info(f"Configurações de auto-update carregadas: enabled={self.auto_check_enabled}, interval={self.auto_check_interval}")

        except Exception as e:
            logging.error(f"Erro ao carregar configurações de auto-update: {e}")

    def save_settings(self):
        """Salva configurações no banco de dados."""
        try:
            db.save_setting('auto_update_enabled', 'true' if self.auto_check_enabled else 'false')
            db.save_setting('auto_update_interval', str(self.auto_check_interval))
            db.save_setting('auto_download_critical', 'true' if self.auto_download_critical else 'false')
            logging.info("Configurações de auto-update salvas")
        except Exception as e:
            logging.error(f"Erro ao salvar configurações de auto-update: {e}")

    def start_auto_check(self):
        """Inicia verificação automática de updates."""
        if not self.auto_check_enabled:
            logging.info("Auto-check de updates desabilitado")
            return

        self.check_timer.start(self.auto_check_interval)
        logging.info(f"Auto-check iniciado (intervalo: {self.auto_check_interval}ms)")

    def stop_auto_check(self):
        """Para verificação automática de updates."""
        self.check_timer.stop()
        logging.info("Auto-check parado")

    def _perform_auto_check(self):
        """Executa verificação automática."""
        if self.is_checking:
            return

        self.is_checking = True

        try:
            # Verificar silenciosamente
            has_update = self.update_checker.check_for_updates(silent=True)

            if has_update:
                update_info = self.update_checker.get_update_info()

                # Se for atualização crítica, baixar automaticamente
                if update_info.get('is_critical') and self.auto_download_critical:
                    logging.info("Atualização crítica detectada, iniciando download automático")
                    self.update_checker.download_update(update_info['latest_version'])

        except Exception as e:
            logging.error(f"Erro no auto-check: {e}")
        finally:
            self.is_checking = False

    def _on_update_available(self, version: str, description: str):
        """Callback quando atualização está disponível."""
        QMessageBox.information(
            None,
            "Atualização Disponível",
            f"Uma nova versão ({version}) está disponível!\n\n{description}\n\n"
            "Deseja fazer download agora?"
        )

    def _on_no_update_available(self):
        """Callback quando não há atualização."""
        logging.info("Nenhuma atualização disponível")

    def _on_check_failed(self, error_msg: str):
        """Callback quando verificação falha."""
        logging.warning(f"Verificação de atualização falhou: {error_msg}")

    def check_now(self) -> bool:
        """Força verificação imediata."""
        return self.update_checker.check_for_updates(silent=False)

    def download_update(self, version: str) -> bool:
        """Inicia download de versão específica."""
        return self.update_checker.download_update(version)

    def install_update(self, installer_path: str) -> bool:
        """Instala atualização baixada."""
        return self.update_checker.install_update(installer_path)

    def set_auto_check_interval(self, interval_ms: int):
        """Define intervalo de verificação automática."""
        if interval_ms < 3600000:  # Mínimo 1 hora
            raise ValueError("Intervalo mínimo é 1 hora")

        self.auto_check_interval = interval_ms
        self.save_settings()
        self.restart_auto_check()

    def enable_auto_check(self, enabled: bool = True):
        """Habilita/desabilita verificação automática."""
        self.auto_check_enabled = enabled
        self.save_settings()

        if enabled:
            self.start_auto_check()
        else:
            self.stop_auto_check()

    def restart_auto_check(self):
        """Reinicia auto-check com novas configurações."""
        self.stop_auto_check()
        self.start_auto_check()

    def get_status(self) -> Dict[str, Any]:
        """Retorna status do sistema de updates."""
        return {
            'auto_check_enabled': self.auto_check_enabled,
            'auto_check_interval_ms': self.auto_check_interval,
            'auto_download_critical': self.auto_download_critical,
            'is_checking': self.is_checking,
            'current_version': self.update_checker.current_version,
            'update_info': self.update_checker.get_update_info()
        }

# Instâncias globais
update_checker = UpdateChecker()
auto_update_manager = AutoUpdateManager()

# Funções de compatibilidade (mantidas para código existente)
def check_for_updates(current_version: str) -> bool:
    """
    Verifica atualizações (função de compatibilidade).

    Args:
        current_version: Versão atual da aplicação

    Returns:
        bool: True se há atualização disponível
    """
    update_checker.current_version = current_version
    return update_checker.check_for_updates(silent=False)

# Funções de conveniência aprimoradas
def check_for_updates_silent() -> bool:
    """Verifica atualizações silenciosamente."""
    return update_checker.check_for_updates(silent=True)

def download_latest_update() -> bool:
    """Faz download da atualização mais recente."""
    update_info = update_checker.get_update_info()
    if update_info.get('is_update_available'):
        return update_checker.download_update(update_info['latest_version'])
    return False

def install_downloaded_update(installer_path: str) -> bool:
    """Instala atualização baixada."""
    return update_checker.install_update(installer_path)

def show_update_settings():
    """Mostra diálogo de configurações de update."""
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QSpinBox, QCheckBox, QPushButton, QGroupBox)

    dialog = QDialog()
    dialog.setWindowTitle("Configurações de Atualização")
    dialog.setModal(True)

    layout = QVBoxLayout(dialog)

    # Grupo de verificação automática
    auto_group = QGroupBox("Verificação Automática")
    auto_layout = QVBoxLayout(auto_group)

    # Checkbox para habilitar
    enable_checkbox = QCheckBox("Verificar atualizações automaticamente")
    enable_checkbox.setChecked(auto_update_manager.auto_check_enabled)
    auto_layout.addWidget(enable_checkbox)

    # Configuração de intervalo
    interval_layout = QHBoxLayout()
    interval_layout.addWidget(QLabel("Intervalo (horas):"))
    interval_spin = QSpinBox()
    interval_spin.setRange(1, 168)  # 1 hora até 1 semana
    interval_spin.setValue(auto_update_manager.auto_check_interval // (60 * 60 * 1000))
    interval_layout.addWidget(interval_spin)
    auto_layout.addLayout(interval_layout)

    layout.addWidget(auto_group)

    # Grupo de download automático
    download_group = QGroupBox("Download Automático")
    download_layout = QVBoxLayout(download_group)

    critical_checkbox = QCheckBox("Baixar automaticamente atualizações críticas")
    critical_checkbox.setChecked(auto_update_manager.auto_download_critical)
    download_layout.addWidget(critical_checkbox)

    layout.addWidget(download_group)

    # Botões
    buttons_layout = QHBoxLayout()

    check_now_btn = QPushButton("Verificar Agora")
    check_now_btn.clicked.connect(lambda: auto_update_manager.check_now())
    buttons_layout.addWidget(check_now_btn)

    buttons_layout.addStretch()

    ok_btn = QPushButton("OK")
    ok_btn.clicked.connect(dialog.accept)
    buttons_layout.addWidget(ok_btn)

    cancel_btn = QPushButton("Cancelar")
    cancel_btn.clicked.connect(dialog.reject)
    buttons_layout.addWidget(cancel_btn)

    layout.addLayout(buttons_layout)

    # Conectar sinais
    enable_checkbox.toggled.connect(interval_spin.setEnabled)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        # Aplicar configurações
        auto_update_manager.enable_auto_check(enable_checkbox.isChecked())
        hours = interval_spin.value()
        auto_update_manager.set_auto_check_interval(hours * 60 * 60 * 1000)
        auto_update_manager.auto_download_critical = critical_checkbox.isChecked()
        auto_update_manager.save_settings()

def get_update_status() -> Dict[str, Any]:
    """Obtém status completo do sistema de updates."""
    return {
        'checker_status': update_checker.get_update_info(),
        'manager_status': auto_update_manager.get_status()
    }
