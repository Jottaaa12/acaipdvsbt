from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QLineEdit,
    QGroupBox, QGridLayout, QFrame, QSpacerItem, QSizePolicy,
    QMessageBox
)
from PyQt6.QtGui import QFont, QShortcut, QKeySequence, QPixmap
from PyQt6.QtCore import Qt, QSize
from decimal import Decimal
from ui.theme import ModernTheme
import logging

class HeldSalesDialog(QDialog):
    """Diálogo moderno para gerenciar vendas em espera (comandas)"""

    def __init__(self, held_sales, mode="resume", parent=None, suggested_name=None):
        """
        Args:
            held_sales: dict com as vendas em espera
            mode: "hold" para salvar venda, "resume" para recuperar
            parent: widget pai
            suggested_name: nome sugerido para a venda (apenas para modo hold)
        """
        super().__init__(parent)
        self.held_sales = held_sales
        self.mode = mode
        self.selected_sale_key = None
        self.search_text = ""

        # Para modo hold: nova venda a ser salva
        self.new_sale_items = []
        self.new_sale_identifier = ""
        self.default_identifier = self.generate_default_identifier()

        self.setup_ui()
        self.setup_shortcuts()
        self.update_display()

        if mode == "resume" and not held_sales:
            QMessageBox.information(self, "Sem Vendas", "Não há vendas salvas em espera.")
            self.reject()

        # Configurações específicas por modo
        if mode == "hold":
            # Configurar campo de entrada com placeholder inteligente
            if hasattr(self, 'identifier_input'):
                # Usar nome sugerido se disponível, senão usar padrão
                initial_name = suggested_name if suggested_name else self.default_identifier
                self.identifier_input.setText(initial_name)
                self.identifier_input.selectAll()  # Selecionar todo o texto para facilitar substituição
                self.identifier_input.setFocus()
                self.new_sale_identifier = initial_name  # Definir valor inicial
                if self.save_button:
                    self.save_button.setEnabled(True)  # Habilitar botão já que tem texto padrão

        elif mode == "resume" and self.held_sales:
            # Selecionar automaticamente a primeira venda
            if self.sales_list.count() > 0:
                self.sales_list.setCurrentRow(0)

    def setup_ui(self):
        """Configura a interface do diálogo"""
        self.setWindowTitle("Gerenciar Vendas em Espera" if self.mode == "resume" else "Salvar Venda")
        self.setModal(True)
        self.setMinimumSize(800, 600)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {ModernTheme.GRAY_LIGHTER};
                border-radius: 12px;
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Título
        title_label = QLabel("Vendas em Espera (Comandas)" if self.mode == "resume" else "Salvar Venda em Espera")
        title_label.setObjectName("title")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # Layout principal
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)

        # Painel esquerdo - Lista de vendas
        left_panel = self.create_left_panel()
        content_layout.addWidget(left_panel, 2)

        # Painel direito - Detalhes/Preview
        right_panel = self.create_right_panel()
        content_layout.addWidget(right_panel, 3)

        # Botões de ação
        buttons_layout = self.create_buttons_layout()
        main_layout.addLayout(buttons_layout)

    def create_left_panel(self):
        """Cria o painel esquerdo com lista de vendas"""
        panel = QFrame()
        panel.setObjectName("card")
        panel.setMinimumWidth(300)

        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        # Cabeçalho
        header_label = QLabel("Vendas Salvas" if self.mode == "resume" else "Nova Venda")
        header_label.setObjectName("card_title")
        layout.addWidget(header_label)

        # Campo de busca (apenas para modo resume)
        if self.mode == "resume":
            search_layout = QHBoxLayout()
            search_label = QLabel("🔍 Buscar:")
            self.search_input = QLineEdit()
            self.search_input.setObjectName("modern_input")
            self.search_input.setPlaceholderText("Digite para filtrar...")
            self.search_input.textChanged.connect(self.on_search_changed)
            search_layout.addWidget(search_label)
            search_layout.addWidget(self.search_input)
            layout.addLayout(search_layout)

        # Lista de vendas
        self.sales_list = QListWidget()
        self.sales_list.setObjectName("sales_list")
        self.sales_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {ModernTheme.WHITE};
                border: 1px solid {ModernTheme.GRAY_LIGHT};
                border-radius: 8px;
                font-size: 14px;
                selection-background-color: {ModernTheme.PRIMARY_LIGHTEST};
                alternate-background-color: {ModernTheme.GRAY_LIGHTER};
            }}
            QListWidget::item {{
                padding: 12px;
                border-bottom: 1px solid {ModernTheme.GRAY_LIGHT};
            }}
            QListWidget::item:selected {{
                background-color: {ModernTheme.PRIMARY_LIGHTEST};
                color: {ModernTheme.PRIMARY_DARK};
                font-weight: bold;
            }}
            QListWidget::item:hover {{
                background-color: {ModernTheme.PRIMARY_LIGHTEST};
            }}
        """)
        self.sales_list.setAlternatingRowColors(True)
        self.sales_list.itemSelectionChanged.connect(self.on_sale_selected)
        self.sales_list.itemDoubleClicked.connect(self.on_sale_double_clicked)
        layout.addWidget(self.sales_list)

        # Botões rápidos (1-9) para modo resume
        if self.mode == "resume" and self.held_sales:
            quick_buttons_group = QGroupBox("Acesso Rápido (1-9)")
            quick_layout = QGridLayout(quick_buttons_group)

            self.quick_buttons = []
            keys = list(self.held_sales.keys())[:9]  # Máximo 9 botões

            for i, key in enumerate(keys):
                button = QPushButton(f"{i+1}")
                button.setObjectName("modern_button_outline")
                button.setMinimumHeight(40)
                button.setMaximumWidth(50)
                button.setToolTip(f"Selecionar: {key}")
                button.clicked.connect(lambda checked, k=key: self.select_sale_by_key(k))
                self.quick_buttons.append(button)
                row = i // 3
                col = i % 3
                quick_layout.addWidget(button, row, col)

            layout.addWidget(quick_buttons_group)

        return panel

    def create_right_panel(self):
        """Cria o painel direito com detalhes da venda"""
        panel = QFrame()
        panel.setObjectName("card")

        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        # Título do painel direito
        if self.mode == "resume":
            details_title = QLabel("Detalhes da Venda Selecionada")
        else:
            details_title = QLabel("Nova Venda a Salvar")
        details_title.setObjectName("card_title")
        layout.addWidget(details_title)

        # Informações da venda
        info_group = QGroupBox("Informações")
        info_layout = QGridLayout(info_group)

        self.identifier_label = QLabel("Identificador:")
        self.identifier_value = QLabel("-")
        self.identifier_value.setStyleSheet(f"font-weight: bold; color: {ModernTheme.PRIMARY};")

        self.items_count_label = QLabel("Itens:")
        self.items_count_value = QLabel("-")

        self.total_label = QLabel("Total:")
        self.total_value = QLabel("R$ 0,00")
        self.total_value.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {ModernTheme.SUCCESS};")

        info_layout.addWidget(self.identifier_label, 0, 0)
        info_layout.addWidget(self.identifier_value, 0, 1)
        info_layout.addWidget(self.items_count_label, 1, 0)
        info_layout.addWidget(self.items_count_value, 1, 1)
        info_layout.addWidget(self.total_label, 2, 0)
        info_layout.addWidget(self.total_value, 2, 1)

        layout.addWidget(info_group)

        # Preview dos itens
        preview_group = QGroupBox("Itens da Venda")
        preview_layout = QVBoxLayout(preview_group)

        self.items_preview = QTextEdit()
        self.items_preview.setReadOnly(True)
        self.items_preview.setMaximumHeight(200)
        self.items_preview.setStyleSheet(f"""
            QTextEdit {{
                background-color: {ModernTheme.WHITE};
                border: 1px solid {ModernTheme.GRAY_LIGHT};
                border-radius: 8px;
                padding: 8px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
            }}
        """)
        preview_layout.addWidget(self.items_preview)

        layout.addWidget(preview_group)

        # Campo para novo identificador (modo hold)
        if self.mode == "hold":
            identifier_group = QGroupBox("Identificador da Venda")
            identifier_layout = QVBoxLayout(identifier_group)

            self.identifier_input = QLineEdit()
            self.identifier_input.setObjectName("modern_input")
            self.identifier_input.setPlaceholderText("Digite o nome ou número da comanda...")
            self.identifier_input.textChanged.connect(self.on_identifier_changed)
            identifier_layout.addWidget(self.identifier_input)

            layout.addWidget(identifier_group)

        return panel

    def create_buttons_layout(self):
        """Cria os botões de ação"""
        layout = QHBoxLayout()

        # Espaçador
        layout.addItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        if self.mode == "resume":
            # Botão Cancelar
            cancel_button = QPushButton("Cancelar (ESC)")
            cancel_button.setObjectName("modern_button_outline")
            cancel_button.clicked.connect(self.reject)
            layout.addWidget(cancel_button)

            # Botão Recuperar
            self.resume_button = QPushButton("Recuperar Venda (Enter)")
            self.resume_button.setObjectName("modern_button_primary")
            self.resume_button.clicked.connect(self.resume_sale)
            self.resume_button.setEnabled(False)
            layout.addWidget(self.resume_button)

        else:  # modo hold
            # Botão Cancelar
            cancel_button = QPushButton("Cancelar (ESC)")
            cancel_button.setObjectName("modern_button_outline")
            cancel_button.clicked.connect(self.reject)
            layout.addWidget(cancel_button)

            # Botão Salvar
            self.save_button = QPushButton("Salvar Venda (Enter)")
            self.save_button.setObjectName("modern_button_primary")
            self.save_button.clicked.connect(self.save_sale)
            self.save_button.setEnabled(False)
            layout.addWidget(self.save_button)

        return layout

    def setup_shortcuts(self):
        """Configura atalhos de teclado"""
        # ESC - Cancelar
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self.reject)

        # Enter - Ação principal
        QShortcut(QKeySequence(Qt.Key.Key_Return), self).activated.connect(self.primary_action)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self).activated.connect(self.primary_action)

        # Navegação com setas
        QShortcut(QKeySequence(Qt.Key.Key_Up), self).activated.connect(self.navigate_up)
        QShortcut(QKeySequence(Qt.Key.Key_Down), self).activated.connect(self.navigate_down)

        # Botões rápidos (1-9)
        if self.mode == "resume":
            for i in range(9):
                key = Qt.Key.Key_1 + i
                QShortcut(QKeySequence(key), self).activated.connect(
                    lambda k=i: self.quick_select(i)
                )

    def update_display(self):
        """Atualiza a exibição da lista de vendas"""
        self.sales_list.clear()

        if self.mode == "resume":
            # Filtrar vendas baseado na busca
            filtered_sales = {}
            if self.search_text:
                for key, items in self.held_sales.items():
                    if self.search_text.lower() in key.lower():
                        filtered_sales[key] = items
            else:
                filtered_sales = self.held_sales

            # Adicionar itens à lista
            for key in sorted(filtered_sales.keys()):
                items = filtered_sales[key]
                total = sum(item['total_price'] for item in items)
                item_count = len(items)

                # Criar texto do item
                display_text = f"{key}\n{item_count} itens - R$ {total:.2f}"

                list_item = QListWidgetItem(display_text)
                list_item.setData(Qt.ItemDataRole.UserRole, key)
                self.sales_list.addItem(list_item)

        else:  # modo hold
            # Mostrar preview da nova venda
            if self.new_sale_items:
                total = sum(item['total_price'] for item in self.new_sale_items)
                item_count = len(self.new_sale_items)
                display_text = f"Nova Venda\n{item_count} itens - R$ {total:.2f}"

                list_item = QListWidgetItem(display_text)
                list_item.setData(Qt.ItemDataRole.UserRole, "new_sale")
                self.sales_list.addItem(list_item)

                # Selecionar automaticamente
                self.sales_list.setCurrentItem(list_item)

    def on_search_changed(self, text):
        """Chamado quando o texto de busca muda"""
        self.search_text = text.strip()
        self.update_display()

    def on_sale_selected(self):
        """Chamado quando uma venda é selecionada"""
        current_item = self.sales_list.currentItem()
        if current_item:
            self.selected_sale_key = current_item.data(Qt.ItemDataRole.UserRole)
            self.update_sale_details()

            # Habilitar botão de ação
            if self.mode == "resume":
                self.resume_button.setEnabled(True)
            else:
                self.save_button.setEnabled(bool(self.new_sale_identifier.strip()))

    def on_sale_double_clicked(self, item):
        """Chamado quando uma venda é clicada duas vezes"""
        self.primary_action()

    def on_identifier_changed(self, text):
        """Chamado quando o identificador muda (modo hold)"""
        self.new_sale_identifier = text.strip()
        if self.save_button:
            self.save_button.setEnabled(bool(text.strip()))

    def update_sale_details(self):
        """Atualiza os detalhes da venda selecionada"""
        if not self.selected_sale_key:
            self.identifier_value.setText("-")
            self.items_count_value.setText("-")
            self.total_value.setText("R$ 0,00")
            self.items_preview.setPlainText("")
            return

        if self.mode == "resume":
            items = self.held_sales.get(self.selected_sale_key, [])
        else:
            items = self.new_sale_items

        # Atualizar informações
        self.identifier_value.setText(self.selected_sale_key)
        self.items_count_value.setText(str(len(items)))

        total = sum(item['total_price'] for item in items)
        self.total_value.setText(f"R$ {total:.2f}")

        # Atualizar preview dos itens
        preview_text = ""
        for i, item in enumerate(items, 1):
            qty_str = f"{item['quantity']:.3f} kg" if item['sale_type'] == 'weight' else f"{int(item['quantity'])} un"
            preview_text += f"{i:2d}. {item['description'][:30]:<30} {qty_str:>8} x R$ {item['unit_price']:>6.2f} = R$ {item['total_price']:>7.2f}\n"

        if not preview_text:
            preview_text = "Nenhum item na venda"

        self.items_preview.setPlainText(preview_text)

    def navigate_up(self):
        """Navega para o item anterior"""
        current_row = self.sales_list.currentRow()
        if current_row > 0:
            self.sales_list.setCurrentRow(current_row - 1)

    def navigate_down(self):
        """Navega para o próximo item"""
        current_row = self.sales_list.currentRow()
        if current_row < self.sales_list.count() - 1:
            self.sales_list.setCurrentRow(current_row + 1)

    def quick_select(self, index):
        """Seleção rápida com teclas 1-9"""
        if self.mode == "resume" and index < self.sales_list.count():
            self.sales_list.setCurrentRow(index)

    def select_sale_by_key(self, key):
        """Seleciona uma venda pela chave"""
        for i in range(self.sales_list.count()):
            item = self.sales_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == key:
                self.sales_list.setCurrentItem(item)
                break

    def primary_action(self):
        """Executa a ação principal (Enter)"""
        if self.mode == "resume":
            self.resume_sale()
        else:
            self.save_sale()

    def resume_sale(self):
        """Recupera a venda selecionada"""
        if not self.selected_sale_key or self.selected_sale_key not in self.held_sales:
            QMessageBox.warning(self, "Seleção Inválida", "Selecione uma venda para recuperar.")
            return

        self.accept()

    def save_sale(self):
        """Salva a nova venda"""
        if not self.new_sale_identifier.strip():
            QMessageBox.warning(self, "Identificador Obrigatório", "Digite um identificador para a venda.")
            return

        if self.new_sale_identifier in self.held_sales:
            reply = QMessageBox.question(
                self, "Identificador Existente",
                f"Já existe uma venda com o identificador '{self.new_sale_identifier}'. Deseja sobrescrever?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.accept()

    def get_result(self):
        """Retorna o resultado do diálogo"""
        if self.mode == "resume":
            return {
                'action': 'resume',
                'sale_key': self.selected_sale_key
            }
        else:
            return {
                'action': 'hold',
                'identifier': self.new_sale_identifier,
                'items': self.new_sale_items
            }

    def generate_default_identifier(self):
        """Gera um identificador padrão do tipo 'Comanda X' onde X é o próximo número disponível"""
        # Procurar por identificadores existentes do tipo "Comanda X"
        existing_numbers = []
        for key in self.held_sales.keys():
            if key.lower().startswith("comanda "):
                try:
                    # Extrair o número após "Comanda "
                    number_str = key[8:].strip()  # Remove "Comanda "
                    number = int(number_str)
                    existing_numbers.append(number)
                except (ValueError, IndexError):
                    continue

        # Encontrar o menor número disponível começando do 1
        next_number = 1
        while next_number in existing_numbers:
            next_number += 1

        return f"Comanda {next_number}"

    @staticmethod
    def show_resume_dialog(held_sales, parent=None):
        """Método estático para mostrar diálogo de recuperação"""
        dialog = HeldSalesDialog(held_sales, mode="resume", parent=parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_result()
        return None

    @staticmethod
    def show_hold_dialog(items, held_sales, parent=None, suggested_name=None):
        """Método estático para mostrar diálogo de salvamento"""
        dialog = HeldSalesDialog(held_sales, mode="hold", parent=parent, suggested_name=suggested_name)
        dialog.new_sale_items = items
        dialog.update_display()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_result()
        return None
