from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, 
    QMessageBox, QListWidgetItem, QLabel
)
from PyQt6.QtCore import Qt
import database as db
from ui.theme import ModernTheme, IconTheme

class BackupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gerenciamento de Backup")
        self.setMinimumSize(600, 400)
        self.setStyleSheet(ModernTheme.get_main_stylesheet())

        self.setup_ui()
        self.load_backups()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Título
        title_label = QLabel("Backups do Sistema")
        title_label.setObjectName("title")
        layout.addWidget(title_label)

        # Lista de backups
        self.backup_list = QListWidget()
        self.backup_list.setObjectName("backup_list")
        layout.addWidget(self.backup_list)

        # Botões
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.create_button = QPushButton(f"{IconTheme.ADD} Criar Novo Backup")
        self.create_button.clicked.connect(self.create_backup)
        button_layout.addWidget(self.create_button)

        self.restore_button = QPushButton(f"{IconTheme.BACKUP} Restaurar Backup Selecionado")
        self.restore_button.clicked.connect(self.restore_backup)
        button_layout.addWidget(self.restore_button)

        layout.addLayout(button_layout)

    def load_backups(self):
        self.backup_list.clear()
        try:
            backups = db.list_backups()
            if not backups:
                self.backup_list.addItem("Nenhum backup encontrado.")
                return

            for backup in backups:
                # Formata a data para exibição
                date_str = backup['created'].strftime("%d/%m/%Y às %H:%M:%S")
                # Calcula o tamanho em MB
                size_mb = backup['size'] / (1024 * 1024)
                
                item_text = f"{backup['filename']} ({size_mb:.2f} MB) - Criado em: {date_str}"
                list_item = QListWidgetItem(item_text)
                list_item.setData(Qt.ItemDataRole.UserRole, backup['path']) # Armazena o caminho completo
                self.backup_list.addItem(list_item)

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao carregar backups: {e}")

    def create_backup(self):
        reply = QMessageBox.question(self, "Confirmar Criação", 
                                     "Deseja criar um novo backup do sistema agora?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            success, message = db.create_backup()
            if success:
                QMessageBox.information(self, "Sucesso", f"Backup criado com sucesso em: {message}")
                self.load_backups()
            else:
                QMessageBox.critical(self, "Erro", f"Falha ao criar backup: {message}")

    def restore_backup(self):
        selected_item = self.backup_list.currentItem()
        if not selected_item or not selected_item.data(Qt.ItemDataRole.UserRole):
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione um backup para restaurar.")
            return

        backup_path = selected_item.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.warning(self, "Confirmar Restauração", 
                                    f"<b>ATENÇÃO:</b> Esta ação substituirá todos os dados atuais pelos dados do backup selecionado ('{backup_path}').<br><br>" \
                                    "Esta operação não pode ser desfeita. Deseja continuar?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                    QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            success, message = db.restore_backup(backup_path)
            if success:
                QMessageBox.information(self, "Sucesso", f"{message}\n\nO aplicativo será reiniciado para aplicar as alterações.")
                # Aqui você pode emitir um sinal para a janela principal reiniciar a aplicação
                self.accept() # Fecha o diálogo
            else:
                QMessageBox.critical(self, "Erro", f"Falha ao restaurar backup: {message}")
