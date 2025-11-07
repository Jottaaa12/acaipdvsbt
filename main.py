__version__ = "1.1.0"

import os
import sys
import tempfile
import locale
import logging
import yoyo

from data.connection import DB_FILE

# Configuracao basica de logging para capturar tudo desde o inicio
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - [%(levelname)s] - %(message)s')

# Workaround for python-escpos issue on Windows with non-ASCII usernames
if sys.platform == "win32":
    cache_dir = os.path.join(os.getcwd(), ".escpos-cache")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    os.environ["ESCPOS_CAPABILITIES_PICKLE_DIR"] = cache_dir

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer
from ui.worker import run_in_thread
import updater

# Import pyi_splash com fallback para desenvolvimento
try:
    import pyi_splash
    PYI_SPLASH_AVAILABLE = True
except ImportError:
    PYI_SPLASH_AVAILABLE = False

class CustomSplashScreen:
    def __init__(self):
        self.splash = None

    def show(self):
        # Mostra splash screen customizado
        if PYI_SPLASH_AVAILABLE:
            return
        from PyQt6.QtWidgets import QSplashScreen
        from PyQt6.QtGui import QPixmap, QFont, QColor, QPainter
        from PyQt6.QtCore import Qt, QTimer
        self.splash = QSplashScreen()
        self.splash.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.splash.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.splash.resize(400, 200)
        screen_geometry = QApplication.primaryScreen().geometry()
        self.splash.move(
            (screen_geometry.width() - self.splash.width()) // 2,
            (screen_geometry.height() - self.splash.height()) // 2
        )
        self.splash.show()
        self.splash.showMessage(
            "PDV Moderno\nCarregando...",
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
            QColor(255, 255, 255)
        )
        QApplication.processEvents()

    def close(self):
        # Fecha splash screen
        if self.splash and not PYI_SPLASH_AVAILABLE:
            self.splash.close()
            self.splash = None

splash_screen = CustomSplashScreen()

from ui.modern_main_window import ModernMainWindow as MainWindow
from ui.modern_login import ModernLoginDialog as LoginDialog
import database as db
import updater
from log_handler import QtLogHandler

class PDVApplication:
    def __init__(self, app):
        self.app = app
        self.current_user = None
        self.main_window = None
        self.login_dialog = None
        self.setup_app_style()
        self.init_database()
        
    def setup_app_style(self):
        # Configura o estilo global da aplicacao
        self.app.setStyleSheet('''
            QMainWindow {
                background-color: #f8f9fa;
            }
            QTabWidget::pane {
                border: 1px solid #dee2e6;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #e9ecef;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 2px solid #007bff;
            }
            QTabBar::tab:hover {
                background-color: #f8f9fa;
            }
        ''')
    
    def start_background_update_check(self):
        """Inicia a verificação de atualização em uma thread separada."""
        logging.info("Iniciando verificação de atualização em segundo plano...")
        updater.update_checker.current_version = __version__
        run_in_thread(
            "update_check",
            updater.update_checker.check_for_updates,
            silent=True
        )

    def init_database(self):
        # (código anterior da função init_database...)
        try:
            # Garante que o caminho do DB exista
            db_path = DB_FILE # Verifique se DB_FILE está importado corretamente

            logging.info("Verificando migrações do banco de dados (yoyo)...")

            # 1. Configura o backend do yoyo
            # Usamos f'sqlite:///{db_path}' para um caminho absoluto
            backend = yoyo.get_backend(f'sqlite:///{db_path}')

            # 2. Lê os scripts da nossa pasta 'migrations'
            migrations = yoyo.read_migrations('./migrations')

            # 3. Descobre quais migrações precisam ser aplicadas
            to_apply = backend.to_apply(migrations)

            if to_apply:
                logging.warning(f"Migrações pendentes detectadas: {[m.id for m in to_apply]}")

                # Mostra a mensagem "Atualizando..." (como você já faz)
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Icon.Information)
                msg_box.setWindowTitle("Atualizando Banco de Dados")
                msg_box.setText("O banco de dados esta sendo atualizado. Por favor, aguarde...")
                msg_box.setStandardButtons(QMessageBox.StandardButton.NoButton)
                msg_box.show()
                QApplication.processEvents()

                try:
                    # 4. Aplica as migrações pendentes, com tratamento para colunas duplicadas
                    for migration in to_apply:
                        try:
                            backend.apply_one(migration)
                        except db.sqlite3.OperationalError as e:
                            error_message = str(e).lower()
                            if 'duplicate column' in error_message or 'already another table or index with this name' in error_message:
                                logging.warning(f"A migração {migration.id} falhou porque parece já ter sido aplicada. Marcando como concluída. Erro: {e}")
                                backend.mark_migrations([migration])
                            else:
                                raise  # Outros erros de DB são relançados

                    logging.info("Todas as migrações pendentes foram processadas.")
                    msg_box.close()
                    QMessageBox.information(None, "Atualização Concluída", "O banco de dados foi atualizado com sucesso!")

                except Exception as e:
                    logging.error(f"Falha crítica durante a migração (yoyo): {e}", exc_info=True)
                    msg_box.close()
                    QMessageBox.critical(None, "Erro na Atualização", f"Ocorreu um erro grave ao atualizar o banco de dados.\nO programa nao pode continuar.\n\nErro: {e}")
                    sys.exit(1)

            else:
                logging.info("Banco de dados já está atualizado.")

            logging.info("Banco de dados inicializado com sucesso.")

        except db.sqlite3.Error as e:
            QMessageBox.critical(None, "Erro de Banco de Dados", 
                               f"Erro ao inicializar o banco de dados SQLite:\n{str(e)}")
            sys.exit(1)
        except Exception as e:
            QMessageBox.critical(None, "Erro Fatal", 
                               f"Um erro inesperado ocorreu na inicializacao:\n{str(e)}")
            sys.exit(1)
    
    def show_login(self):
        # Exibe a tela de login
        self.login_dialog = LoginDialog()
        self.login_dialog.login_successful.connect(self.on_login_successful)
        
        if self.login_dialog.exec() != LoginDialog.DialogCode.Accepted:
            sys.exit(0)
    
    def on_login_successful(self, user_data):
        # Callback executado quando login e bem-sucedido
        self.current_user = user_data
        self.main_window = MainWindow(self.current_user)

        # Conecta o sinal de atualização disponível a um slot na janela principal
        updater.update_checker.update_available.connect(self.main_window.show_update_notification)

        self.setup_logging(self.main_window.log_console_dialog.append_log)
        logging.info(f"Login realizado: {user_data['username']} ({user_data['role']})")
        self.main_window.logout_requested.connect(self.on_logout_requested)
        self.main_window.showMaximized()

        try:
            pyi_splash.close()
        except:
            pass
        
        if self.login_dialog:
            self.login_dialog.close()

        # Inicia a verificação de atualização em segundo plano
        self.start_background_update_check()

        if self.current_user.get('role') == 'gerente':
            try:
                from integrations.whatsapp_manager import WhatsAppManager
                
                logging.info("Iniciando integrações (WhatsApp)...")
                
                # Inicia a conexão automática com o WhatsApp
                whatsapp_manager = WhatsAppManager.get_instance()
                if not whatsapp_manager.is_ready:
                    whatsapp_manager.connect()
            except Exception as e:
                logging.error(f"Erro ao iniciar integrações automáticas: {e}")
    
    def setup_logging(self, log_slot):
        # Configura o sistema de logging
        log_handler = QtLogHandler()
        log_handler.log_updated.connect(log_slot)
        log_format = '%(asctime)s - [%(levelname)-8s] - %(message)s (%(filename)s:%(lineno)d)'
        formatter = logging.Formatter(log_format, datefmt='%H:%M:%S')
        log_handler.setFormatter(formatter)
        logging.getLogger().addHandler(log_handler)
        logging.getLogger().setLevel(logging.DEBUG)
        logging.info("Aplicacao iniciada com sucesso.")
        logging.info(f"Usuario '{self.current_user['username']}' logado. Nivel de acesso: '{self.current_user['role']}'.")
    
    def on_logout_requested(self):
        # Callback executado quando logout e solicitado
        if self.current_user:
            db.log_user_session(self.current_user['id'], 'logout')
            logging.info(f"Logout realizado: {self.current_user['username']}")
        
        if self.main_window:
            self.main_window.close()
            self.main_window = None
        
        self.current_user = None
        QTimer.singleShot(100, self.show_login)
    
    def run(self):
        # Executa a aplicacao
        self.show_login()
        return self.app.exec()

def main():
    # Funcao principal da aplicacao
    logging.info("Iniciando a aplicacao PDV Moderno...")
    app = QApplication(sys.argv)

    try:
        locale.setlocale(locale.LC_ALL, '')
        logging.info(f"Locale do sistema definido para: {locale.getlocale()}")
    except locale.Error as e:
        logging.warning(f"Aviso: Nao foi possivel definir o locale do sistema: {e}")

    try:
        logging.info("Criando instancia da PDVApplication...")
        pdv_app = PDVApplication(app)
        logging.info("Executando a aplicacao...")
        exit_code = pdv_app.run()
        logging.info(f"Aplicacao encerrada com codigo de saida: {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        logging.error("Erro fatal na execucao da aplicacao.", exc_info=True)
        if 'pdv_app' not in locals() or not pdv_app.app:
            app = QApplication(sys.argv)
        QMessageBox.critical(None, "Erro Fatal", 
                           f"Erro inesperado na aplicacao:\n{str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
