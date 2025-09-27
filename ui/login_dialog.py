from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QComboBox, QMessageBox, QFrame
)
from PyQt6.QtGui import QFont, QPixmap, QIcon
from PyQt6.QtCore import Qt, pyqtSignal
import database as db

class LoginDialog(QDialog):
    # Signal emitido quando login é bem-sucedido
    login_successful = pyqtSignal(dict)  # Emite dados do usuário
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDV Açaí - Login do Sistema")
        self.setFixedSize(400, 300)
        self.setModal(True)
        
        # Remove botões de minimizar/maximizar
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        
        self.setup_ui()
        self.load_users()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 30, 40, 30)
        
        # Título
        title_label = QLabel("Sistema PDV Açaí")
        title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #2c3e50; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Subtítulo
        subtitle_label = QLabel("Faça login para continuar")
        subtitle_label.setFont(QFont("Arial", 10))
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("color: #7f8c8d; margin-bottom: 20px;")
        layout.addWidget(subtitle_label)
        
        # Frame principal
        main_frame = QFrame()
        main_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 20px;
            }
        """)
        frame_layout = QVBoxLayout(main_frame)
        frame_layout.setSpacing(15)
        
        # Campo usuário
        user_layout = QVBoxLayout()
        user_label = QLabel("Usuário:")
        user_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.user_combo = QComboBox()
        self.user_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border: 2px solid #ced4da;
                border-radius: 4px;
                font-size: 12px;
                background-color: white;
            }
            QComboBox:focus {
                border-color: #007bff;
            }
        """)
        user_layout.addWidget(user_label)
        user_layout.addWidget(self.user_combo)
        frame_layout.addLayout(user_layout)
        
        # Campo senha
        password_layout = QVBoxLayout()
        password_label = QLabel("Senha:")
        password_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Digite sua senha...")
        self.password_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #ced4da;
                border-radius: 4px;
                font-size: 12px;
                background-color: white;
                min-height: 20px;
            }
            QLineEdit:focus {
                border-color: #007bff;
                background-color: #ffffff;
            }
            QLineEdit:hover {
                border-color: #adb5bd;
            }
        """)
        self.password_input.returnPressed.connect(self.attempt_login)
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        frame_layout.addLayout(password_layout)
        
        layout.addWidget(main_frame)
        
        # Botões
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
        """)
        self.cancel_button.clicked.connect(self.reject)
        
        self.login_button = QPushButton("Entrar")
        self.login_button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)
        self.login_button.clicked.connect(self.attempt_login)
        self.login_button.setDefault(True)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.login_button)
        layout.addLayout(button_layout)
        
        # Status
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #dc3545; font-size: 10px;")
        layout.addWidget(self.status_label)
        
        # Define ordem de tabulação e foco inicial
        self.setTabOrder(self.user_combo, self.password_input)
        self.setTabOrder(self.password_input, self.login_button)
        self.setTabOrder(self.login_button, self.cancel_button)
        
        # Define foco inicial no campo senha
        self.password_input.setFocus()
        
    def load_users(self):
        """Carrega usuários ativos no combo box."""
        try:
            users = db.get_all_users()
            self.user_combo.clear()
            
            for user in users:
                if user['active']:
                    display_text = f"{user['username']} ({user['role'].title()})"
                    self.user_combo.addItem(display_text, user['id'])
            
            if self.user_combo.count() == 0:
                self.status_label.setText("Nenhum usuário ativo encontrado!")
                self.login_button.setEnabled(False)
            else:
                # Seleciona admin por padrão se existir
                for i in range(self.user_combo.count()):
                    if "admin" in self.user_combo.itemText(i).lower():
                        self.user_combo.setCurrentIndex(i)
                        break
                        
        except Exception as e:
            self.status_label.setText(f"Erro ao carregar usuários: {str(e)}")
            self.login_button.setEnabled(False)
    
    def attempt_login(self):
        """Tenta fazer login com as credenciais fornecidas."""
        if self.user_combo.count() == 0:
            return
            
        # Pega dados do usuário selecionado
        current_index = self.user_combo.currentIndex()
        if current_index < 0:
            self.status_label.setText("Selecione um usuário!")
            return
            
        user_id = self.user_combo.itemData(current_index)
        username = self.user_combo.itemText(current_index).split(" (")[0]
        password = self.password_input.text().strip()
        
        if not password:
            self.status_label.setText("Digite a senha!")
            self.password_input.setFocus()
            return
        
        # Tenta autenticar
        try:
            user_data = db.authenticate_user(username, password)
            
            if user_data:
                # Login bem-sucedido
                db.log_user_session(user_data['id'], 'login')
                self.login_successful.emit(user_data)
                self.accept()
            else:
                # Falha na autenticação
                self.status_label.setText("Usuário ou senha incorretos!")
                self.password_input.clear()
                self.password_input.setFocus()
                
        except Exception as e:
            self.status_label.setText(f"Erro no login: {str(e)}")
    
    def closeEvent(self, event):
        """Intercepta o fechamento da janela."""
        # Se a janela for fechada sem login, encerra a aplicação
        event.accept()
        
    def keyPressEvent(self, event):
        """Intercepta teclas pressionadas."""
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

class UserManagementDialog(QDialog):
    """Dialog para gerenciar usuários (apenas para gerentes)."""
    
    def __init__(self, current_user):
        super().__init__()
        self.current_user = current_user
        self.setWindowTitle("Gerenciar Usuários")
        self.setFixedSize(600, 400)
        self.setModal(True)
        
        if current_user['role'] != 'gerente':
            QMessageBox.warning(self, "Acesso Negado", "Apenas gerentes podem gerenciar usuários!")
            self.reject()
            return
            
        self.setup_ui()
        self.load_users()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Título
        title = QLabel("Gerenciamento de Usuários")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Botões de ação
        button_layout = QHBoxLayout()
        
        self.add_button = QPushButton("Adicionar Usuário")
        self.add_button.clicked.connect(self.add_user)
        
        self.edit_button = QPushButton("Editar Usuário")
        self.edit_button.clicked.connect(self.edit_user)
        
        self.toggle_button = QPushButton("Ativar/Desativar")
        self.toggle_button.clicked.connect(self.toggle_user)
        
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.toggle_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # Lista de usuários (implementar com QTableWidget se necessário)
        self.users_label = QLabel("Lista de usuários será implementada aqui...")
        layout.addWidget(self.users_label)
        
        # Botão fechar
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
    
    def load_users(self):
        """Carrega lista de usuários."""
        # Implementar carregamento da lista
        pass
    
    def add_user(self):
        """Adiciona novo usuário."""
        # Implementar dialog de adição
        pass
    
    def edit_user(self):
        """Edita usuário selecionado."""
        # Implementar dialog de edição
        pass
    
    def toggle_user(self):
        """Ativa/desativa usuário selecionado."""
        # Implementar toggle
        pass
