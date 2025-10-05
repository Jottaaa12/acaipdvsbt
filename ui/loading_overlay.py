from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication, QProgressBar
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QPropertyAnimation, QRect, QEasingCurve
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor, QMovie
import os
from typing import Optional

class LoadingOverlay(QWidget):
    """
    Overlay de carregamento moderno e reutilizável para o PDV.
    Pode ser usado para operações assíncronas, processamento de dados,
    conexão com dispositivos, etc.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.message_label = None
        self.progress_bar = None
        self.animation = None
        self.loading_movie = None
        self.fade_animation = None

        # Estado do overlay
        self.is_visible = False
        self.auto_hide_timer = None

        self.setup_ui()
        self.setup_animations()

    def setup_ui(self):
        """Configura a interface do overlay."""
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Layout principal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Container centralizado
        container = QWidget()
        container.setObjectName("loadingContainer")
        container.setStyleSheet("""
            QWidget#loadingContainer {
                background-color: rgba(255, 255, 255, 0.95);
                border-radius: 15px;
                border: 2px solid #e3f2fd;
            }
        """)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(30, 30, 30, 30)
        container_layout.setSpacing(20)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Label de mensagem
        self.message_label = QLabel("Processando...")
        self.message_label.setObjectName("loadingMessage")
        self.message_label.setStyleSheet("""
            QLabel#loadingMessage {
                color: #1976d2;
                font-size: 16px;
                font-weight: 500;
                padding: 10px;
            }
        """)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        container_layout.addWidget(self.message_label)

        # Barra de progresso (opcional)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("loadingProgress")
        self.progress_bar.setStyleSheet("""
            QProgressBar#loadingProgress {
                border: 2px solid #e3f2fd;
                border-radius: 8px;
                text-align: center;
                font-size: 12px;
                font-weight: bold;
                color: #1976d2;
            }
            QProgressBar::chunk#loadingProgress {
                background-color: #2196f3;
                border-radius: 6px;
            }
        """)
        self.progress_bar.setRange(0, 0)  # Indeterminado por padrão
        self.progress_bar.setVisible(False)
        container_layout.addWidget(self.progress_bar)

        # Label para informações adicionais
        self.info_label = QLabel("")
        self.info_label.setObjectName("loadingInfo")
        self.info_label.setStyleSheet("""
            QLabel#loadingInfo {
                color: #666;
                font-size: 12px;
                padding: 5px;
            }
        """)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setWordWrap(True)
        self.info_label.setVisible(False)
        container_layout.addWidget(self.info_label)

        layout.addWidget(container)

        # Configurar tamanho inicial
        self.resize(400, 200)

    def setup_animations(self):
        """Configura animações de entrada/saída."""
        # Animação de fade in/out
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(300)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # Animação de escala
        self.scale_animation = QPropertyAnimation(self, b"geometry")
        self.scale_animation.setDuration(300)
        self.scale_animation.setEasingCurve(QEasingCurve.Type.InOutBack)

    def show_loading(self, message: str = "Processando...",
                    show_progress: bool = False,
                    progress_range: tuple = (0, 0),
                    auto_hide_ms: Optional[int] = None,
                    info_text: str = ""):
        """
        Exibe overlay de carregamento.

        Args:
            message: Mensagem a ser exibida
            show_progress: Se deve mostrar barra de progresso
            progress_range: Tupla (min, max) para barra de progresso
            auto_hide_ms: Tempo em ms para ocultar automaticamente
            info_text: Texto informativo adicional
        """

        # Atualizar conteúdo
        self.message_label.setText(message)

        if show_progress and progress_range != (0, 0):
            self.progress_bar.setRange(progress_range[0], progress_range[1])
            self.progress_bar.setValue(progress_range[0])
            self.progress_bar.setVisible(True)
            self.progress_bar.setFormat("Processando... %p%")
        else:
            self.progress_bar.setVisible(False)

        if info_text:
            self.info_label.setText(info_text)
            self.info_label.setVisible(True)
        else:
            self.info_label.setVisible(False)

        # Configurar tamanho baseado no conteúdo
        self.adjustSize()

        # Posicionar no centro do parent
        if self.parent():
            parent_rect = self.parent().rect()
            self.move(parent_rect.center() - self.rect().center())

        # Configurar auto-hide se especificado
        if auto_hide_ms:
            if self.auto_hide_timer:
                self.auto_hide_timer.stop()
            self.auto_hide_timer = QTimer()
            self.auto_hide_timer.timeout.connect(self.hide_loading)
            self.auto_hide_timer.start(auto_hide_ms)

        # Mostrar com animação
        self.show_with_animation()

    def hide_loading(self):
        """Oculta overlay de carregamento."""
        if self.auto_hide_timer:
            self.auto_hide_timer.stop()
            self.auto_hide_timer = None

        self.hide_with_animation()

    def show_with_animation(self):
        """Mostra o overlay com animação."""
        if self.is_visible:
            return

        self.is_visible = True
        self.show()
        self.raise_()

        # Animação de fade in
        self.setWindowOpacity(0.0)
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()

        # Animação de escala (zoom in)
        start_rect = QRect(self.x() + self.width()//4, self.y() + self.height()//4,
                          self.width()//2, self.height()//2)
        end_rect = QRect(self.x(), self.y(), self.width(), self.height())

        self.scale_animation.setStartValue(start_rect)
        self.scale_animation.setEndValue(end_rect)
        self.scale_animation.start()

    def hide_with_animation(self):
        """Oculta o overlay com animação."""
        if not self.is_visible:
            return

        self.is_visible = False

        # Animação de fade out
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.finished.connect(self._on_fade_out_finished)
        self.fade_animation.start()

    def _on_fade_out_finished(self):
        """Callback quando fade out termina."""
        if not self.is_visible:
            self.hide()
            self.setWindowOpacity(1.0)
        self.fade_animation.finished.disconnect(self._on_fade_out_finished)

    def update_progress(self, value: int, message: str = None):
        """
        Atualiza progresso da barra.

        Args:
            value: Valor do progresso
            message: Nova mensagem (opcional)
        """
        if self.progress_bar.isVisible():
            self.progress_bar.setValue(value)

        if message:
            self.message_label.setText(message)

    def set_progress_range(self, min_value: int, max_value: int):
        """
        Define faixa da barra de progresso.

        Args:
            min_value: Valor mínimo
            max_value: Valor máximo
        """
        self.progress_bar.setRange(min_value, max_value)
        self.progress_bar.setVisible(True)

    def resizeEvent(self, event):
        """Ajusta posição quando redimensionado."""
        super().resizeEvent(event)
        if self.parent():
            parent_rect = self.parent().rect()
            self.move(parent_rect.center() - self.rect().center())

    def paintEvent(self, event):
        """Pinta fundo semi-transparente."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))  # Fundo escuro semi-transparente

class LoadingManager(QObject):
    """
    Gerenciador centralizado de estados de carregamento.
    Permite controle global de múltiplos overlays de carregamento.
    """

    def __init__(self):
        super().__init__()
        self.overlays = {}  # widget -> overlay
        self.global_overlay = None

    def get_overlay(self, widget: QWidget) -> LoadingOverlay:
        """
        Obtém ou cria overlay para um widget específico.

        Args:
            widget: Widget para o qual criar o overlay

        Returns:
            LoadingOverlay: Overlay do widget
        """
        if widget not in self.overlays:
            overlay = LoadingOverlay(widget)
            self.overlays[widget] = overlay

        return self.overlays[widget]

    def show_loading(self, widget: QWidget = None, message: str = "Processando...",
                    show_progress: bool = False, progress_range: tuple = (0, 0),
                    auto_hide_ms: Optional[int] = None, info_text: str = ""):
        """
        Exibe loading para um widget específico ou global.

        Args:
            widget: Widget específico (None para global)
            message: Mensagem de carregamento
            show_progress: Se mostrar barra de progresso
            progress_range: Faixa da barra de progresso
            auto_hide_ms: Auto-hide em milissegundos
            info_text: Texto informativo
        """
        if widget is None:
            # Criar overlay global se necessário
            if self.global_overlay is None:
                self.global_overlay = LoadingOverlay()

            overlay = self.global_overlay
        else:
            overlay = self.get_overlay(widget)

        overlay.show_loading(message, show_progress, progress_range, auto_hide_ms, info_text)

    def hide_loading(self, widget: QWidget = None):
        """
        Oculta loading para um widget específico ou global.

        Args:
            widget: Widget específico (None para global)
        """
        if widget is None:
            if self.global_overlay:
                self.global_overlay.hide_loading()
        else:
            overlay = self.overlays.get(widget)
            if overlay:
                overlay.hide_loading()

    def update_progress(self, widget: QWidget = None, value: int = 0, message: str = None):
        """
        Atualiza progresso para um widget específico ou global.

        Args:
            widget: Widget específico (None para global)
            value: Valor do progresso
            message: Nova mensagem
        """
        if widget is None:
            if self.global_overlay:
                self.global_overlay.update_progress(value, message)
        else:
            overlay = self.overlays.get(widget)
            if overlay:
                overlay.update_progress(value, message)

    def is_loading(self, widget: QWidget = None) -> bool:
        """
        Verifica se há loading ativo para um widget.

        Args:
            widget: Widget específico (None para global)

        Returns:
            bool: True se há loading ativo
        """
        if widget is None:
            return self.global_overlay.is_visible if self.global_overlay else False
        else:
            overlay = self.overlays.get(widget)
            return overlay.is_visible if overlay else False

# Instância global do LoadingManager
loading_manager = LoadingManager()

# Funções de conveniência para uso rápido
def show_loading(message: str = "Processando...", widget: QWidget = None,
                show_progress: bool = False, auto_hide_ms: Optional[int] = None):
    """Mostra loading de forma rápida."""
    loading_manager.show_loading(widget, message, show_progress, auto_hide_ms=auto_hide_ms)

def hide_loading(widget: QWidget = None):
    """Oculta loading de forma rápida."""
    loading_manager.hide_loading(widget)

def update_loading_progress(value: int, message: str = None, widget: QWidget = None):
    """Atualiza progresso do loading."""
    loading_manager.update_progress(widget, value, message)

def is_loading(widget: QWidget = None) -> bool:
    """Verifica se há loading ativo."""
    return loading_manager.is_loading(widget)
