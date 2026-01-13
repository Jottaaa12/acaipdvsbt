
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView, QDialog,
    QFormLayout, QComboBox, QSpinBox, QTabWidget, QDialogButtonBox, QGroupBox,
    QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
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
# --- Página Principal de Gerenciamento de Estoque ---
class StockManagementPage(QWidget):
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        # Título
        title_label = QLabel("Gerenciamento de Estoque de Insumos")
        title_label.setObjectName("title")
        main_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Seção de Gerenciamento de Grupos
        self.group_manager = StockGroupManagementWidget()
        self.group_manager.groups_changed.connect(self.reload_all)
        main_layout.addWidget(self.group_manager)

        # Separador visual
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet("background-color: #e5e7eb; margin: 10px 0;") # Gray light
        main_layout.addWidget(sep)

        # Filtro e Tabela
        filter_layout = QHBoxLayout()
        filter_label = QLabel("Filtrar por Grupo:")
        filter_label.setObjectName("form_label")
        self.filter_combo = QComboBox()
        self.filter_combo.setObjectName("modern_combo")
        self.filter_combo.addItem("Todos os Grupos", userData=None)
        self.filter_combo.currentIndexChanged.connect(self.filter_items)
        
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.filter_combo, 1)
        main_layout.addLayout(filter_layout)

        # Tabela Única de Itens
        self.items_table = self.create_items_table()
        self.items_table.itemSelectionChanged.connect(self._on_selection_changed)
        main_layout.addWidget(self.items_table)

        # Painel de Ações para o item selecionado
        self.setup_actions_panel(main_layout)

        # Dados em memória
        self.all_items = []

        self.reload_all()
        self.update_action_buttons_state() # Estado inicial

    def setup_actions_panel(self, parent_layout):
        actions_group = QGroupBox("Ações para o Item Selecionado")
        actions_layout = QHBoxLayout(actions_group)

        self.add_one_btn = QPushButton("+1")
        self.add_one_btn.setObjectName("modern_button_success") # Assuming this style exists or will fallback
        self.add_one_btn.setToolTip("Adicionar 1 unidade ao estoque do item selecionado")
        self.add_one_btn.clicked.connect(lambda: self.handle_adjust_stock(1))

        self.remove_one_btn = QPushButton("-1")
        self.remove_one_btn.setObjectName("modern_button_warning") # Assuming exists or fallback
        self.remove_one_btn.setToolTip("Remover 1 unidade do estoque do item selecionado")
        self.remove_one_btn.clicked.connect(lambda: self.handle_adjust_stock(-1))

        self.edit_item_btn = QPushButton("Editar Item")
        self.edit_item_btn.setObjectName("modern_button_secondary")
        self.edit_item_btn.clicked.connect(self.handle_edit_item)

        self.delete_item_btn = QPushButton("Excluir Item")
        self.delete_item_btn.setObjectName("modern_button_error")
        self.delete_item_btn.clicked.connect(self.handle_delete_item)

        # Botão para adicionar novo item (movido para perto das ações)
        self.add_item_button = QPushButton("Adicionar Novo Item")
        self.add_item_button.setObjectName("modern_button_primary")
        self.add_item_button.clicked.connect(self.add_item)

        actions_layout.addWidget(self.add_one_btn)
        actions_layout.addWidget(self.remove_one_btn)
        actions_layout.addStretch()
        actions_layout.addWidget(self.edit_item_btn)
        actions_layout.addWidget(self.delete_item_btn)
        actions_layout.addStretch()
        actions_layout.addWidget(self.add_item_button)

        parent_layout.addWidget(actions_group)

    def get_selected_item_data(self):
        if self.items_table.currentItem():
            selected_row = self.items_table.currentRow()
            if selected_row >= 0:
                # Recupera o dicionário do item armazenado na primeira coluna
                return self.items_table.item(selected_row, 0).data(Qt.ItemDataRole.UserRole)
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
        self.load_filter_options()
        self.load_all_items() # Carrega todos os dados
        self.filter_items() # Aplica o filtro atual
        self.update_action_buttons_state()

    def load_filter_options(self):
        current_data = self.filter_combo.currentData()
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItem("Todos os Grupos", userData=None)
        
        groups = sm.get_all_stock_groups()
        for group in groups:
            self.filter_combo.addItem(group['nome'], userData=group['id'])
            
        # Restaura seleção se possível
        if current_data is not None:
            index = self.filter_combo.findData(current_data)
            if index != -1:
                self.filter_combo.setCurrentIndex(index)
        
        self.filter_combo.blockSignals(False)

    def load_all_items(self):
        self.all_items = sm.get_all_stock_items()

    def filter_items(self):
        selected_group_id = self.filter_combo.currentData()
        
        filtered_items = []
        if selected_group_id is None:
            filtered_items = self.all_items
        else:
            filtered_items = [item for item in self.all_items if item['grupo_id'] == selected_group_id]
            
        self.populate_table(filtered_items)

    def populate_table(self, items):
        self.items_table.setRowCount(0)
        for row_num, item in enumerate(items):
            self.items_table.insertRow(row_num)
            
            # Formatação de cores para estoque baixo
            is_low_stock = item['estoque_atual'] <= item['estoque_minimo']
            text_color = QColor("#ef4444") if is_low_stock else None # Red for low stock warning
            
            # Código
            code_item = QTableWidgetItem(item['codigo'])
            code_item.setData(Qt.ItemDataRole.UserRole, item) # Store Data here
            if text_color: code_item.setForeground(text_color)
            self.items_table.setItem(row_num, 0, code_item)

            # Nome
            nome_item = QTableWidgetItem(item['nome'])
            if text_color: nome_item.setForeground(text_color)
            self.items_table.setItem(row_num, 1, nome_item)

            # Estoque Atual
            atual_item = QTableWidgetItem(str(item['estoque_atual']))
            if text_color: atual_item.setForeground(text_color)
            self.items_table.setItem(row_num, 2, atual_item)

            # Estoque Mínimo
            min_item = QTableWidgetItem(str(item['estoque_minimo']))
            if text_color: min_item.setForeground(text_color)
            self.items_table.setItem(row_num, 3, min_item)

            # Unidade
            un_item = QTableWidgetItem(item['unidade_medida'])
            if text_color: un_item.setForeground(text_color)
            self.items_table.setItem(row_num, 4, un_item)

        self.items_table.resizeColumnsToContents()

    def handle_adjust_stock(self, amount):
        item = self.get_selected_item_data()
        if not item:
            return

        new_quantity = item['estoque_atual'] + amount
        # Ensure non-negative
        if new_quantity < 0:
            QMessageBox.warning(self, "Ação Inválida", "O estoque não pode ser negativo.")
            return

        success, message = sm.adjust_stock_quantity(item['codigo'], new_quantity)
        if success:
            self.reload_all() # Poderia otimizar e apenas atualizar a linha, mas reload é seguro
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

    def create_items_table(self):
        table = QTableWidget()
        table.setObjectName("table") # Uses global style or specific
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Código", "Nome", "Estoque Atual", "Estoque Mínimo", "Unidade"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        
        header = table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        return table

    def add_item(self):
        dialog = StockItemDialog(parent=self)
        if dialog.exec():
            data = dialog.get_data()
            
            if not data.get('codigo') or not data.get('nome') or not data.get('unidade_medida'):
                QMessageBox.warning(self, "Campos Incompletos", "Os campos 'Código', 'Nome' e 'Unidade' são obrigatórios.")
                return

            if data.get('grupo_id') is None:
                QMessageBox.warning(self, "Grupo Inválido", "Nenhum grupo foi selecionado. Por favor, crie um grupo antes de adicionar um item.")
                return
            
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


