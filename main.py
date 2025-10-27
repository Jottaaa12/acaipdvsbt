__version__ = "1.1.0"

import os
import sys
import tempfile
import locale
import logging

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
import migration
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
    
    def init_database(self):
        # Inicializa e migra o banco de dados, se necessario
        try:
            # Garante que todas as tabelas existam antes de verificar as migrações.
            # A funcao create_tables() usa "CREATE TABLE IF NOT EXISTS", entao e seguro executa-la sempre.
            db.create_tables()
            logging.info("Verificacao de tabelas concluida.")

            logging.info("Verificando a necessidade de migracao do banco de dados...")
            if migration.is_any_migration_needed():
                logging.warning("Migracao do banco de dados necessaria. Executando automaticamente...")
                
                # Mostra uma mensagem informativa nao-interativa
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Icon.Information)
                msg_box.setWindowTitle("Atualizando Banco de Dados")
                msg_box.setText("O banco de dados esta sendo atualizado. Por favor, aguarde...")
                msg_box.setStandardButtons(QMessageBox.StandardButton.NoButton) # Sem botoes
                msg_box.show()
                QApplication.processEvents() # Garante que a mensagem seja exibida

                try:
                    migration.run_all_migrations()
                    logging.info("Migracao do banco de dados concluida com sucesso.")
                    msg_box.close() # Fecha a mensagem de "aguarde"
                    QMessageBox.information(None, "Atualizacao Concluida", "O banco de dados foi atualizado com sucesso!")
                except Exception as e:
                    logging.error(f"Falha critica durante a migracao automatica: {e}", exc_info=True)
                    msg_box.close()
                    QMessageBox.critical(None, "Erro na Atualizacao", f"Ocorreu um erro grave ao atualizar o banco de dados.\nO programa nao pode continuar.\n\nErro: {e}")
                    sys.exit(1)
            else:
                logging.info("Banco de dados ja esta atualizado.")

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
        logging.getLogger().setLevel(logging.INFO)
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

    if updater.check_for_updates(__version__):
        pass

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