from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QTabWidget, QWidget, QApplication
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
        self._update_local_confirm_button_state() # Updated to reflect local tab

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        self.setFixedSize(550, 400) # Adjust size for tabs

        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        # --- Tab 1: Limpeza Local ---
        local_tab = QWidget()
        local_layout = QVBoxLayout(local_tab)
        local_layout.setSpacing(15)
        local_layout.setContentsMargins(15, 15, 15, 15)

        local_warning_label = QLabel("<html><b><font color='#c0392b' size='4'>ATENÇÃO: Limpeza de Dados Locais</font></b><br>" 
                                     "Esta operação é <b>IRREVERSÍVEL</b> e apagará os dados do <b>COMPUTADOR ATUAL</b>.<br>" 
                                     "Isso inclui: Vendas, Sessões de Caixa, Auditoria, etc.<br>" 
                                     "Certifique-se de ter um backup recente antes de prosseguir.</html>")
        local_warning_label.setWordWrap(True)
        local_layout.addWidget(local_warning_label)

        local_password_layout = QHBoxLayout()
        local_password_label = QLabel("Senha de Gerente:")
        self.local_password_input = QLineEdit()
        self.local_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        local_password_layout.addWidget(local_password_label)
        local_password_layout.addWidget(self.local_password_input)
        local_layout.addLayout(local_password_layout)

        local_phrase_layout = QHBoxLayout()
        local_phrase_label = QLabel(f"Digite \"<b>CONFIRMAR EXCLUSAO</b>\" para prosseguir:")
        self.local_phrase_input = QLineEdit()
        local_phrase_layout.addWidget(local_phrase_label)
        local_phrase_layout.addWidget(self.local_phrase_input)
        local_layout.addLayout(local_phrase_layout)
        local_layout.addStretch()

        self.local_confirm_button = QPushButton("Excluir Dados Locais Permanentemente")
        self.local_confirm_button.setStyleSheet("background-color: #c0392b; color: white; padding: 8px;")
        self.local_confirm_button.setEnabled(False)
        local_layout.addWidget(self.local_confirm_button, 0, Qt.AlignmentFlag.AlignRight)

        # --- Tab 2: Limpeza Nuvem ---
        supabase_tab = QWidget()
        supabase_layout = QVBoxLayout(supabase_tab)
        supabase_layout.setSpacing(15)
        supabase_layout.setContentsMargins(15, 15, 15, 15)

        supabase_warning_label = QLabel("<html><b><font color='#e67e22' size='4'>ATENÇÃO: Limpeza de Dados da Nuvem (Supabase)</font></b><br>" 
                                        "Esta operação é <b>EXTREMAMENTE PERIGOSA</b> e apagará todos os dados transacionais da nuvem.<br>"
                                        "<b>A ação afetará TODOS os caixas sincronizados com esta conta.</b><br>"
                                        "Dados a serem apagados: Vendas, Sessões de Caixa, Auditoria, etc.<br>"
                                        "Dados a serem mantidos: Usuários, Produtos, Clientes, etc.</html>")
        supabase_warning_label.setWordWrap(True)
        supabase_layout.addWidget(supabase_warning_label)

        supabase_password_layout = QHBoxLayout()
        supabase_password_label = QLabel("Senha de Gerente:")
        self.supabase_password_input = QLineEdit()
        self.supabase_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        supabase_password_layout.addWidget(supabase_password_label)
        supabase_password_layout.addWidget(self.supabase_password_input)
        supabase_layout.addLayout(supabase_password_layout)

        supabase_phrase_layout = QHBoxLayout()
        supabase_phrase_label = QLabel(f"Digite \"<b>LIMPAR NUVEM</b>\" para prosseguir:")
        self.supabase_phrase_input = QLineEdit()
        supabase_phrase_layout.addWidget(supabase_phrase_label)
        supabase_phrase_layout.addWidget(self.supabase_phrase_input)
        supabase_layout.addLayout(supabase_phrase_layout)
        supabase_layout.addStretch()

        self.supabase_confirm_button = QPushButton("Limpar Dados da Nuvem Permanentemente")
        self.supabase_confirm_button.setStyleSheet("background-color: #e67e22; color: white; padding: 8px;")
        self.supabase_confirm_button.setEnabled(False)
        supabase_layout.addWidget(self.supabase_confirm_button, 0, Qt.AlignmentFlag.AlignRight)

        tab_widget.addTab(local_tab, "Limpeza de Dados Locais")
        tab_widget.addTab(supabase_tab, "Limpeza de Dados da Nuvem")

        # --- Botão de Cancelar Global ---
        self.cancel_button = QPushButton("Fechar")
        main_layout.addWidget(self.cancel_button, 0, Qt.AlignmentFlag.AlignRight)

    def _connect_signals(self):
        # Sinais da aba Local
        self.local_password_input.textChanged.connect(self._update_local_confirm_button_state)
        self.local_phrase_input.textChanged.connect(self._update_local_confirm_button_state)
        self.local_confirm_button.clicked.connect(self._attempt_local_delete)

        # Sinais da aba Nuvem
        self.supabase_password_input.textChanged.connect(self._update_supabase_confirm_button_state)
        self.supabase_phrase_input.textChanged.connect(self._update_supabase_confirm_button_state)
        self.supabase_confirm_button.clicked.connect(self._attempt_supabase_clear)

        # Sinais globais
        self.cancel_button.clicked.connect(self.reject)

    def _update_supabase_confirm_button_state(self):
        is_password_correct = db.authenticate_user(self.user['username'], self.supabase_password_input.text()) is not None
        is_phrase_correct = self.supabase_phrase_input.text() == "LIMPAR NUVEM"
        self.supabase_confirm_button.setEnabled(is_password_correct and is_phrase_correct)

    def _attempt_supabase_clear(self):
        reply = QMessageBox.question(self, "Confirmação Final - Limpeza da Nuvem",
                                     "<b>VOCÊ ESTÁ PRESTES A APAGAR TODOS OS DADOS TRANSACIONAIS DA NUVEM.</b><br><br>"
                                     "Esta ação é <b>IRREVERSÍVEL</b> e afetará <b>TODOS</b> os caixas sincronizados.<br>"
                                     "Tem certeza absoluta que deseja continuar?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            logging.warning(f"Usuário {self.user['username']} iniciou limpeza de dados transacionais do Supabase.")
            
            self.supabase_confirm_button.setEnabled(False)
            self.supabase_confirm_button.setText("Limpando...")
            QApplication.processEvents() # Update UI

            try:
                from data.sync_manager import SyncManager
                sync_manager = SyncManager()
                success, message = sync_manager.truncate_supabase_data()

                if success:
                    QMessageBox.information(self, "Sucesso", message)
                    logging.info(f"Limpeza de dados do Supabase concluída com sucesso pelo usuário {self.user['username']}.")
                else:
                    QMessageBox.critical(self, "Erro", message)
                    logging.error(f"Falha na limpeza de dados do Supabase. Usuário: {self.user['username']}. Erro: {message}")

            except Exception as e:
                QMessageBox.critical(self, "Erro Crítico", f"Ocorreu um erro inesperado ao tentar limpar os dados: {e}")
                logging.critical(f"Erro inesperado na limpeza de dados do Supabase: {e}", exc_info=True)
            finally:
                self.supabase_confirm_button.setText("Limpar Dados da Nuvem Permanentemente")
                self._update_supabase_confirm_button_state()
        else:
            logging.info(f"Usuário {self.user['username']} cancelou a limpeza de dados do Supabase.")

    def _update_local_confirm_button_state(self):
        is_password_correct = db.authenticate_user(self.user['username'], self.local_password_input.text()) is not None
        is_phrase_correct = self.local_phrase_input.text() == "CONFIRMAR EXCLUSAO"
        self.local_confirm_button.setEnabled(is_password_correct and is_phrase_correct)

    def _attempt_local_delete(self):
        # Confirmação final antes de chamar a função do DB
        reply = QMessageBox.question(self, "Confirmação Final - Limpeza Local",
                                     "Você tem CERTEZA absoluta que deseja EXCLUIR TODOS os dados históricos LOCAIS?\n" 
                                     "Esta ação é IRREVERSÍVEL e não pode ser desfeita.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            logging.info(f"Usuário {self.user['username']} iniciou exclusão de dados históricos locais.")
            success, message = db.delete_historical_data(self.user['id'])
            if success:
                QMessageBox.information(self, "Sucesso", "Dados históricos locais excluídos com sucesso!")
                logging.info(f"Usuário {self.user['username']} excluiu dados históricos locais com sucesso.")
                self.data_deleted.emit() # Emite sinal para a página de configurações atualizar
                self.accept()
            else:
                QMessageBox.critical(self, "Erro", f"Falha ao excluir dados históricos locais: {message}")
                logging.error(f"Usuário {self.user['username']} falhou ao excluir dados históricos locais: {message}")
        else:
            logging.info(f"Usuário {self.user['username']} cancelou a exclusão de dados históricos locais na confirmação final.")
