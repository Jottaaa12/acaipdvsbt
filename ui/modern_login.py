from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QComboBox, QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt, pyqtSignal
from ui.theme import ModernTheme, IconTheme
import database as db

class ModernLoginDialog(QDialog):
    """Dialog de login moderno com tema roxo/amarelo"""
    
    login_successful = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDV Açaí - Login")
        self.setMinimumWidth(450)
        self.setModal(True)
        
        # Remove bordas da janela para visual moderno
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        
        self.setup_ui()
        self.apply_theme()
        self.load_users()
        
    def setup_ui(self):
        """Configura a interface moderna"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Container principal com gradiente
        main_container = QFrame()
        main_container.setObjectName("main_container")
        main_layout.addWidget(main_container)
        
        container_layout = QVBoxLayout(main_container)
        container_layout.setContentsMargins(40, 40, 40, 40)
        container_layout.setSpacing(30)
        
        # Header com título
        header_layout = QVBoxLayout()
        header_layout.setSpacing(10)
        
        title = QLabel("🍇 PDV Açaí")
        title.setObjectName("login_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title)
        
        subtitle = QLabel("Sistema de Gestão Moderno")
        subtitle.setObjectName("login_subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(subtitle)
        
        container_layout.addLayout(header_layout)
        
        # Formulário de login
        form_frame = QFrame()
        form_frame.setObjectName("login_form")
        
        # Adiciona sombra ao formulário
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(ModernTheme.PRIMARY_DARK))
        shadow.setOffset(0, 5)
        form_frame.setGraphicsEffect(shadow)
        
        form_layout = QVBoxLayout(form_frame)
        form_layout.setContentsMargins(30, 30, 30, 30)
        form_layout.setSpacing(20)
        
        # Campo usuário
        user_layout = QVBoxLayout()
        user_layout.setSpacing(8)
        
        user_label = QLabel(f"{IconTheme.USERS} Usuário")
        user_label.setObjectName("form_label")
        user_layout.addWidget(user_label)
        
        self.user_combo = QComboBox()
        self.user_combo.setObjectName("modern_combo")
        user_layout.addWidget(self.user_combo)
        
        form_layout.addLayout(user_layout)
        
        # Campo senha
        password_layout = QVBoxLayout()
        password_layout.setSpacing(8)
        
        password_label = QLabel("🔒 Senha")
        password_label.setObjectName("form_label")
        password_layout.addWidget(password_label)
        
        self.password_input = QLineEdit()
        self.password_input.setObjectName("modern_input")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Digite sua senha...")
        # Nota: Enter é tratado no keyPressEvent
        password_layout.addWidget(self.password_input)
        
        form_layout.addLayout(password_layout)
        
        # Botões
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setObjectName("cancel_button")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.login_button = QPushButton(f"{IconTheme.USERS} Entrar")
        self.login_button.setObjectName("login_button")
        self.login_button.clicked.connect(self.attempt_login)
        self.login_button.setDefault(True)
        button_layout.addWidget(self.login_button)
        
        form_layout.addLayout(button_layout)
        
        # Status
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(f"""
            color: {ModernTheme.ERROR};
            font-size: 12px;
            font-weight: 500;
            padding: 10px;
            border-radius: 6px;
            background-color: rgba(239, 68, 68, 0.1);
        """)
        self.status_label.hide()
        form_layout.addWidget(self.status_label)
        
        container_layout.addWidget(form_frame)
        
        # Footer
        footer = QLabel("Desenvolvido com ❤️ para açaiterias modernas")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(f"""
            color: rgba(255, 255, 255, 0.7);
            font-size: 11px;
            font-style: italic;
            margin-top: 10px;
        """)
        container_layout.addWidget(footer)
        
        # Define foco inicial
        self.password_input.setFocus()
    
    def apply_theme(self):
        """Aplica o tema moderno"""
        self.setStyleSheet(f"""
            QDialog {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 {ModernTheme.PRIMARY}, 
                    stop:0.5 {ModernTheme.PRIMARY_LIGHT}, 
                    stop:1 {ModernTheme.SECONDARY});
                border-radius: 15px;
            }}
            
            QFrame#main_container {{
                background: transparent;
                border-radius: 15px;
            }}
            
            QLabel#login_title {{
                color: {ModernTheme.WHITE};
                font-size: 32px;
                font-weight: 700;
                margin-bottom: 5px;
            }}
            
            QLabel#login_subtitle {{
                color: rgba(255, 255, 255, 0.9);
                font-size: 16px;
                font-weight: 400;
                margin-bottom: 20px;
            }}
            
            QFrame#login_form {{
                background-color: {ModernTheme.WHITE};
                border-radius: 15px;
                border: none;
            }}
            
            QLabel#form_label {{
                color: {ModernTheme.DARK};
                font-size: 14px;
                font-weight: 600;
            }}
            
            QLineEdit#modern_input {{
                background-color: {ModernTheme.GRAY_LIGHTER};
                border: 2px solid {ModernTheme.GRAY_LIGHT};
                border-radius: 10px;
                padding: 12px 16px;
                font-size: 14px;
                color: {ModernTheme.DARK};
            }}
            
            QLineEdit#modern_input:focus {{
                border-color: {ModernTheme.PRIMARY};
                background-color: {ModernTheme.WHITE};
            }}
            
            QComboBox#modern_combo {{
                background-color: {ModernTheme.GRAY_LIGHTER};
                border: 2px solid {ModernTheme.GRAY_LIGHT};
                border-radius: 10px;
                padding: 12px 16px;
                font-size: 14px;
                color: {ModernTheme.DARK};
            }}
            
            QComboBox#modern_combo:focus {{
                border-color: {ModernTheme.PRIMARY};
                background-color: {ModernTheme.WHITE};
            }}
            
            QComboBox#modern_combo::drop-down {{
                border: none;
                width: 30px;
            }}
            
            QComboBox#modern_combo::down-arrow {{
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 6px solid {ModernTheme.GRAY};
                margin-right: 10px;
            }}
            
            QComboBox#modern_combo QAbstractItemView {{
                background-color: {ModernTheme.WHITE};
                border: 1px solid {ModernTheme.GRAY_LIGHT};
                border-radius: 8px;
                selection-background-color: {ModernTheme.PRIMARY_LIGHTEST};
                selection-color: {ModernTheme.PRIMARY_DARK};
                padding: 5px;
            }}
            
            QPushButton#login_button {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 {ModernTheme.PRIMARY}, 
                    stop:1 {ModernTheme.PRIMARY_LIGHT});
                color: {ModernTheme.WHITE};
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: 600;
            }}
            
            QPushButton#login_button:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 {ModernTheme.PRIMARY_DARK}, 
                    stop:1 {ModernTheme.PRIMARY});
            }}
            
            QPushButton#login_button:pressed {{
                background: {ModernTheme.PRIMARY_DARK};
            }}
            
            QPushButton#cancel_button {{
                background-color: {ModernTheme.GRAY_LIGHT};
                color: {ModernTheme.DARK};
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: 600;
            }}
            
            QPushButton#cancel_button:hover {{
                background-color: {ModernTheme.GRAY};
                color: {ModernTheme.WHITE};
            }}
        """)
    
    def load_users(self):
        """Carrega usuários ativos"""
        try:
            users = db.get_all_users()
            self.user_combo.clear()
            
            for user in users:
                if user['active']:
                    role_icon = "👑" if user['role'] == 'gerente' else "👤"
                    display_text = f"{role_icon} {user['username']} ({user['role'].title()})"
                    self.user_combo.addItem(display_text, user['id'])
            
            if self.user_combo.count() == 0:
                self.show_error("Nenhum usuário ativo encontrado!")
                self.login_button.setEnabled(False)
            else:
                # Seleciona admin por padrão
                for i in range(self.user_combo.count()):
                    if "admin" in self.user_combo.itemText(i).lower():
                        self.user_combo.setCurrentIndex(i)
                        break
                        
        except Exception as e:
            self.show_error(f"Erro ao carregar usuários: {str(e)}")
            self.login_button.setEnabled(False)
    
    def attempt_login(self):
        """Tenta fazer login"""
        if self.user_combo.count() == 0:
            return
            
        current_index = self.user_combo.currentIndex()
        if current_index < 0:
            self.show_error("Selecione um usuário!")
            return
            
        user_id = self.user_combo.itemData(current_index)
        username = self.user_combo.itemText(current_index).split(" ")[1]  # Remove ícone
        password = self.password_input.text().strip()
        
        if not password:
            self.show_error("Digite a senha!")
            self.password_input.setFocus()
            return
        
        try:
            user_data = db.authenticate_user(username, password)
            
            if user_data:
                # Login bem-sucedido
                db.log_user_session(user_data['id'], 'login')
                self.login_successful.emit(user_data)
                self.accept()
            else:
                # Falha na autenticação
                self.show_error("Usuário ou senha incorretos!")
                self.password_input.clear()
                self.password_input.setFocus()
                
        except Exception as e:
            self.show_error(f"Erro no login: {str(e)}")
    
    def show_error(self, message):
        """Exibe mensagem de erro"""
        self.status_label.setText(message)
        self.status_label.show()
    
    def keyPressEvent(self, event):
        """Intercepta teclas"""
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Intercepta Enter para evitar que feche o diálogo prematuramente
            self.attempt_login()
        else:
            super().keyPressEvent(event)
    
    def mousePressEvent(self, event):
        """Permite arrastar a janela"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.globalPosition().toPoint()
    
    def mouseMoveEvent(self, event):
        """Move a janela quando arrastada"""
        if hasattr(self, 'drag_start_position'):
            if event.buttons() == Qt.MouseButton.LeftButton:
                self.move(self.pos() + event.globalPosition().toPoint() - self.drag_start_position)
                self.drag_start_position = event.globalPosition().toPoint()
