"""
Sistema de cores e tema moderno para PDV Açaí
Paleta: Roxo e Amarelo com sombras e profundidade
"""
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor

class ThemeManager:
    """Gerenciador de Temas (Light/Dark)"""

    _instance = None
    
    # Definição das paletas de cores para substituição no QSS
    THEMES = {
        "light": {
            "@PRIMARY_DARK": "#4c1d95",
            "@PRIMARY": "#6f42c1",
            "@PRIMARY_LIGHT": "#8b5cf6",
            "@PRIMARY_LIGHTEST": "#c084fc",
            "@SECONDARY": "#f59e0b",
            "@SECONDARY_DARK": "#d97706",
            "@DARK": "#1f2937",
            "@GRAY": "#6b7280",
            "@GRAY_LIGHT": "#d1d5db",
            "@GRAY_LIGHTER": "#f3f4f6",
            "@WHITE": "#ffffff",
            "@SUCCESS": "#10b981",
            "@ERROR": "#ef4444",
        },
        "dark": {
            "@PRIMARY_DARK": "#3730a3",
            "@PRIMARY": "#6366f1",
            "@PRIMARY_LIGHT": "#818cf8",
            "@PRIMARY_LIGHTEST": "#312e81",
            "@SECONDARY": "#f59e0b",
            "@SECONDARY_DARK": "#b45309",
            "@DARK": "#f3f4f6",
            "@GRAY": "#9ca3af",
            "@GRAY_LIGHT": "#374151",
            "@GRAY_LIGHTER": "#111827",
            "@WHITE": "#1f2937",
            "@SUCCESS": "#10b981",
            "@ERROR": "#ef4444",
        }
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ThemeManager, cls).__new__(cls)
            cls._instance.current_theme = "light"
        return cls._instance

    def load_stylesheet(self, theme_name="light"):
        """Carrega o arquivo QSS e substitui as variáveis"""
        self.current_theme = theme_name
        
        # Caminho para o arquivo QSS - compatível com PyInstaller
        import sys
        if getattr(sys, 'frozen', False):
            # Executando como executável empacotado
            base_path = sys._MEIPASS
        else:
            # Executando em desenvolvimento
            base_path = os.getcwd()
        
        qss_path = os.path.join(base_path, "resources", "styles", f"{theme_name}.qss")
        
        if not os.path.exists(qss_path):
            print(f"Erro: Arquivo de estilo não encontrado: {qss_path}")
            return ""

        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                stylesheet = f.read()
            
            # Substitui as variáveis - IMPORTANTE: ordenar por tamanho (maior primeiro)
            # para evitar que @GRAY seja substituído antes de @GRAY_LIGHTER
            colors = self.THEMES.get(theme_name, self.THEMES["light"])
            sorted_keys = sorted(colors.keys(), key=len, reverse=True)
            for key in sorted_keys:
                stylesheet = stylesheet.replace(key, colors[key])
                
            return stylesheet
        except Exception as e:
            print(f"Erro ao carregar tema: {e}")
            return ""

    def apply_theme(self, app, theme_name="light"):
        """Aplica o tema à aplicação"""
        stylesheet = self.load_stylesheet(theme_name)
        if stylesheet:
            app.setStyleSheet(stylesheet)
            
    def get_color(self, color_name):
        """Retorna a cor atual do tema"""
        colors = self.THEMES.get(self.current_theme, self.THEMES["light"])
        return colors.get(f"@{color_name}", "#000000")

# Mantendo a classe ModernTheme para compatibilidade com código legado que importa constantes
# Mas agora ela busca do ThemeManager
class ModernTheme:
    """Tema moderno com paleta roxo/amarelo (Proxy para ThemeManager)"""
    
    manager = ThemeManager()
    
    # Cores Primárias (Roxo)
    PRIMARY_DARK = manager.get_color("PRIMARY_DARK")
    PRIMARY = manager.get_color("PRIMARY")
    PRIMARY_LIGHT = manager.get_color("PRIMARY_LIGHT")
    PRIMARY_LIGHTEST = manager.get_color("PRIMARY_LIGHTEST")
    
    # Cores Secundárias (Amarelo)
    SECONDARY_DARK = manager.get_color("SECONDARY_DARK")
    SECONDARY = manager.get_color("SECONDARY")
    
    # Cores Neutras
    DARK = manager.get_color("DARK")
    GRAY = manager.get_color("GRAY")
    GRAY_LIGHT = manager.get_color("GRAY_LIGHT")
    GRAY_LIGHTER = manager.get_color("GRAY_LIGHTER")
    WHITE = manager.get_color("WHITE")
    
    # Cores de Status
    SUCCESS = manager.get_color("SUCCESS")
    WARNING = "#f59e0b"
    ERROR = manager.get_color("ERROR")
    INFO = "#3b82f6"
    
    # Gradientes (Estáticos por enquanto, mas poderiam ser dinâmicos)
    GRADIENT_PRIMARY = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {PRIMARY}, stop:1 {PRIMARY_LIGHT})"
    
    @staticmethod
    def get_main_stylesheet():
        """Retorna o stylesheet principal da aplicação (Depreciado, use ThemeManager)"""
        return ThemeManager().load_stylesheet(ThemeManager().current_theme)

    @staticmethod
    def get_payment_dialog_stylesheet():
        """Retorna estilo para o diálogo de pagamento adaptado ao tema atual."""
        """Retorna estilo para o diálogo de pagamento adaptado ao tema atual."""
        # DEPRECATED: Os estilos foram movidos para resources/styles/light.qss e dark.qss
        # e são carregados globalmente pelo ThemeManager.apply_theme()
        return ""
    
    @staticmethod
    def get_login_stylesheet():
        """Retorna o stylesheet para a tela de login"""
        # Simplificado para usar o QSS global, mas mantendo caso seja chamado especificamente
        return ""

class IconTheme:
    """Ícones para o tema moderno"""
    
    # Ícones Unicode para sidebar
    DASHBOARD = "🏠"
    SALES = "💰"
    PRODUCTS = "📦"
    REPORTS = "📊"
    SETTINGS = "⚙️"
    USERS = "👤"
    DATABASE = "🗄️"
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
