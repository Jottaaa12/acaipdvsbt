from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt6.QtCore import Qt, pyqtSignal
import database as db
import logging

class DataManagementDialog(QDialog):
    data_deleted = pyqtSignal()

    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle("Gerenciamento de Dados Históricos")
        self.setFixedSize(500, 350)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint) # Remove o botão de ajuda

        self._setup_ui()
        self._connect_signals()
        self._update_confirm_button_state()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # --- Aviso de Perigo ---
        warning_label = QLabel("<html><b><font color='red' size='4'>ATENÇÃO: Esta operação é IRREVERSÍVEL!</font></b><br>" 
                               "Todos os dados históricos listados abaixo serão PERMANENTEMENTE apagados.<br>" 
                               "Isso inclui: Vendas, Itens de Venda, Pagamentos, Sessões de Caixa, Movimentos de Caixa, Contagens de Caixa e Logs de Auditoria.<br>" 
                               "Certifique-se de ter um backup recente antes de prosseguir.</html>")
        warning_label.setWordWrap(True)
        main_layout.addWidget(warning_label)

        # --- Confirmação de Senha ---
        password_layout = QHBoxLayout()
        password_label = QLabel("Senha de Gerente:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        main_layout.addLayout(password_layout)

        # --- Confirmação de Frase ---
        phrase_layout = QHBoxLayout()
        phrase_label = QLabel(f"Digite \"<b>CONFIRMAR EXCLUSAO</b>\" para prosseguir:")
        phrase_label.setWordWrap(True)
        self.phrase_input = QLineEdit()
        phrase_layout.addWidget(phrase_label)
        phrase_layout.addWidget(self.phrase_input)
        main_layout.addLayout(phrase_layout)

        # --- Botões ---
        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancelar")
        self.confirm_button = QPushButton("Excluir Dados Permanentemente")
        self.confirm_button.setStyleSheet("background-color: #dc3545; color: white;") # Estilo de botão de perigo
        self.confirm_button.setEnabled(False) # Desabilitado por padrão

        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.confirm_button)
        main_layout.addLayout(button_layout)

    def _connect_signals(self):
        self.password_input.textChanged.connect(self._update_confirm_button_state)
        self.phrase_input.textChanged.connect(self._update_confirm_button_state)
        self.cancel_button.clicked.connect(self.reject)
        self.confirm_button.clicked.connect(self._attempt_delete)

    def _update_confirm_button_state(self):
        is_password_correct = db.authenticate_user(self.user['username'], self.password_input.text()) is not None
        is_phrase_correct = self.phrase_input.text() == "CONFIRMAR EXCLUSAO"
        self.confirm_button.setEnabled(is_password_correct and is_phrase_correct)

    def _attempt_delete(self):
        # Confirmação final antes de chamar a função do DB
        reply = QMessageBox.question(self, "Confirmação Final",
                                     "Você tem CERTEZA absoluta que deseja EXCLUIR TODOS os dados históricos?\n" 
                                     "Esta ação é IRREVERSÍVEL e não pode ser desfeita.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            logging.info(f"Usuário {self.user['username']} iniciou exclusão de dados históricos.")
            success, message = db.delete_historical_data(self.user['id'])
            if success:
                QMessageBox.information(self, "Sucesso", "Dados históricos excluídos com sucesso!")
                logging.info(f"Usuário {self.user['username']} excluiu dados históricos com sucesso.")
                self.data_deleted.emit() # Emite sinal para a página de configurações atualizar
                self.accept()
            else:
                QMessageBox.critical(self, "Erro", f"Falha ao excluir dados históricos: {message}")
                logging.error(f"Usuário {self.user['username']} falhou ao excluir dados históricos: {message}")
        else:
            logging.info(f"Usuário {self.user['username']} cancelou a exclusão de dados históricos na confirmação final.")
