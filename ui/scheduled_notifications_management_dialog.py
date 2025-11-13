from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem, QHBoxLayout, QDialog, QMessageBox, QLineEdit, QTextEdit, QTimeEdit, QCheckBox
from PyQt6.QtCore import Qt, QTime, QDate
from config_manager import ConfigManager
import uuid

class ScheduledNotificationsManagementDialog(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.setup_ui()
        self.load_notifications()

    def setup_ui(self):
        self.setWindowTitle("Gerenciar Avisos Agendados")
        self.main_layout = QVBoxLayout(self)

        self.notifications_list_widget = QListWidget()
        self.notifications_list_widget.itemDoubleClicked.connect(self.edit_notification)
        self.main_layout.addWidget(self.notifications_list_widget)

        self.add_button = QPushButton("Adicionar Novo Aviso")
        self.add_button.clicked.connect(self.add_notification)
        self.main_layout.addWidget(self.add_button)

    def load_notifications(self):
        self.notifications_list_widget.clear()
        notifications = self.config_manager.get_scheduled_notifications()
        for notification in notifications:
            item = QListWidgetItem(f"{notification.get('mensagem', 'Sem Mensagem')} - {notification.get('horario', '')}")
            item.setData(Qt.ItemDataRole.UserRole, notification)
            self.notifications_list_widget.addItem(item)

    def add_notification(self):
        dialog = NotificationEditDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            notification_data = dialog.get_notification_data()
            if notification_data:
                notification_data['id'] = str(uuid.uuid4()) # Generate a unique ID
                self.config_manager.add_scheduled_notification(notification_data)
                self.load_notifications()
                QMessageBox.information(self, "Sucesso", "Aviso agendado adicionado com sucesso!")

    def edit_notification(self, item):
        notification_data = item.data(Qt.ItemDataRole.UserRole)
        dialog = NotificationEditDialog(self, notification_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_data = dialog.get_notification_data()
            if updated_data:
                self.config_manager.update_scheduled_notification(notification_data['id'], updated_data)
                self.load_notifications()
                QMessageBox.information(self, "Sucesso", "Aviso agendado atualizado com sucesso!")

    def delete_notification(self):
        selected_item = self.notifications_list_widget.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Atenção", "Selecione um aviso para excluir.")
            return

        reply = QMessageBox.question(self, "Confirmar Exclusão", "Tem certeza que deseja excluir este aviso agendado?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            notification_data = selected_item.data(Qt.ItemDataRole.UserRole)
            self.config_manager.delete_scheduled_notification(notification_data['id'])
            self.load_notifications()
            QMessageBox.information(self, "Sucesso", "Aviso agendado excluído com sucesso!")


class NotificationEditDialog(QDialog):
    def __init__(self, parent=None, notification_data=None):
        super().__init__(parent)
        self.notification_data = notification_data if notification_data else {}
        self.setWindowTitle("Editar Aviso Agendado" if notification_data else "Novo Aviso Agendado")
        self.setMinimumSize(400, 300)
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Remetente
        layout.addWidget(QLabel("Remetente:"))
        self.sender_input = QLineEdit()
        self.sender_input.setPlaceholderText("Ex: Loja Principal")
        layout.addWidget(self.sender_input)

        # Mensagem
        layout.addWidget(QLabel("Mensagem:"))
        self.message_input = QTextEdit()
        layout.addWidget(self.message_input)

        # Números (separados por vírgula)
        layout.addWidget(QLabel("Números de Telefone (separados por vírgula):"))
        self.numbers_input = QLineEdit()
        self.numbers_input.setPlaceholderText("Ex: +5511987654321, +5521912345678")
        layout.addWidget(self.numbers_input)

        # Horário
        layout.addWidget(QLabel("Horário de Envio:"))
        self.time_input = QTimeEdit()
        self.time_input.setDisplayFormat("HH:mm")
        self.time_input.setTime(QTime.currentTime())
        layout.addWidget(self.time_input)

        # Dias da Semana
        layout.addWidget(QLabel("Dias da Semana:"))
        self.day_checkboxes = {}
        days_layout = QHBoxLayout()
        days = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        for day in days:
            checkbox = QCheckBox(day)
            self.day_checkboxes[day] = checkbox
            days_layout.addWidget(checkbox)
        layout.addLayout(days_layout)

        # Ativo
        self.active_checkbox = QCheckBox("Ativo")
        self.active_checkbox.setChecked(True)
        layout.addWidget(self.active_checkbox)

        # Botões
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Salvar")
        self.save_button.clicked.connect(self.accept)
        button_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

    def load_data(self):
        if self.notification_data:
            self.sender_input.setText(self.notification_data.get('remetente', ''))
            self.message_input.setText(self.notification_data.get('mensagem', ''))
            self.numbers_input.setText(", ".join(self.notification_data.get('numeros', [])))
            
            time_str = self.notification_data.get('horario', '00:00')
            self.time_input.setTime(QTime.fromString(time_str, "HH:mm"))

            for day, checkbox in self.day_checkboxes.items():
                if day in self.notification_data.get('dias_semana', []):
                    checkbox.setChecked(True)
                else:
                    checkbox.setChecked(False)
            
            self.active_checkbox.setChecked(self.notification_data.get('ativo', True))

    def get_notification_data(self):
        selected_days = [day for day, checkbox in self.day_checkboxes.items() if checkbox.isChecked()]
        
        if not self.sender_input.text().strip():
            QMessageBox.warning(self, "Erro", "O campo 'Remetente' não pode estar vazio.")
            return None
        if not self.message_input.toPlainText().strip():
            QMessageBox.warning(self, "Erro", "O campo 'Mensagem' não pode estar vazio.")
            return None
        if not self.numbers_input.text().strip():
            QMessageBox.warning(self, "Erro", "O campo 'Números de Telefone' não pode estar vazio.")
            return None
        if not selected_days:
            QMessageBox.warning(self, "Erro", "Selecione pelo menos um dia da semana.")
            return None

        return {
            'id': self.notification_data.get('id'), # Keep existing ID if editing
            'remetente': self.sender_input.text().strip(),
            'mensagem': self.message_input.toPlainText().strip(),
            'numeros': [num.strip() for num in self.numbers_input.text().split(',') if num.strip()],
            'horario': self.time_input.time().toString("HH:mm"),
            'dias_semana': selected_days,
            'ativo': self.active_checkbox.isChecked()
        }
