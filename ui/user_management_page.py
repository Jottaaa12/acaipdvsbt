# ui/user_management_page.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QComboBox, QCheckBox, QMessageBox,
    QGroupBox, QFormLayout
)
from PyQt6.QtCore import Qt
import database as db
from integrations.whatsapp_manager import WhatsAppManager

class UserManagementPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_user_id = None
        self.setup_ui()
        self.load_users()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)

        # --- Painel da Esquerda (Tabela de Usuários) ---
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("<b>Usuários Cadastrados</b>"))
        
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(4)
        self.users_table.setHorizontalHeaderLabels(["ID", "Username", "Nível", "Status"])
        self.users_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.users_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.users_table.itemSelectionChanged.connect(self.on_user_selected)
        
        left_panel.addWidget(self.users_table)
        
        # --- Painel da Direita (Formulário de Edição/Criação) ---
        right_panel = QVBoxLayout()
        
        form_group = QGroupBox("Informações do Usuário")
        form_layout = QFormLayout(form_group)
        
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.role_combo = QComboBox()
        self.role_combo.addItems(["operador", "gerente"])
        self.active_checkbox = QCheckBox("Usuário Ativo")
        
        form_layout.addRow("Username:", self.username_input)
        form_layout.addRow("Senha:", self.password_input)
        form_layout.addRow("Confirmar Senha:", self.confirm_password_input)
        form_layout.addRow("Nível de Acesso:", self.role_combo)
        form_layout.addRow(self.active_checkbox)
        
        # Botões de Ação
        buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("Salvar")
        self.new_button = QPushButton("Novo")
        
        self.save_button.clicked.connect(self.save_user)
        self.new_button.clicked.connect(self.clear_form)
        
        buttons_layout.addWidget(self.new_button)
        buttons_layout.addWidget(self.save_button)
        
        right_panel.addWidget(form_group)
        right_panel.addLayout(buttons_layout)
        right_panel.addStretch()

        main_layout.addLayout(left_panel, 2) # Tabela ocupa 2/3
        main_layout.addLayout(right_panel, 1) # Formulário ocupa 1/3
        
        self.clear_form()

    def load_users(self):
        """Carrega ou recarrega a lista de usuários na tabela."""
        self.users_table.setRowCount(0)
        try:
            users = db.get_all_users()
            for row_num, user in enumerate(users):
                self.users_table.insertRow(row_num)
                self.users_table.setItem(row_num, 0, QTableWidgetItem(str(user['id'])))
                self.users_table.setItem(row_num, 1, QTableWidgetItem(user['username']))
                self.users_table.setItem(row_num, 2, QTableWidgetItem(user['role'].title()))
                
                status = "Ativo" if user['active'] else "Inativo"
                status_item = QTableWidgetItem(status)
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.users_table.setItem(row_num, 3, status_item)

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível carregar os usuários: {e}")

    def on_user_selected(self):
        """Preenche o formulário quando um usuário é selecionado na tabela."""
        selected_rows = self.users_table.selectionModel().selectedRows()
        if not selected_rows:
            return
            
        row = selected_rows[0].row()
        self.current_user_id = int(self.users_table.item(row, 0).text())
        
        user = db.get_user_by_id(self.current_user_id) # Você precisará garantir que essa função exista em db.py
        
        if user:
            self.username_input.setText(user['username'])
            self.role_combo.setCurrentText(user['role'])
            self.active_checkbox.setChecked(bool(user['active']))
            self.password_input.clear()
            self.confirm_password_input.clear()
            self.password_input.setPlaceholderText("Deixe em branco para não alterar")
            self.username_input.setEnabled(False) # Não permitir alterar username

    def save_user(self):
        """Salva um novo usuário ou atualiza um existente."""
        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()
        role = self.role_combo.currentText()
        is_active = self.active_checkbox.isChecked()

        if not username:
            QMessageBox.warning(self, "Campo Obrigatório", "O campo 'Username' não pode estar vazio.")
            return

        # --- Lógica para NOVO usuário ---
        if self.current_user_id is None:
            if not password or password != confirm_password:
                QMessageBox.warning(self, "Senhas não coincidem", "A senha e a confirmação devem ser iguais e não podem estar vazias.")
                return
            
            success, message_or_id = db.create_user(username, password, role)

            if not success:
                QMessageBox.warning(self, "Erro ao Criar Usuário", message_or_id)
                return

            QMessageBox.information(self, "Sucesso", f"Usuário '{username}' criado com sucesso!")
            user_id = message_or_id
            # Atualiza o status do usuário com o valor correto da checkbox
            db.update_user(user_id, active=is_active)

        # --- Lógica para ATUALIZAR usuário ---
        else:
            if password and (password != confirm_password):
                QMessageBox.warning(self, "Senhas não coincidem", "Se for alterar a senha, a confirmação deve ser igual.")
                return
            
            # O update só envia a senha se ela foi preenchida
            success, message = db.update_user(self.current_user_id, 
                                           password=password if password else None, 
                                           role=role, 
                                           active=is_active)
            
            if success:
                QMessageBox.information(self, "Sucesso", "Usuário atualizado com sucesso!")
            else:
                QMessageBox.warning(self, "Erro ao Atualizar", message)

        # Notifica o WhatsApp Manager para atualizar a lista de usuários autorizados
        try:
            WhatsAppManager.get_instance().update_authorized_users()
        except Exception as e:
            # Logar o erro seria ideal aqui, mas por enquanto evitamos que a UI quebre
            print(f"Falha ao notificar o WhatsApp Manager sobre a atualização de usuários: {e}")

        self.load_users()
        self.clear_form()

    def clear_form(self):
        """Limpa o formulário para criar um novo usuário."""
        self.current_user_id = None
        self.username_input.clear()
        self.password_input.clear()
        self.confirm_password_input.clear()
        self.role_combo.setCurrentIndex(0)
        self.active_checkbox.setChecked(True)
        self.users_table.clearSelection()
        self.password_input.setPlaceholderText("")
        self.username_input.setEnabled(True)
        self.username_input.setFocus()
