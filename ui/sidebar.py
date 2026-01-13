from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QScrollArea, QWidget
from PyQt6.QtCore import pyqtSignal, Qt
from ui.theme import IconTheme, ThemeManager

class ModernSidebar(QFrame):
    """Sidebar moderna retrátil"""
    
    page_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.expanded = True
        self.active_button = None
        self.setObjectName("sidebar")
        self.setFixedWidth(250)
        
        self.setup_ui()
        
    def setup_ui(self):
        """Configura a interface da sidebar"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header da sidebar
        header = QFrame()
        header.setFixedHeight(80)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 20, 20, 20)
        
        # Logo e título
        self.logo_label = QLabel("🍇")
        self.logo_label.setObjectName("logoLabel")
        self.title_label = QLabel("PDV Moderno")
        self.title_label.setObjectName("dashboardTitleLabel")
        
        header_layout.addWidget(self.logo_label)
        header_layout.addWidget(self.title_label)
        layout.addWidget(header)

        # Separador
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setObjectName("sidebarSeparator")
        layout.addWidget(separator)
        
        # Menu area com Scroll
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setObjectName("sidebarScrollArea")
        
        # Estilo para o scrollbar ficar discreto ou invisível se preferir
        self.scroll_area.setStyleSheet("""
            QScrollArea#sidebarScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 4px; background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); border-radius: 2px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)

        self.menu_container = QWidget() # Mudado de QFrame para QWidget para usar no ScrollArea
        self.menu_container.setObjectName("sidebarMenuContainer")
        self.menu_container.setStyleSheet("background: transparent;") # Garante fundo transparente
        menu_layout = QVBoxLayout(self.menu_container)
        menu_layout.setContentsMargins(0, 10, 0, 10) # Margens reduzidas
        menu_layout.setSpacing(5)
        
        self.scroll_area.setWidget(self.menu_container)
        layout.addWidget(self.scroll_area) # Adiciona o ScrollArea ao layout principal da Sidebar
        
        # Botões do menu
        self.menu_buttons = {}
        menu_items = [
            ("dashboard", f"{IconTheme.DASHBOARD} Dashboard", "dashboard"),
            ("sales", f"{IconTheme.SALES} Vendas", "sales"),
            ("sales_history", f"{IconTheme.HISTORY} Histórico", "sales_history"),
            ("credit", f"💳 Fiados", "credit"),
            ("products", f"{IconTheme.PRODUCTS} Produtos", "products"),
            ("customers", f"👥 Clientes", "customers"),
            ("stock", f"{IconTheme.PRODUCTS} Estoque", "stock"),
            ("reports", f"{IconTheme.REPORTS} Relatórios", "reports"),
            ("cash", f"{IconTheme.CASH} Caixa", "cash"),
            ("settings", f"{IconTheme.SETTINGS} Configurações", "settings"),
        ]
        
        for key, text, page in menu_items:
            button = QPushButton(text)
            button.setObjectName("sidebar_button")
            button.clicked.connect(lambda checked, p=page: self.page_changed.emit(p))
            self.menu_buttons[key] = button
            menu_layout.addWidget(button)
        
        menu_layout.addStretch()
        # Botão Tema
        self.theme_button = QPushButton("🌓 Tema")
        self.theme_button.setObjectName("sidebar_button")
        menu_layout.addWidget(self.theme_button)

        # Botão logout
        self.logout_button = QPushButton(f"{IconTheme.LOGOUT} Sair")
        self.logout_button.setObjectName("sidebar_button")
        menu_layout.addWidget(self.logout_button)
        
        layout.addWidget(self.scroll_area)
        
        # Define dashboard como ativo por padrão
        self.set_active_button(self.menu_buttons["dashboard"])
    
    def set_active_button(self, button):
        """Sets the visual style for the active sidebar button."""
        if self.active_button:
            self.active_button.setProperty("active", False)
            self.active_button.style().unpolish(self.active_button)
            self.active_button.style().polish(self.active_button)
        
        button.setProperty("active", True)
        button.style().unpolish(button)
        button.style().polish(button)

        self.active_button = button
    
    def toggle_sidebar(self):
        """Alterna entre expandido e retraído"""
        if self.expanded:
            self.collapse()
        else:
            self.expand()
    
    def collapse(self):
        """Recolhe a sidebar"""
        self.expanded = False
        self.setFixedWidth(70)
        
        # Esconde textos
        self.title_label.hide()
        for button in self.menu_buttons.values():
            # Mantém apenas o ícone
            text = button.text()
            icon = text.split()[0] if text else ""
            button.setText(icon)
        
        # Botão tema
        self.theme_button.setText("🌓")

        logout_text = self.logout_button.text()
        logout_icon = logout_text.split()[0] if logout_text else ""
        self.logout_button.setText(logout_icon)
    
    def expand(self):
        """Expande a sidebar"""
        self.expanded = True
        self.setFixedWidth(250)
        
        # Mostra textos
        self.title_label.show()
        
        # Restaura textos dos botões
        menu_items = [
            ("dashboard", f"{IconTheme.DASHBOARD} Dashboard"),
            ("sales", f"{IconTheme.SALES} Vendas"),
            ("sales_history", f"{IconTheme.HISTORY} Histórico"),
            ("credit", f"💳 Fiados"),
            ("products", f"{IconTheme.PRODUCTS} Produtos"),
            ("customers", f"👥 Clientes"),
            ("stock", f"{IconTheme.PRODUCTS} Estoque"),
            ("reports", f"{IconTheme.REPORTS} Relatórios"),
            ("cash", f"{IconTheme.CASH} Caixa"),
            ("settings", f"{IconTheme.SETTINGS} Configurações"),
        ]
        
        for key, text in menu_items:
            if key in self.menu_buttons:
                self.menu_buttons[key].setText(text)
        
        self.theme_button.setText("🌓 Tema")
        self.logout_button.setText(f"{IconTheme.LOGOUT} Sair")
