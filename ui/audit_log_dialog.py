from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton,
    QHBoxLayout, QHeaderView
)
from PyQt6.QtCore import Qt
import database as db
from ui.theme import ModernTheme
import logging

class AuditLogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log de Auditoria do Sistema")
        self.setMinimumSize(900, 600)
        self.setStyleSheet(ModernTheme.get_main_stylesheet())

        self.setup_ui()
        self.load_logs()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Tabela de logs
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Data/Hora", "Usuário", "Ação", "Tabela", 
            "ID do Registro", "Valores Antigos", "Novos Valores"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)


        layout.addWidget(self.table)

        # Botões
        button_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.clicked.connect(self.load_logs)
        button_layout.addWidget(self.refresh_button)

        button_layout.addStretch()

        self.close_button = QPushButton("Fechar")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def load_logs(self):
        try:
            logs = db.get_audit_log(limit=500) # Limite para não sobrecarregar
            self.table.setRowCount(len(logs))

            for row_idx, log_entry in enumerate(logs):
                self.table.setItem(row_idx, 0, QTableWidgetItem(str(log_entry.get('timestamp', ''))))
                self.table.setItem(row_idx, 1, QTableWidgetItem(log_entry.get('username', 'N/A')))
                self.table.setItem(row_idx, 2, QTableWidgetItem(log_entry.get('action', '')))
                self.table.setItem(row_idx, 3, QTableWidgetItem(log_entry.get('table_name', '')))
                self.table.setItem(row_idx, 4, QTableWidgetItem(str(log_entry.get('record_id', ''))))
                self.table.setItem(row_idx, 5, QTableWidgetItem(str(log_entry.get('old_values', ''))))
                self.table.setItem(row_idx, 6, QTableWidgetItem(str(log_entry.get('new_values', ''))))
            
            self.table.resizeColumnsToContents()

        except Exception as e:
            logging.error(f"Erro ao carregar logs de auditoria: {e}", exc_info=True)
            # Aqui poderia mostrar uma QMessageBox de erro