from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QComboBox, QMessageBox, QFormLayout
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, pyqtSignal
import database as db

class LoginDialog(QDialog):
    # Signal emitido quando login é bem-sucedido
    login_successful = pyqtSignal(dict)  # Emite dados do usuário
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDV Açaí - Login")
        self.setFixedSize(350, 200)
        self.setModal(True)
        
        self.setup_ui()
        self.load_users()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 20, 30, 20)
        
        # Título
        title = QLabel("Sistema PDV Açaí")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Formulário
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        # Campo usuário
        self.user_combo = QComboBox()
        self.user_combo.setMinimumHeight(30)
        form_layout.addRow("Usuário:", self.user_combo)
        
        # Campo senha
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setMinimumHeight(30)
        self.password_input.setPlaceholderText("Digite sua senha")
        self.password_input.returnPressed.connect(self.attempt_login)
        form_layout.addRow("Senha:", self.password_input)
        
        layout.addLayout(form_layout)
        
        # Botões
        button_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setMinimumHeight(35)
        self.cancel_button.clicked.connect(self.reject)
        
        self.login_button = QPushButton("Entrar")
        self.login_button.setMinimumHeight(35)
        self.login_button.clicked.connect(self.attempt_login)
        self.login_button.setDefault(True)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.login_button)
        layout.addLayout(button_layout)
        
        # Status
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: red; font-size: 11px;")
        layout.addWidget(self.status_label)
        
        # Define foco inicial
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
    
    def keyPressEvent(self, event):
        """Intercepta teclas pressionadas."""
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
