__version__ = "1.0.0"

import sys
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer
from ui.modern_main_window import ModernMainWindow as MainWindow
from ui.modern_login import ModernLoginDialog as LoginDialog
import database as db
import updater

class PDVApplication:
    def __init__(self):
        self.app = QApplication(sys.argv)
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
        """Inicializa o banco de dados."""
        try:
            db.create_tables()
            print("Banco de dados inicializado com sucesso.")
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
        print(f"Login realizado: {user_data['username']} ({user_data['role']})")
        
        # Cria e exibe a janela principal
        self.main_window = MainWindow(self.current_user)
        self.main_window.logout_requested.connect(self.on_logout_requested)
        self.main_window.show()
        
        # Fecha o dialog de login
        if self.login_dialog:
            self.login_dialog.close()
    
    def on_logout_requested(self):
        """Callback executado quando logout é solicitado."""
        if self.current_user:
            # Registra logout
            db.log_user_session(self.current_user['id'], 'logout')
            print(f"Logout realizado: {self.current_user['username']}")
        
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
    if updater.check_for_updates(__version__):
        sys.exit(0)
    try:
        pdv_app = PDVApplication()
        sys.exit(pdv_app.run())
    except Exception as e:
        QMessageBox.critical(None, "Erro Fatal", 
                           f"Erro inesperado na aplicação:\n{str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
