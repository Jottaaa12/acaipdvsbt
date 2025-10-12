
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView, QDialog,
    QFormLayout, QComboBox, QSpinBox, QTabWidget, QDialogButtonBox, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal
import stock_manager as sm

# --- Diálogo para Adicionar/Editar Item ---
class StockItemDialog(QDialog):
    def __init__(self, item_data=None, parent=None):
        super().__init__(parent)
        self.item_data = item_data

        self.setWindowTitle("Adicionar Novo Item de Estoque" if not item_data else "Editar Item de Estoque")
        
        layout = QFormLayout(self)
        
        self.codigo_input = QLineEdit(item_data.get('codigo', '') if item_data else '')
        self.nome_input = QLineEdit(item_data.get('nome', '') if item_data else '')
        self.grupo_combo = QComboBox()
        self.estoque_atual_input = QSpinBox(maximum=999999)
        self.estoque_minimo_input = QSpinBox(maximum=999999)
        self.unidade_input = QLineEdit(item_data.get('unidade_medida', '') if item_data else '')

        if item_data:
            self.estoque_atual_input.setValue(item_data.get('estoque_atual', 0))
            self.estoque_minimo_input.setValue(item_data.get('estoque_minimo', 0))

        self.populate_groups_combo()

        layout.addRow("Código:", self.codigo_input)
        layout.addRow("Nome do Item:", self.nome_input)
        layout.addRow("Grupo:", self.grupo_combo)
        layout.addRow("Estoque Atual:", self.estoque_atual_input)
        layout.addRow("Estoque Mínimo:", self.estoque_minimo_input)
        layout.addRow("Unidade (ex: pct, kg, un):", self.unidade_input)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

    def populate_groups_combo(self):
        self.grupo_combo.clear()
        groups = sm.get_all_stock_groups()
        for group in groups:
            self.grupo_combo.addItem(group['nome'], userData=group['id'])
        
        if self.item_data:
            group_id_to_select = self.item_data.get('grupo_id')
            if group_id_to_select:
                index = self.grupo_combo.findData(group_id_to_select)
                if index != -1:
                    self.grupo_combo.setCurrentIndex(index)

    def get_data(self):
        return {
            'id': self.item_data.get('id') if self.item_data else None,
            'codigo': self.codigo_input.text().strip(),
            'nome': self.nome_input.text().strip(),
            'grupo_id': self.grupo_combo.currentData(),
            'estoque_atual': self.estoque_atual_input.value(),
            'estoque_minimo': self.estoque_minimo_input.value(),
            'unidade_medida': self.unidade_input.text().strip()
        }

# --- Widget de Gerenciamento de Grupos ---
class StockGroupManagementWidget(QWidget):
    groups_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.current_group_id = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        form_layout = QFormLayout()
        self.name_input = QLineEdit(placeholderText="Nome do Novo Grupo")
        self.save_button = QPushButton("Salvar Grupo")
        self.delete_button = QPushButton("Excluir Grupo")
        
        form_layout.addRow(QLabel("Gerenciar Grupos:"), self.name_input)
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.delete_button)
        form_layout.addRow(button_layout)

        self.groups_combo = QComboBox()
        self.groups_combo.setPlaceholderText("Selecione um grupo para editar/excluir")
        
        layout.addWidget(self.groups_combo, 1)
        layout.addLayout(form_layout, 2)

        self.save_button.clicked.connect(self.save_group)
        self.delete_button.clicked.connect(self.delete_group)
        self.groups_combo.currentIndexChanged.connect(self.select_group)

        self.load_groups()

    def load_groups(self):
        self.groups_combo.blockSignals(True)
        self.groups_combo.clear()
        self.groups_combo.addItem("Selecione um grupo...", userData=None)
        groups = sm.get_all_stock_groups()
        for group in groups:
            self.groups_combo.addItem(group['nome'], userData=group['id'])
        self.groups_combo.blockSignals(False)
        self.clear_fields()

    def select_group(self, index):
        if index <= 0:
            self.clear_fields()
            return
        self.current_group_id = self.groups_combo.currentData()
        self.name_input.setText(self.groups_combo.currentText())

    def save_group(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Campo Vazio", "O nome do grupo não pode estar vazio.")
            return

        if self.current_group_id:
            success, message = sm.update_stock_group(self.current_group_id, name)
        else:
            success, message = sm.add_stock_group(name)
        
        if success:
            QMessageBox.information(self, "Sucesso", "Grupo salvo com sucesso.")
            self.groups_changed.emit() # Emite o sinal para recarregar
        else:
            QMessageBox.warning(self, "Erro ao Salvar", message)

    def delete_group(self):
        if not self.current_group_id:
            QMessageBox.warning(self, "Atenção", "Selecione um grupo para excluir.")
            return

        reply = QMessageBox.question(self, "Confirmar Exclusão",
                                     f"Tem certeza que deseja excluir o grupo '{self.name_input.text()}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            success, message = sm.delete_stock_group(self.current_group_id)
            if success:
                QMessageBox.information(self, "Sucesso", "Grupo excluído com sucesso.")
                self.groups_changed.emit() # Emite o sinal para recarregar
            else:
                QMessageBox.warning(self, "Erro ao Excluir", message)

    def clear_fields(self):
        self.current_group_id = None
        self.name_input.clear()
        self.groups_combo.setCurrentIndex(0)

# --- Página Principal de Gerenciamento de Estoque ---
class StockManagementPage(QWidget):
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        # Título
        title_label = QLabel("Gerenciamento de Estoque de Insumos")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        main_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Seção de Gerenciamento de Grupos
        self.group_manager = StockGroupManagementWidget()
        self.group_manager.groups_changed.connect(self.reload_all)
        main_layout.addWidget(self.group_manager)

        # Abas para cada grupo
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_selection_changed) # Atualiza estado dos botões ao mudar de aba
        main_layout.addWidget(self.tabs)

        # Painel de Ações para o item selecionado
        self.setup_actions_panel(main_layout)

        self.reload_all()
        self.update_action_buttons_state() # Estado inicial

    def setup_actions_panel(self, parent_layout):
        actions_group = QGroupBox("Ações para o Item Selecionado")
        actions_layout = QHBoxLayout(actions_group)

        self.add_one_btn = QPushButton("+1")
        self.add_one_btn.setToolTip("Adicionar 1 unidade ao estoque do item selecionado")
        self.add_one_btn.clicked.connect(lambda: self.handle_adjust_stock(1))

        self.remove_one_btn = QPushButton("-1")
        self.remove_one_btn.setToolTip("Remover 1 unidade do estoque do item selecionado")
        self.remove_one_btn.clicked.connect(lambda: self.handle_adjust_stock(-1))

        self.edit_item_btn = QPushButton("Editar Item")
        self.edit_item_btn.clicked.connect(self.handle_edit_item)

        self.delete_item_btn = QPushButton("Excluir Item")
        self.delete_item_btn.clicked.connect(self.handle_delete_item)

        # Botão para adicionar novo item (movido para perto das ações)
        self.add_item_button = QPushButton("Adicionar Novo Item")
        self.add_item_button.clicked.connect(self.add_item)

        actions_layout.addWidget(self.add_one_btn)
        actions_layout.addWidget(self.remove_one_btn)
        actions_layout.addStretch()
        actions_layout.addWidget(self.edit_item_btn)
        actions_layout.addWidget(self.delete_item_btn)
        actions_layout.addStretch()
        actions_layout.addWidget(self.add_item_button)

        parent_layout.addWidget(actions_group)

    def get_current_table(self):
        current_widget = self.tabs.currentWidget()
        if current_widget:
            return current_widget.findChild(QTableWidget)
        return None

    def get_selected_item_data(self):
        table = self.get_current_table()
        if table and table.currentItem():
            selected_row = table.currentRow()
            if selected_row >= 0:
                # Recupera o dicionário do item armazenado na primeira coluna
                return table.item(selected_row, 0).data(Qt.ItemDataRole.UserRole)
        return None

    def update_action_buttons_state(self):
        item_selected = self.get_selected_item_data() is not None
        self.add_one_btn.setEnabled(item_selected)
        self.remove_one_btn.setEnabled(item_selected)
        self.edit_item_btn.setEnabled(item_selected)
        self.delete_item_btn.setEnabled(item_selected)

    def _on_selection_changed(self):
        self.update_action_buttons_state()

    def reload_all(self):
        self.group_manager.load_groups()
        self.load_items_by_group()
        self.update_action_buttons_state()

    def load_items_by_group(self):
        self.tabs.clear()
        all_items = sm.get_all_stock_items()
        groups = sm.get_all_stock_groups()

        group_map = {g['id']: {'name': g['nome'], 'items': []} for g in groups}
        for item in all_items:
            if item['grupo_id'] in group_map:
                group_map[item['grupo_id']]['items'].append(item)

        for group_id, group_data in group_map.items():
            # Usar um QWidget como container para a aba
            tab_content_widget = QWidget()
            tab_layout = QVBoxLayout(tab_content_widget)
            
            table = self.create_items_table(group_data['items'])
            # Conecta o sinal de seleção da tabela à atualização dos botões
            table.itemSelectionChanged.connect(self._on_selection_changed)
            tab_layout.addWidget(table)
            
            self.tabs.addTab(tab_content_widget, group_data['name'])

    def handle_adjust_stock(self, amount):
        item = self.get_selected_item_data()
        if not item:
            return

        new_quantity = item['estoque_atual'] + amount
        success, message = sm.adjust_stock_quantity(item['codigo'], new_quantity)
        if success:
            self.reload_all()
        else:
            QMessageBox.warning(self, "Erro", message)

    def handle_edit_item(self):
        item = self.get_selected_item_data()
        if not item:
            return
        self.edit_item(item)

    def handle_delete_item(self):
        item = self.get_selected_item_data()
        if not item:
            return
        self.delete_item(item)

    def create_items_table(self, items):
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Código", "Nome", "Estoque Atual", "Estoque Mínimo", "Unidade"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        
        header = table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        for row_num, item in enumerate(items):
            table.insertRow(row_num)
            table.setItem(row_num, 0, QTableWidgetItem(item['codigo']))
            table.setItem(row_num, 1, QTableWidgetItem(item['nome']))
            table.setItem(row_num, 2, QTableWidgetItem(str(item['estoque_atual'])))
            table.setItem(row_num, 3, QTableWidgetItem(str(item['estoque_minimo'])))
            table.setItem(row_num, 4, QTableWidgetItem(item['unidade_medida']))
            
            # Armazena o dicionário completo do item na primeira coluna para fácil acesso
            table.item(row_num, 0).setData(Qt.ItemDataRole.UserRole, item)

        table.resizeColumnsToContents()
        return table

    def add_item(self):
        dialog = StockItemDialog(parent=self)
        if dialog.exec():
            data = dialog.get_data()
            
            # Validação explícita para melhor feedback ao usuário
            if not data.get('codigo') or not data.get('nome') or not data.get('unidade_medida'):
                QMessageBox.warning(self, "Campos Incompletos", "Os campos 'Código', 'Nome' e 'Unidade' são obrigatórios.")
                return

            if data.get('grupo_id') is None:
                QMessageBox.warning(self, "Grupo Inválido", "Nenhum grupo foi selecionado. Por favor, crie um grupo antes de adicionar um item.")
                return
            
            # Remove a chave 'id' que é None ao adicionar um novo item
            add_data = {k: v for k, v in data.items() if k != 'id'}

            success, message = sm.add_stock_item(**add_data)
            if success:
                QMessageBox.information(self, "Sucesso", "Item adicionado com sucesso.")
                self.reload_all()
            else:
                QMessageBox.warning(self, "Erro ao Adicionar", message)

    def edit_item(self, item):
        dialog = StockItemDialog(item_data=item, parent=self)
        if dialog.exec():
            data = dialog.get_data()
            success, message = sm.update_stock_item(**data)
            if success:
                QMessageBox.information(self, "Sucesso", "Item atualizado com sucesso.")
                self.reload_all()
            else:
                QMessageBox.warning(self, "Erro", message)

    def delete_item(self, item):
        reply = QMessageBox.question(self, "Confirmar Exclusão",
                                     f"Tem certeza que deseja excluir o item '{item['nome']}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            success, message = sm.delete_stock_item(item['id'])
            if success:
                QMessageBox.information(self, "Sucesso", "Item excluído com sucesso.")
                self.reload_all()
            else:
                QMessageBox.warning(self, "Erro", message)


