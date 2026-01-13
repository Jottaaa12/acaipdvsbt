"""
Widget para exibir o status de dispositivos Bluetooth conectados.
Fornece indicadores visuais e informações sobre o estado das impressoras Bluetooth.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QFrame,
    QPushButton, QProgressBar, QScrollArea, QGroupBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QPalette, QColor
import logging

class BluetoothDeviceWidget(QFrame):
    """Widget para exibir informações de um dispositivo Bluetooth específico."""

    def __init__(self, device_info, parent=None):
        super().__init__(parent)
        self.device_info = device_info
        self.setup_ui()
        self.update_status()

    def setup_ui(self):
        """Configura a interface do widget do dispositivo."""
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        # Indicador de status (círculo colorido)
        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(16, 16)
        self.status_indicator.setStyleSheet("border-radius: 8px; border: 1px solid #ccc;")
        layout.addWidget(self.status_indicator)

        # Informações do dispositivo
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        self.name_label = QLabel()
        self.name_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))

        self.port_label = QLabel()
        self.port_label.setFont(QFont("Arial", 8))
        self.port_label.setStyleSheet("color: #666;")

        self.status_label = QLabel()
        self.status_label.setFont(QFont("Arial", 8))

        info_layout.addWidget(self.name_label)
        info_layout.addWidget(self.port_label)
        info_layout.addWidget(self.status_label)

        layout.addLayout(info_layout)
        layout.addStretch()

        # Botão de ações (se necessário)
        self.action_button = QPushButton("🔄")
        self.action_button.setFixedSize(24, 24)
        self.action_button.setToolTip("Testar conectividade")
        self.action_button.clicked.connect(self.test_connectivity)
        layout.addWidget(self.action_button)

    def update_status(self):
        """Atualiza a exibição do status do dispositivo."""
        device = self.device_info

        # Nome do dispositivo
        name = device.get('name', f'Dispositivo ({device.get("port", "N/A")})')
        self.name_label.setText(name)

        # Porta
        port = device.get('port', 'N/A')
        self.port_label.setText(f'Porta: {port}')

        # Status
        is_connected = device.get('is_connected', False)
        connection_attempts = device.get('connection_attempts', 0)
        last_error = device.get('last_error', '')

        if is_connected:
            self.status_label.setText("Conectado")
            self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")
            self.status_indicator.setStyleSheet("background-color: #28a745; border-radius: 8px; border: 1px solid #ccc;")
            self.action_button.setText("✓")
            self.action_button.setEnabled(False)
        elif connection_attempts > 0:
            self.status_label.setText(f"Tentativas: {connection_attempts}")
            self.status_label.setStyleSheet("color: #ffc107;")
            self.status_indicator.setStyleSheet("background-color: #ffc107; border-radius: 8px; border: 1px solid #ccc;")
            self.action_button.setText("🔄")
            self.action_button.setEnabled(True)
        elif last_error:
            self.status_label.setText("Erro de conexão")
            self.status_label.setStyleSheet("color: #dc3545;")
            self.status_indicator.setStyleSheet("background-color: #dc3545; border-radius: 8px; border: 1px solid #ccc;")
            self.action_button.setText("⚠")
            self.action_button.setEnabled(True)
        else:
            self.status_label.setText("Desconhecido")
            self.status_label.setStyleSheet("color: #6c757d;")
            self.status_indicator.setStyleSheet("background-color: #6c757d; border-radius: 8px; border: 1px solid #ccc;")
            self.action_button.setText("?")
            self.action_button.setEnabled(True)

    def test_connectivity(self):
        """Testa a conectividade do dispositivo."""
        # Este método será conectado ao sinal do widget pai
        pass

class BluetoothStatusWidget(QWidget):
    """
    Widget principal para monitoramento do status Bluetooth.
    Exibe informações sobre dispositivos Bluetooth e permite ações.
    """

    # Sinais
    connectivity_test_requested = pyqtSignal(str)  # Emite porta do dispositivo
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.devices = []
        self.monitoring_active = False
        self.reconnect_active = False
        self.setup_ui()
        self.setup_timer()

    def setup_ui(self):
        """Configura a interface principal do widget."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Título
        title_layout = QHBoxLayout()

        title_label = QLabel("📱 Status Bluetooth")
        title_font = QFont("Arial", 12, QFont.Weight.Bold)
        title_label.setFont(title_font)

        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # Botão de refresh
        self.refresh_button = QPushButton("🔄")
        self.refresh_button.setFixedSize(30, 30)
        self.refresh_button.setToolTip("Atualizar status")
        self.refresh_button.clicked.connect(self.request_refresh)
        title_layout.addWidget(self.refresh_button)

        main_layout.addLayout(title_layout)

        # Área de scroll para dispositivos
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setMaximumHeight(200)

        self.devices_container = QWidget()
        self.devices_layout = QVBoxLayout(self.devices_container)
        self.devices_layout.setSpacing(5)
        self.devices_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area.setWidget(self.devices_container)
        main_layout.addWidget(scroll_area)

        # Status geral
        status_group = QGroupBox("Status Geral")
        status_layout = QVBoxLayout(status_group)

        self.status_info_label = QLabel()
        self.status_info_label.setWordWrap(True)
        status_layout.addWidget(self.status_info_label)

        # Barra de progresso para reconexão
        self.reconnect_progress = QProgressBar()
        self.reconnect_progress.setVisible(False)
        self.reconnect_progress.setRange(0, 100)
        status_layout.addWidget(self.reconnect_progress)

        main_layout.addWidget(status_group)

        # Botões de ação
        buttons_layout = QHBoxLayout()

        self.scan_button = QPushButton("🔍 Escanear Dispositivos")
        self.scan_button.clicked.connect(self.request_refresh)
        buttons_layout.addWidget(self.scan_button)

        self.test_all_button = QPushButton("🧪 Testar Todos")
        self.test_all_button.clicked.connect(self.test_all_devices)
        buttons_layout.addWidget(self.test_all_button)

        main_layout.addLayout(buttons_layout)

        # Mensagem quando não há dispositivos
        self.no_devices_label = QLabel("Nenhum dispositivo Bluetooth detectado")
        self.no_devices_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_devices_label.setStyleSheet("color: #6c757d; font-style: italic;")
        main_layout.addWidget(self.no_devices_label)
        self.no_devices_label.setVisible(False)

    def setup_timer(self):
        """Configura timer para atualização automática."""
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(5000)  # Atualiza a cada 5 segundos

    def update_devices(self, devices_info):
        """
        Atualiza a lista de dispositivos exibidos.

        Args:
            devices_info: Dicionário com informações dos dispositivos
        """
        self.devices = devices_info.get('devices', [])

        # Limpa dispositivos existentes
        while self.devices_layout.count():
            child = self.devices_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Adiciona novos dispositivos
        for device_info in self.devices:
            device_widget = BluetoothDeviceWidget(device_info)
            device_widget.test_connectivity.connect(
                lambda port=device_info.get('port'): self.connectivity_test_requested.emit(port)
            )
            self.devices_layout.addWidget(device_widget)

        # Atualiza status geral
        self.update_general_status(devices_info)

        # Mostra/esconde mensagem de "sem dispositivos"
        self.no_devices_label.setVisible(len(self.devices) == 0)

    def update_general_status(self, devices_info):
        """Atualiza as informações de status geral."""
        available = devices_info.get('available_devices', 0)
        connected = devices_info.get('connected_devices', 0)
        monitoring = devices_info.get('monitoring_active', False)
        reconnecting = devices_info.get('reconnect_active', False)
        attempts = devices_info.get('reconnect_attempts', 0)

        status_parts = []
        status_parts.append(f"Dispositivos disponíveis: {available}")
        status_parts.append(f"Conectados: {connected}")

        if monitoring:
            status_parts.append("Monitoramento: Ativo")
        else:
            status_parts.append("Monitoramento: Inativo")

        if reconnecting:
            status_parts.append(f"Reconexão em andamento (tentativa {attempts})")
            self.reconnect_progress.setVisible(True)
            # Simula progresso baseado no número de tentativas
            progress = min(attempts * 20, 90)
            self.reconnect_progress.setValue(progress)
        else:
            self.reconnect_progress.setVisible(False)

        self.status_info_label.setText(" | ".join(status_parts))

        # Atualiza cores baseado no status
        if connected > 0:
            self.status_info_label.setStyleSheet("color: #28a745;")  # Verde
        elif available > 0:
            self.status_info_label.setStyleSheet("color: #ffc107;")  # Amarelo
        else:
            self.status_info_label.setStyleSheet("color: #dc3545;")  # Vermelho

    def update_display(self):
        """Atualiza a exibição (chamado pelo timer)."""
        # Este método pode ser usado para atualizações automáticas
        pass

    def request_refresh(self):
        """Solicita atualização dos dados."""
        self.refresh_requested.emit()

    def test_all_devices(self):
        """Testa conectividade de todos os dispositivos."""
        for device in self.devices:
            port = device.get('port')
            if port:
                self.connectivity_test_requested.emit(port)

    def set_monitoring_status(self, active: bool):
        """Atualiza o indicador de monitoramento."""
        self.monitoring_active = active
        # Pode atualizar visualmente se necessário

    def set_reconnect_status(self, active: bool, attempts: int = 0):
        """Atualiza o indicador de reconexão."""
        self.reconnect_active = active
        if active and attempts > 0:
            self.reconnect_progress.setVisible(True)
            progress = min(attempts * 25, 100)
            self.reconnect_progress.setValue(progress)
        else:
            self.reconnect_progress.setVisible(False)
