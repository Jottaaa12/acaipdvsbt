__version__ = "1.1.0"

import os
import sys
import tempfile
import locale

# Workaround for python-escpos issue on Windows with non-ASCII usernames
# See: https://github.com/python-escpos/python-escpos/issues/484
# The library tries to create a temp dir in the user's home folder,
# which can fail if the username has special characters.
# We force it to use a local .cache directory instead.
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

# Splash screen customizado para desenvolvimento
class CustomSplashScreen:
    def __init__(self):
        self.splash = None

    def show(self):
        """Mostra splash screen customizado."""
        if PYI_SPLASH_AVAILABLE:
            return

        from PyQt6.QtWidgets import QSplashScreen
        from PyQt6.QtGui import QPixmap, QFont, QColor, QPainter
        from PyQt6.QtCore import Qt, QTimer

        # Criar splash screen simples
        self.splash = QSplashScreen()

        # Configurar aparência
        self.splash.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.splash.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Definir tamanho
        self.splash.resize(400, 200)

        # Centralizar na tela
        screen_geometry = QApplication.primaryScreen().geometry()
        self.splash.move(
            (screen_geometry.width() - self.splash.width()) // 2,
            (screen_geometry.height() - self.splash.height()) // 2
        )

        # Mostrar mensagem
        self.splash.show()
        self.splash.showMessage(
            "PDV Moderno\nCarregando...",
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
            QColor(255, 255, 255)
        )

        QApplication.processEvents()

    def close(self):
        """Fecha splash screen."""
        if self.splash and not PYI_SPLASH_AVAILABLE:
            self.splash.close()
            self.splash = None

# Instância global da splash screen
splash_screen = CustomSplashScreen()

from ui.modern_main_window import ModernMainWindow as MainWindow
from ui.modern_login import ModernLoginDialog as LoginDialog
import database as db
import migration
import updater
import logging
from log_handler import QtLogHandler

class PDVApplication:
    def __init__(self, app):
        self.app = app
        self.current_user = None
        self.main_window = None
        self.login_dialog = None
        
        # Configura o estilo da aplicação
        self.setup_app_style()
        
        # Inicializa o banco de dados
        self.init_database()
        
    def setup_app_style(self):
        """Configura o estilo global da aplicação."""
        self.app.setStyleSheet("""
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
        """)
    
    def init_database(self):
        """Inicializa e migra o banco de dados, se necessário."""
        try:
            db.create_tables()
            
            logging.info("Verificando a necessidade de migração do banco de dados...")
            if migration.is_any_migration_needed():
                logging.warning("Migração do banco de dados necessária.")
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Icon.Information)
                msg_box.setWindowTitle("Atualização do Banco de Dados")
                msg_box.setText("Uma atualização na estrutura do banco de dados é necessária.")
                msg_box.setInformativeText("Isso pode levar alguns instantes. Por favor, aguarde...")
                msg_box.setStandardButtons(QMessageBox.StandardButton.NoButton)
                msg_box.show()
                self.app.processEvents()

                migration.run_all_migrations()
                msg_box.close()

                QMessageBox.information(None, "Atualização Concluída", "O banco de dados foi atualizado com sucesso!")
                logging.info("Migração do banco de dados concluída com sucesso.")
            else:
                logging.info("Banco de dados já está atualizado.")

            logging.info("Banco de dados inicializado com sucesso.")
        except db.sqlite3.Error as e:
            QMessageBox.critical(None, "Erro de Banco de Dados", 
                               f"Erro ao inicializar o banco de dados SQLite:\n{str(e)}")
            sys.exit(1)
        except Exception as e:
            QMessageBox.critical(None, "Erro Fatal", 
                               f"Um erro inesperado ocorreu na inicialização:\n{str(e)}")
            sys.exit(1)
    
    def show_login(self):
        """Exibe a tela de login."""
        self.login_dialog = LoginDialog()
        self.login_dialog.login_successful.connect(self.on_login_successful)
        
        if self.login_dialog.exec() != LoginDialog.DialogCode.Accepted:
            # Se o login foi cancelado, encerra a aplicação
            sys.exit(0)
    
    def on_login_successful(self, user_data):
        """Callback executado quando login é bem-sucedido."""
        self.current_user = user_data
        
        # Cria e exibe a janela principal
        self.main_window = MainWindow(self.current_user)
        
        # Configura o logging
        self.setup_logging(self.main_window.log_console_dialog.append_log)

        logging.info(f"Login realizado: {user_data['username']} ({user_data['role']})")

        self.main_window.logout_requested.connect(self.on_logout_requested)
        self.main_window.showMaximized()

        # Fecha a tela de splash screen quando a janela principal estiver pronta
        try:
            pyi_splash.close()
        except:
            pass
        
        # Fecha o dialog de login
        if self.login_dialog:
            self.login_dialog.close()

        # Inicia a conexão com o WhatsApp automaticamente se for gerente
        if self.current_user.get('role') == 'gerente':
            try:
                from integrations.whatsapp_manager import WhatsAppManager
                logging.info("Iniciando conexão automática com o WhatsApp...")
                whatsapp_manager = WhatsAppManager.get_instance()
                if not whatsapp_manager.is_ready:
                    whatsapp_manager.connect()
            except Exception as e:
                logging.error(f"Erro ao iniciar conexão automática com o WhatsApp: {e}")
    
    def setup_logging(self, log_slot):
        """
        Configura o sistema de logging para enviar todas as mensagens
        para o slot da interface gráfica especificado.
        """
        log_handler = QtLogHandler()
        
        # Conecta o sinal do handler (que carrega a mensagem) ao slot do console
        log_handler.log_updated.connect(log_slot)

        # Define um formato amigável para as mensagens de log
        log_format = '%(asctime)s - [%(levelname)-8s] - %(message)s (%(filename)s:%(lineno)d)'
        formatter = logging.Formatter(log_format, datefmt='%H:%M:%S')
        log_handler.setFormatter(formatter)

        # Adiciona nosso handler customizado ao logger raiz
        logging.getLogger().addHandler(log_handler)
        
        # Define o nível de log. DEBUG é o mais verboso. Use INFO para produção.
        logging.getLogger().setLevel(logging.INFO)

        logging.info("Aplicação iniciada com sucesso.")
        logging.info(f"Usuário '{self.current_user['username']}' logado. Nível de acesso: '{self.current_user['role']}'.")
    
    def on_logout_requested(self):
        """Callback executado quando logout é solicitado."""
        if self.current_user:
            # Registra logout
            db.log_user_session(self.current_user['id'], 'logout')
            logging.info(f"Logout realizado: {self.current_user['username']}")
        
        # Fecha janela principal
        if self.main_window:
            self.main_window.close()
            self.main_window = None
        
        # Limpa usuário atual
        self.current_user = None
        
        # Exibe login novamente
        QTimer.singleShot(100, self.show_login)
    
    def run(self):
        """Executa a aplicação."""
        # Exibe tela de login
        self.show_login()
        
        # Inicia loop da aplicação
        return self.app.exec()

def main():
    """Função principal da aplicação."""
    # A QApplication deve ser criada ANTES de qualquer widget, incluindo QMessageBoxes do updater.
    app = QApplication(sys.argv)

    # Configura o locale para o padrão do sistema.
    # Isto é CRUCIAL para a conversão correta de números decimais (ponto vs. vírgula).
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error as e:
        # Em alguns ambientes minimos, definir o locale pode falhar.
        # Apenas imprimimos o aviso mas não impedimos a execução.
        print(f"Aviso: Não foi possível definir o locale do sistema: {e}")

    if updater.check_for_updates(__version__):
        # A verificação de atualização pode ter fechado a app, então verificamos de novo.
        # Se o updater decidir sair, o código abaixo não será executado.
        pass

    try:
        pdv_app = PDVApplication(app)
        sys.exit(pdv_app.run())
    except Exception as e:
        # Garante que a app exista para mostrar o erro
        if 'pdv_app' not in locals() or not pdv_app.app:
            QApplication(sys.argv) # Cria uma instância de emergência
        QMessageBox.critical(None, "Erro Fatal", 
                           f"Erro inesperado na aplicação:\n{str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
