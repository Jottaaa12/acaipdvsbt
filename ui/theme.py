"""
Sistema de cores e tema moderno para PDV Açaí
Paleta: Roxo e Amarelo com sombras e profundidade
"""

class ModernTheme:
    """Tema moderno com paleta roxo/amarelo"""
    
    # Cores Primárias (Roxo)
    PRIMARY_DARK = "#4c1d95"      # Roxo escuro
    PRIMARY = "#6f42c1"           # Roxo principal
    PRIMARY_LIGHT = "#8b5cf6"     # Roxo médio
    PRIMARY_LIGHTER = "#a855f7"   # Roxo claro
    PRIMARY_LIGHTEST = "#c084fc"  # Roxo muito claro
    
    # Cores Secundárias (Amarelo)
    SECONDARY_DARK = "#d97706"    # Amarelo escuro
    SECONDARY = "#f59e0b"         # Amarelo principal
    SECONDARY_LIGHT = "#fbbf24"   # Amarelo médio
    SECONDARY_LIGHTER = "#fcd34d" # Amarelo claro
    SECONDARY_LIGHTEST = "#fef3c7" # Amarelo muito claro
    
    # Cores Neutras
    DARK = "#1f2937"              # Cinza escuro
    DARK_LIGHT = "#374151"        # Cinza médio escuro
    GRAY = "#6b7280"              # Cinza médio
    GRAY_LIGHT = "#d1d5db"        # Cinza claro
    GRAY_LIGHTER = "#f3f4f6"      # Cinza muito claro
    WHITE = "#ffffff"             # Branco
    
    # Cores de Status
    SUCCESS = "#10b981"           # Verde sucesso
    SUCCESS_LIGHT = "#2ecc71"
    SUCCESS_DARK = "#16a085"
    WARNING = "#f59e0b"           # Amarelo aviso
    ERROR = "#ef4444"             # Vermelho erro
    ERROR_LIGHT = "#e74c3c"
    INFO = "#3b82f6"              # Azul informação
    INFO_DARK = "#2980b9"
    INFO_LIGHT = "#3498db"
    
    # Gradientes
    GRADIENT_PRIMARY = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {PRIMARY}, stop:1 {PRIMARY_LIGHT})"
    GRADIENT_SECONDARY = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {SECONDARY}, stop:1 {SECONDARY_LIGHT})"
    GRADIENT_PURPLE_YELLOW = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {PRIMARY}, stop:1 {SECONDARY})"
    
    @staticmethod
    def get_main_stylesheet():
        """Retorna o stylesheet principal da aplicação"""
        return f"""
        /* === APLICAÇÃO PRINCIPAL === */
        QMainWindow {{
            background-color: {ModernTheme.GRAY_LIGHTER};
            color: {ModernTheme.DARK};
            font-family: 'Segoe UI', Arial, sans-serif;
        }}
        
        /* === SIDEBAR === */
        QFrame#sidebar {{
            background: {ModernTheme.GRADIENT_PRIMARY};
            border: none;
            border-radius: 0px;
        }}
        
        QFrame#sidebar_collapsed {{
            background: {ModernTheme.GRADIENT_PRIMARY};
            border: none;
            border-radius: 0px;
            max-width: 60px;
        }}
        
        /* === BOTÕES SIDEBAR === */
        QPushButton#sidebar_button {{
            background-color: transparent;
            color: {ModernTheme.WHITE};
            border: none;
            padding: 15px 20px;
            text-align: left;
            font-size: 14px;
            font-weight: 500;
            border-radius: 8px;
            margin: 2px 8px;
        }}
        
        QPushButton#sidebar_button:hover {{
            background-color: rgba(255, 255, 255, 0.1);
        }}
        
        QPushButton#sidebar_button:pressed {{
            background-color: rgba(255, 255, 255, 0.2);
        }}
        
        QPushButton#sidebar_button[active="true"] {{
            background-color: {ModernTheme.WHITE};
            color: {ModernTheme.PRIMARY};
            font-weight: 600;
        }}
        
        /* === CARDS === */
        QFrame#card {{
            background-color: {ModernTheme.WHITE};
            border: 1px solid {ModernTheme.GRAY_LIGHT};
            border-radius: 12px;
            padding: 20px;
        }}
        
        QFrame#card_shadow {{
            background-color: {ModernTheme.WHITE};
            border: none;
            border-radius: 12px;
            padding: 20px;
        }}

        QFrame#metricCard {{
            background-color: {ModernTheme.WHITE};
            border: none;
            border-radius: 12px;
            padding: 15px;
        }}
        
        /* === BOTÕES MODERNOS === */
        QPushButton#modern_button_primary {{
            background: {ModernTheme.GRADIENT_PRIMARY};
            color: {ModernTheme.WHITE};
            border: none;
            padding: 8px 24px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            min-height: 20px;
        }}
        
        QPushButton#modern_button_primary:hover {{
            background: {ModernTheme.PRIMARY_DARK};
        }}
        
        QPushButton#modern_button_primary:pressed {{
            background: {ModernTheme.PRIMARY_DARK};
        }}
        
        QPushButton#modern_button_secondary {{
            background: {ModernTheme.GRADIENT_SECONDARY};
            color: {ModernTheme.WHITE};
            border: none;
            padding: 8px 24px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            min-height: 20px;
        }}
        
        QPushButton#modern_button_secondary:hover {{
            background: {ModernTheme.SECONDARY_DARK};
        }}
        
        QPushButton#modern_button_outline {{
            background-color: transparent;
            color: {ModernTheme.PRIMARY};
            border: 2px solid {ModernTheme.PRIMARY};
            padding: 8px 22px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            min-height: 20px;
        }}
        
        QPushButton#modern_button_outline:hover {{
            background-color: {ModernTheme.PRIMARY};
            color: {ModernTheme.WHITE};
        }}

        QPushButton#modern_button_error {{
            background-color: {ModernTheme.ERROR};
            color: {ModernTheme.WHITE};
            border: none;
            padding: 8px 22px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            min-height: 20px;
        }}

        QPushButton#modern_button_error:hover {{
            background-color: #d02d2d; /* Cor mais escura para hover */
        }}
        
        /* === INPUTS MODERNOS === */
        QLineEdit#modern_input {{
            background-color: {ModernTheme.WHITE};
            border: 2px solid {ModernTheme.GRAY_LIGHT};
            border-radius: 8px;
            padding: 8px 16px;
            font-size: 14px;
            color: {ModernTheme.DARK};
            min-height: 20px;
        }}
        
        QLineEdit#modern_input:focus {{
            border-color: {ModernTheme.PRIMARY};
            background-color: {ModernTheme.WHITE};
        }}
        
        QComboBox#modern_combo {{
            background-color: {ModernTheme.WHITE};
            border: 2px solid {ModernTheme.GRAY_LIGHT};
            border-radius: 8px;
            padding: 8px 16px;
            font-size: 14px;
            color: {ModernTheme.DARK};
            min-height: 20px;
        }}
        
        QComboBox#modern_combo:focus {{
            border-color: {ModernTheme.PRIMARY};
        }}
        
        QComboBox#modern_combo::drop-down {{
            border: none;
            width: 30px;
        }}
        
        QComboBox#modern_combo::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid {ModernTheme.GRAY};
            margin-right: 10px;
        }}
        
        /* === GENERIC LABEL === */
        QLabel {{
            color: {ModernTheme.DARK};
            font-size: 14px;
        }}
        
        /* === LABELS === */
        QLabel#title {{
            color: {ModernTheme.DARK};
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 10px;
        }}
        
        QLabel#subtitle {{
            color: {ModernTheme.GRAY};
            font-size: 16px;
            font-weight: 500;
            margin-bottom: 20px;
        }}
        
        QLabel#card_title {{
            color: {ModernTheme.DARK};
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 10px;
        }}
        
        QLabel#metric_value {{
            color: {ModernTheme.PRIMARY};
            font-size: 32px;
            font-weight: 700;
        }}
        
        QLabel#metric_label {{
            color: {ModernTheme.GRAY};
            font-size: 14px;
            font-weight: 500;
        }}

        QLabel#logoLabel {{
            font-size: 32px;
        }}

        QLabel#dashboardTitleLabel {{
            color: {ModernTheme.PRIMARY_DARK};
            font-size: 28px;
            font-weight: 700;
        }}

        QFrame#sidebarSeparator {{
            background-color: rgba(255, 255, 255, 0.2);
            height: 1px;
        }}

        QLabel#metricIcon {{
            font-size: 24px;
        }}

        QLabel#metricValue {{
            font-size: 24px;
            font-weight: 700;
        }}

        QLabel#metricLabel {{
            color: {ModernTheme.GRAY};
            font-size: 12px;
            font-weight: 500;
        }}

        QLabel#form_label {{
            color: {ModernTheme.DARK};
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 5px;
        }}
        
        /* === TABELAS === */
        QTableWidget {{
            background-color: {ModernTheme.WHITE};
            border: 1px solid {ModernTheme.GRAY_LIGHT};
            border-radius: 8px;
            gridline-color: {ModernTheme.GRAY_LIGHT};
            font-size: 14px;
        }}
        
        QTableWidget::item {{
            padding: 12px 8px;
            border-bottom: 1px solid {ModernTheme.GRAY_LIGHT};
            color: {ModernTheme.DARK};
        }}
        
        QTableWidget::item:selected {{
            background-color: {ModernTheme.PRIMARY_LIGHTEST};
            color: {ModernTheme.PRIMARY_DARK};
        }}
        
        QHeaderView::section {{
            background: {ModernTheme.GRADIENT_PRIMARY};
            color: {ModernTheme.WHITE};
            padding: 12px 8px;
            border: none;
            font-weight: 600;
            font-size: 14px;
        }}
        
        /* === STATUS BAR === */
        QStatusBar {{
            background: {ModernTheme.GRADIENT_PRIMARY};
            color: {ModernTheme.WHITE};
            border: none;
            font-size: 12px;
            padding: 5px;
        }}
        
        QStatusBar QLabel {{
            color: {ModernTheme.WHITE};
            padding: 5px 10px;
            border-radius: 4px;
            margin: 2px;
        }}
        
        /* === MENU BAR === */
        QMenuBar {{
            background: {ModernTheme.WHITE};
            color: {ModernTheme.DARK};
            border-bottom: 1px solid {ModernTheme.GRAY_LIGHT};
            padding: 5px;
        }}
        
        QMenuBar::item {{
            background: transparent;
            padding: 8px 12px;
            border-radius: 4px;
        }}
        
        QMenuBar::item:selected {{
            background: {ModernTheme.PRIMARY_LIGHTEST};
            color: {ModernTheme.PRIMARY_DARK};
        }}
        
        QMenu {{
            background: {ModernTheme.WHITE};
            border: 1px solid {ModernTheme.GRAY_LIGHT};
            border-radius: 8px;
            padding: 5px;
        }}
        
        QMenu::item {{
            padding: 8px 16px;
            border-radius: 4px;
        }}
        
        QMenu::item:selected {{
            background: {ModernTheme.PRIMARY_LIGHTEST};
            color: {ModernTheme.PRIMARY_DARK};
        }}

        /* === GROUPBOX === */
        QGroupBox {{
            background-color: {ModernTheme.WHITE};
            border: 1px solid {ModernTheme.GRAY_LIGHT};
            border-radius: 8px;
            margin-top: 15px;
            padding: 10px;
            font-size: 14px;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 10px;
            left: 10px;
            color: {ModernTheme.PRIMARY};
            font-weight: bold;
        }}

        QFrame#dashboardContentContainer {{
            background-color: {ModernTheme.GRAY_LIGHTER};
        }}

        ModernDashboard {{
            background-color: transparent;
        }}

        QLabel#dashboardTitle {{
            color: {ModernTheme.DARK};
            font-size: 28px;
            font-weight: 700;
        }}

        QLabel#dashboardSubtitle {{
            color: {ModernTheme.GRAY};
            font-size: 16px;
        }}

        QTableWidget#dashboardTable {{
            border: none;
            background-color: {ModernTheme.WHITE};
        }}

        QHeaderView#dashboardHeader::section {{
            background-color: {ModernTheme.GRAY_LIGHTER};
            padding: 4px;
            border: none;
            font-weight: bold;
        }}

        QLabel#dashboardStatusLabel {{
            font-size: 14px;
        }}
        """

    @staticmethod
    def get_payment_dialog_stylesheet():
        return f"""
            QDialog {{
                background-color: {ModernTheme.DARK_LIGHT};
                color: {ModernTheme.WHITE};
            }}
            QLabel {{
                font-size: 14px;
                color: {ModernTheme.GRAY_LIGHT};
            }}
            QLabel#totalLabel {{
                color: {ModernTheme.WHITE};
                padding-bottom: 10px;
            }}
            QLabel#remainingLabel, QLabel#changeLabel {{
                padding: 5px;
                border-radius: 5px;
            }}
            QLabel#remainingLabel[status=\"warning\"] {{
                background-color: {ModernTheme.WARNING};
            }}
            QLabel#remainingLabel[status=\"success\"] {{
                background-color: {ModernTheme.SUCCESS};
            }}
            QLabel#changeLabel[status=\"success\"] {{
                background-color: {ModernTheme.SUCCESS_LIGHT};
                color: {ModernTheme.WHITE};
                font-weight: bold;
            }}
            QLineEdit {{
                background-color: {ModernTheme.DARK_LIGHT};
                border: 1px solid {ModernTheme.GRAY};
                border-radius: 5px;
                padding: 12px;
                font-size: 18px;
                color: {ModernTheme.WHITE};
            }}
            QListWidget {{
                background-color: {ModernTheme.DARK_LIGHT};
                border: 1px solid {ModernTheme.GRAY};
                border-radius: 5px;
                font-size: 16px;
            }}
            QListWidget::item {{
                padding: 8px;
                color: {ModernTheme.WHITE};
            }}
            QListWidget::item:alternate {{
                background-color: #3a5064;
                color: {ModernTheme.WHITE};
            }}
            
            /* --- Modern Payment Buttons --- */
            QPushButton#paymentMethodButton {{
                background-color: {ModernTheme.DARK_LIGHT};
                color: {ModernTheme.WHITE};
                border: 2px solid {ModernTheme.GRAY};
                padding: 15px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 16px;
                min-height: 45px;
            }}
            QPushButton#paymentMethodButton:hover {{
                background-color: {ModernTheme.GRAY};
                border-color: #5b7d9c;
            }}
            QPushButton#paymentMethodButton:checked {{
                background-color: {ModernTheme.SUCCESS};
                border-color: {ModernTheme.SUCCESS_LIGHT};
                color: white;
            }}

            /* --- Other Buttons --- */
            QPushButton#addPaymentButton {{
                background-color: {ModernTheme.INFO_DARK};
                border: none;
                padding: 12px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton#addPaymentButton:hover {{
                background-color: {ModernTheme.INFO_LIGHT};
            }}
            QPushButton#finalizeButton {{
                background-color: {ModernTheme.SUCCESS};
                border: none;
                padding: 12px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton#finalizeButton:hover {{
                background-color: {ModernTheme.SUCCESS_LIGHT};
            }}
            QPushButton#removePaymentButton {{
                background-color: {ModernTheme.ERROR};
                border: none;
                padding: 12px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton#removePaymentButton:hover {{
                background-color: {ModernTheme.ERROR_LIGHT};
            }}
            QPushButton#creditSaleButton {{
                background-color: {ModernTheme.DARK_LIGHT};
                color: {ModernTheme.WHITE};
                border: 2px solid {ModernTheme.GRAY};
                font-size: 16px;
                padding: 15px;
                border-radius: 8px;
                font-weight: bold;
                min-height: 45px;
            }}
            QPushButton#creditSaleButton:hover {{
                background-color: {ModernTheme.GRAY};
                border-color: #5b7d9c;
            }}
            QPushButton:disabled {{
                background-color: {ModernTheme.GRAY};
                color: {ModernTheme.GRAY_LIGHT};
                border-color: {ModernTheme.GRAY_LIGHT};
            }}
        """
    
    @staticmethod
    def get_login_stylesheet():
        """Retorna o stylesheet para a tela de login"""
        return f"""
        QDialog {{
            background: {ModernTheme.GRADIENT_PURPLE_YELLOW};
            border-radius: 12px;
        }}
        
        QLabel#login_title {{
            color: {ModernTheme.WHITE};
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 10px;
        }}
        
        QLabel#login_subtitle {{
            color: rgba(255, 255, 255, 0.8);
            font-size: 14px;
            font-weight: 400;
            margin-bottom: 30px;
        }}
        
        QFrame#login_form {{
            background-color: {ModernTheme.WHITE};
            border-radius: 12px;
            padding: 30px;
        }}
        
        QPushButton#login_button {{
            background: {ModernTheme.GRADIENT_PRIMARY};
            color: {ModernTheme.WHITE};
            border: none;
            padding: 15px 30px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            min-height: 25px;
        }}
        
        QPushButton#login_button:hover {{
            background: {ModernTheme.PRIMARY_DARK};
        }}
        
        QPushButton#cancel_button {{
            background-color: {ModernTheme.GRAY_LIGHT};
            color: {ModernTheme.DARK};
            border: none;
            padding: 15px 30px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            min-height: 25px;
        }}
        
        QPushButton#cancel_button:hover {{
            background-color: {ModernTheme.GRAY};
            color: {ModernTheme.WHITE};
        }}
        """

class IconTheme:
    """Ícones para o tema moderno"""
    
    # Ícones Unicode para sidebar
    DASHBOARD = "🏠"
    SALES = "💰"
    PRODUCTS = "📦"
    REPORTS = "📊"
    SETTINGS = "⚙️"
    USERS = "👤"
    DATABASE = "🗄️" # Novo ícone para gerenciamento de dados
    CASH = "💵"
    HISTORY = "🕒"
    LOGOUT = "🚪"
    
    # Ícones de ação
    ADD = "➕"
    EDIT = "✏️"
    DELETE = "🗑️"
    SAVE = "💾"
    CANCEL = "❌"
    SEARCH = "🔍"
    FILTER = "🔽"
    PRINT = "🖨️"
    BACKUP = "💾"
    WITHDRAWAL = "➖"
    SYNC = "🔄"

    # Ícones de status
    SUCCESS = "✅"
    WARNING = "⚠️"
    ERROR = "❌"
    INFO = "ℹ️"
    
    # Ícones de hardware
    SCALE = "⚖️"
    PRINTER = "🖨️"
    BARCODE = "📊"

    @staticmethod
    def get_icon(name):
        icons = {
            "open": IconTheme.CASH,
            "close": IconTheme.CANCEL,
            "supply": IconTheme.ADD,
            "withdrawal": IconTheme.WITHDRAWAL,
            "filter": IconTheme.FILTER,
            "dashboard": IconTheme.DASHBOARD,
            "sales": IconTheme.SALES,
            "products": IconTheme.PRODUCTS,
            "reports": IconTheme.REPORTS,
            "settings": IconTheme.SETTINGS,
            "users": IconTheme.USERS,
            "history": IconTheme.HISTORY,
            "logout": IconTheme.LOGOUT,
            "add": IconTheme.ADD,
            "edit": IconTheme.EDIT,
            "delete": IconTheme.DELETE,
            "save": IconTheme.SAVE,
            "cancel": IconTheme.CANCEL,
            "search": IconTheme.SEARCH,
            "print": IconTheme.PRINT,
            "backup": IconTheme.BACKUP,
            "success": IconTheme.SUCCESS,
            "warning": IconTheme.WARNING,
            "error": IconTheme.ERROR,
            "info": IconTheme.INFO,
            "scale": IconTheme.SCALE,
            "printer": IconTheme.PRINTER,
            "barcode": IconTheme.BARCODE,
        }
        return icons.get(name, "")
