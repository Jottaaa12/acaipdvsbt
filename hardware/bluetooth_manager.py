"""
Gerenciador avançado de dispositivos Bluetooth para impressoras térmicas.
Fornece funcionalidades como detecção automática, reconexão, cache de dispositivos,
testes de conectividade e suporte para múltiplos dispositivos.
"""

import serial.tools.list_ports
import serial
import threading
import time
import logging
import json
import os
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class BluetoothDevice:
    """Representa um dispositivo Bluetooth."""
    name: str
    address: str
    port: str
    is_connected: bool = False
    last_seen: datetime = None
    connection_attempts: int = 0
    last_error: str = ""

    def __post_init__(self):
        if self.last_seen is None:
            self.last_seen = datetime.now()

class BluetoothManager:
    """
    Gerenciador avançado para conexões Bluetooth com impressoras térmicas.
    """

    def __init__(self, config_path: str = None):
        """
        Inicializa o gerenciador Bluetooth.

        Args:
            config_path: Caminho para arquivo de configuração/cache
        """
        # Logger (inicializar primeiro)
        self.logger = logging.getLogger(__name__)

        self.devices: Dict[str, BluetoothDevice] = {}
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), 'bluetooth_cache.json')
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.connection_timeout = 10  # segundos
        self.reconnect_attempts = 3
        self.monitor_interval = 30  # segundos
        self.status_callbacks: List[Callable] = []

        # Suporte para múltiplos dispositivos
        self.active_printers: Dict[str, BluetoothDevice] = {}  # Porta -> Dispositivo ativo
        self.device_priorities: Dict[str, int] = {}  # Porta -> Prioridade (0=primária, 1=secundária, etc.)

        # Carrega cache de dispositivos
        self._load_device_cache()

    def add_status_callback(self, callback: Callable):
        """Adiciona callback para notificações de status."""
        self.status_callbacks.append(callback)

    def _notify_status_change(self, device: BluetoothDevice, status: str, message: str):
        """Notifica callbacks sobre mudanças de status."""
        for callback in self.status_callbacks:
            try:
                callback(device, status, message)
            except Exception as e:
                self.logger.error(f"Erro no callback de status: {e}")

    def scan_bluetooth_devices(self) -> List[BluetoothDevice]:
        """
        Escaneia dispositivos Bluetooth pareados no sistema Windows.

        Returns:
            Lista de dispositivos Bluetooth encontrados
        """
        devices = []

        try:
            # Lista todas as portas COM disponíveis
            ports = serial.tools.list_ports.comports()

            for port in ports:
                # Verifica se é uma porta Bluetooth (SPP - Serial Port Profile)
                if self._is_bluetooth_port(port):
                    device = BluetoothDevice(
                        name=port.description or f"Bluetooth Device ({port.device})",
                        address=self._extract_bluetooth_address(port),
                        port=port.device,
                        last_seen=datetime.now()
                    )
                    devices.append(device)

                    # Atualiza cache
                    if device.port not in self.devices:
                        self.devices[device.port] = device
                    else:
                        self.devices[device.port].last_seen = datetime.now()

        except Exception as e:
            self.logger.error(f"Erro ao escanear dispositivos Bluetooth: {e}")

        # Salva cache atualizado
        self._save_device_cache()

        return devices

    def _is_bluetooth_port(self, port) -> bool:
        """
        Verifica se uma porta COM é Bluetooth.

        Args:
            port: Objeto da porta COM

        Returns:
            True se for porta Bluetooth
        """
        # Verifica descrição da porta
        description = port.description.lower()
        return any(keyword in description for keyword in [
            'bluetooth', 'bt', 'wireless', 'serial port profile'
        ])

    def _extract_bluetooth_address(self, port) -> str:
        """
        Extrai endereço Bluetooth da descrição da porta.

        Args:
            port: Objeto da porta COM

        Returns:
            Endereço Bluetooth ou string vazia
        """
        # Tenta extrair endereço MAC da descrição
        description = port.description
        import re

        # Padrões comuns de endereço Bluetooth
        patterns = [
            r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})',  # AA:BB:CC:DD:EE:FF
            r'([0-9A-Fa-f]{12})'  # AABBCCDDEEFF
        ]

        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                address = match.group(0)
                # Normaliza para formato AA:BB:CC:DD:EE:FF
                if len(address) == 12:  # Formato sem separadores
                    address = ':'.join(address[i:i+2] for i in range(0, 12, 2))
                return address.upper()

        return ""

    def test_connectivity(self, port: str, timeout: int = None) -> Tuple[bool, str]:
        """
        Testa conectividade com dispositivo Bluetooth.

        Args:
            port: Porta COM do dispositivo
            timeout: Timeout em segundos (usa padrão se None)

        Returns:
            Tupla (sucesso, mensagem)
        """
        if timeout is None:
            timeout = self.connection_timeout

        try:
            self.logger.info(f"Testando conectividade Bluetooth na porta {port}")

            # Tenta abrir conexão serial
            with serial.Serial(port, baudrate=9600, timeout=timeout) as ser:
                # Pequeno delay para estabilizar
                time.sleep(0.5)

                # Testa se porta responde (envia comando de status ESC/POS)
                ser.write(b'\x1b@\x1dv\x00')  # ESC @ (reset) + GS v 0 (status)
                time.sleep(0.2)

                # Verifica se há dados de resposta
                if ser.in_waiting > 0:
                    response = ser.read(ser.in_waiting)
                    self.logger.info(f"Resposta recebida da porta {port}: {len(response)} bytes")
                    return True, f"Conectividade OK - Resposta: {len(response)} bytes"
                else:
                    # Mesmo sem resposta, se conseguiu abrir a porta está OK
                    return True, "Porta acessível (sem resposta específica)"

        except serial.SerialException as e:
            error_msg = f"Erro de serial: {e}"
            self.logger.warning(f"Conectividade falhou na porta {port}: {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Erro inesperado: {e}"
            self.logger.error(f"Erro ao testar conectividade na porta {port}: {error_msg}")
            return False, error_msg

    def connect_device(self, device: BluetoothDevice, baudrate: int = 9600) -> Tuple[bool, str]:
        """
        Conecta a um dispositivo Bluetooth específico.

        Args:
            device: Dispositivo Bluetooth
            baudrate: Baudrate para conexão

        Returns:
            Tupla (sucesso, mensagem)
        """
        try:
            self.logger.info(f"Conectando ao dispositivo Bluetooth: {device.name} ({device.port})")

            # Testa conectividade primeiro
            success, message = self.test_connectivity(device.port)
            if not success:
                device.last_error = message
                device.connection_attempts += 1
                return False, message

            # Tenta estabelecer conexão completa
            ser = serial.Serial(
                device.port,
                baudrate=baudrate,
                timeout=self.connection_timeout,
                write_timeout=self.connection_timeout
            )

            # Armazena referência da conexão (em produção, seria gerenciado pelo PrinterHandler)
            device.is_connected = True
            device.connection_attempts = 0
            device.last_error = ""

            self.logger.info(f"Dispositivo Bluetooth conectado: {device.name}")
            self._notify_status_change(device, "connected", f"Conectado com sucesso")

            # Fecha conexão de teste (PrinterHandler gerenciará a real)
            ser.close()

            return True, f"Conectado ao dispositivo {device.name}"

        except Exception as e:
            error_msg = f"Erro ao conectar: {e}"
            device.last_error = error_msg
            device.connection_attempts += 1
            device.is_connected = False

            self.logger.error(f"Falha na conexão Bluetooth: {error_msg}")
            self._notify_status_change(device, "connection_failed", error_msg)

            return False, error_msg

    def start_monitoring(self):
        """Inicia monitoramento contínuo de dispositivos Bluetooth."""
        if self.monitoring_active:
            return

        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()

        self.logger.info("Monitoramento Bluetooth iniciado")

    def stop_monitoring(self):
        """Para monitoramento de dispositivos Bluetooth."""
        self.monitoring_active = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)

        self.logger.info("Monitoramento Bluetooth parado")

    def _monitoring_loop(self):
        """Loop principal de monitoramento."""
        connectivity_test_count = 0

        while self.monitoring_active:
            try:
                # Só faz scan se houver dispositivos registrados
                registered_devices = self.get_registered_printers()
                if registered_devices and connectivity_test_count % 3 == 0:
                    # Escaneia dispositivos apenas se houver registrados
                    devices = self.scan_bluetooth_devices()

                # Testa conectividade apenas dos dispositivos registrados
                for device in registered_devices:
                    self._perform_periodic_connectivity_test(device)

                # Remove dispositivos não registrados do cache para evitar testes futuros
                self._cleanup_unregistered_devices()

                # Remove dispositivos não vistos há muito tempo
                self._cleanup_old_devices()

                # Incrementa contador
                connectivity_test_count += 1

            except Exception as e:
                self.logger.error(f"Erro no loop de monitoramento: {e}")

            # Aguarda próximo ciclo
            time.sleep(self.monitor_interval)

    def _perform_periodic_connectivity_test(self, device: BluetoothDevice):
        """
        Executa teste de conectividade periódico para um dispositivo.

        Args:
            device: Dispositivo a testar
        """
        try:
            # Só testa conectividade se for um dispositivo registrado/ativo
            if device.port not in self.active_printers:
                return

            # Testa conectividade com timeout reduzido para monitoramento
            success, message = self.test_connectivity(device.port, timeout=3)

            # Verifica se é erro de permissão (porta em uso)
            is_permission_error = "acesso negado" in message.lower() or "permission denied" in message.lower()

            # Atualiza status baseado no resultado
            if success:
                if not device.is_connected:
                    device.is_connected = True
                    device.connection_attempts = 0
                    device.last_error = ""
                    self._notify_status_change(device, "connected", "Conectado via monitoramento")
                    self.logger.info(f"Dispositivo conectado via monitoramento: {device.name}")
                # Se já estava conectado, apenas atualiza last_seen
                device.last_seen = datetime.now()
            else:
                # Se estava conectado e falhou, marca como desconectado
                if device.is_connected:
                    device.is_connected = False
                    device.last_error = message
                    self._notify_status_change(device, "disconnected", f"Perda de conexão: {message}")
                    self.logger.warning(f"Dispositivo desconectado: {device.name} - {message}")

                # Para impressoras registradas, só tenta reconexão se NÃO for erro de permissão
                if device.port in self.active_printers and not is_permission_error:
                    # Verifica se não excedeu limite de tentativas consecutivas
                    if device.connection_attempts < 3:  # Máximo 3 tentativas consecutivas
                        self._notify_status_change(device, "reconnecting", "Tentando reconexão automática")
                    else:
                        self.logger.warning(f"Máximo de tentativas consecutivas atingido para {device.port}")
                elif is_permission_error:
                    # Para erros de permissão, loga mas não tenta reconectar
                    self.logger.warning(f"Porta {device.port} em uso por outro programa. Parando tentativas de reconexão.")

        except Exception as e:
            self.logger.error(f"Erro no teste de conectividade para {device.name}: {e}")
            device.last_error = str(e)
            if device.is_connected:
                device.is_connected = False
                self._notify_status_change(device, "error", f"Erro no teste: {e}")

    def _cleanup_unregistered_devices(self):
        """Remove dispositivos não registrados do cache para evitar testes futuros."""
        devices_to_remove = []

        for port, device in self.devices.items():
            if port not in self.active_printers:
                devices_to_remove.append(port)

        for port in devices_to_remove:
            del self.devices[port]
            self.logger.debug(f"Dispositivo não registrado removido do cache: {port}")

        if devices_to_remove:
            self._save_device_cache()

    def _cleanup_old_devices(self):
        """Remove dispositivos não vistos há mais de 24 horas."""
        cutoff_time = datetime.now() - timedelta(hours=24)
        devices_to_remove = []

        for port, device in self.devices.items():
            if device.last_seen < cutoff_time:
                devices_to_remove.append(port)

        for port in devices_to_remove:
            del self.devices[port]
            self.logger.info(f"Dispositivo removido do cache: {port}")

        if devices_to_remove:
            self._save_device_cache()

    def get_available_devices(self) -> List[BluetoothDevice]:
        """
        Retorna lista de dispositivos Bluetooth disponíveis.

        Returns:
            Lista de dispositivos
        """
        return list(self.devices.values())

    def get_connected_devices(self) -> List[BluetoothDevice]:
        """
        Retorna lista de dispositivos conectados.

        Returns:
            Lista de dispositivos conectados
        """
        return [d for d in self.devices.values() if d.is_connected]

    def _load_device_cache(self):
        """Carrega cache de dispositivos do arquivo."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for port, device_data in data.get('devices', {}).items():
                    device = BluetoothDevice(
                        name=device_data.get('name', f'Bluetooth Device ({port})'),
                        address=device_data.get('address', ''),
                        port=port,
                        is_connected=device_data.get('is_connected', False),
                        last_seen=datetime.fromisoformat(device_data.get('last_seen', datetime.now().isoformat())),
                        connection_attempts=device_data.get('connection_attempts', 0),
                        last_error=device_data.get('last_error', '')
                    )
                    self.devices[port] = device

                # Carrega configurações
                config = data.get('config', {})
                self.connection_timeout = config.get('connection_timeout', 10)
                self.reconnect_attempts = config.get('reconnect_attempts', 3)
                self.monitor_interval = config.get('monitor_interval', 30)

                self.logger.info(f"Cache Bluetooth carregado: {len(self.devices)} dispositivos")

        except Exception as e:
            self.logger.warning(f"Erro ao carregar cache Bluetooth: {e}")

    def _save_device_cache(self):
        """Salva cache de dispositivos no arquivo."""
        try:
            data = {
                'devices': {},
                'config': {
                    'connection_timeout': self.connection_timeout,
                    'reconnect_attempts': self.reconnect_attempts,
                    'monitor_interval': self.monitor_interval
                }
            }

            for port, device in self.devices.items():
                data['devices'][port] = {
                    'name': device.name,
                    'address': device.address,
                    'is_connected': device.is_connected,
                    'last_seen': device.last_seen.isoformat(),
                    'connection_attempts': device.connection_attempts,
                    'last_error': device.last_error
                }

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            self.logger.error(f"Erro ao salvar cache Bluetooth: {e}")

    def configure(self, connection_timeout: int = None, reconnect_attempts: int = None,
                  monitor_interval: int = None):
        """
        Configura parâmetros do gerenciador Bluetooth.

        Args:
            connection_timeout: Timeout de conexão em segundos
            reconnect_attempts: Número máximo de tentativas de reconexão
            monitor_interval: Intervalo de monitoramento em segundos
        """
        if connection_timeout is not None:
            self.connection_timeout = connection_timeout
        if reconnect_attempts is not None:
            self.reconnect_attempts = reconnect_attempts
        if monitor_interval is not None:
            self.monitor_interval = monitor_interval

        self._save_device_cache()
        self.logger.info("Configuração Bluetooth atualizada")

    def register_printer(self, port: str, name: str = None, priority: int = 0) -> bool:
        """
        Registra uma impressora Bluetooth para uso múltiplo.

        Args:
            port: Porta COM do dispositivo
            name: Nome personalizado da impressora
            priority: Prioridade (0=primária, 1=secundária, etc.)

        Returns:
            True se registrada com sucesso
        """
        if port not in self.devices:
            self.logger.warning(f"Dispositivo na porta {port} não encontrado no cache")
            return False

        device = self.devices[port]
        if name:
            device.name = name

        self.active_printers[port] = device
        self.device_priorities[port] = priority

        self.logger.info(f"Impressora registrada: {device.name} (porta {port}, prioridade {priority})")
        self._save_device_cache()

        return True

    def unregister_printer(self, port: str) -> bool:
        """
        Remove uma impressora do registro de múltiplos dispositivos.

        Args:
            port: Porta COM da impressora

        Returns:
            True se removida com sucesso
        """
        if port in self.active_printers:
            device = self.active_printers[port]
            del self.active_printers[port]
            if port in self.device_priorities:
                del self.device_priorities[port]

            self.logger.info(f"Impressora removida: {device.name} (porta {port})")
            self._save_device_cache()
            return True

        return False

    def get_registered_printers(self) -> List[BluetoothDevice]:
        """
        Retorna lista de impressoras registradas, ordenadas por prioridade.

        Returns:
            Lista de dispositivos registrados ordenados por prioridade
        """
        registered = list(self.active_printers.values())

        # Ordena por prioridade (menor número = maior prioridade)
        registered.sort(key=lambda d: self.device_priorities.get(d.port, 999))

        return registered

    def get_primary_printer(self) -> Optional[BluetoothDevice]:
        """
        Retorna a impressora primária (prioridade 0).

        Returns:
            Dispositivo primário ou None se não houver
        """
        primary_printers = [d for d in self.active_printers.values()
                          if self.device_priorities.get(d.port, 999) == 0]

        return primary_printers[0] if primary_printers else None

    def get_backup_printers(self) -> List[BluetoothDevice]:
        """
        Retorna lista de impressoras de backup (prioridade > 0).

        Returns:
            Lista de dispositivos de backup ordenados por prioridade
        """
        backup = [d for d in self.active_printers.values()
                 if self.device_priorities.get(d.port, 999) > 0]

        # Ordena por prioridade
        backup.sort(key=lambda d: self.device_priorities.get(d.port, 999))

        return backup

    def failover_to_backup(self, failed_port: str) -> Optional[BluetoothDevice]:
        """
        Executa failover para impressora de backup quando a primária falha.

        Args:
            failed_port: Porta da impressora que falhou

        Returns:
            Dispositivo de backup disponível ou None
        """
        self.logger.info(f"Iniciando failover da porta {failed_port}")

        # Marca dispositivo como falho
        if failed_port in self.devices:
            self.devices[failed_port].is_connected = False
            self.devices[failed_port].last_error = "Failover acionado"

        # Busca primeira impressora de backup disponível
        backup_printers = self.get_backup_printers()

        for backup in backup_printers:
            success, message = self.test_connectivity(backup.port, timeout=3)
            if success:
                self.logger.info(f"Failover bem-sucedido para {backup.name} (porta {backup.port})")
                return backup
            else:
                self.logger.warning(f"Backup {backup.name} indisponível: {message}")

        self.logger.error("Nenhuma impressora de backup disponível")
        return None

    def load_printer_configuration(self, config: dict):
        """
        Carrega configuração de múltiplas impressoras.

        Args:
            config: Dicionário com configuração das impressoras
        """
        printers_config = config.get('bluetooth_printers', [])

        for printer_config in printers_config:
            port = printer_config.get('port')
            name = printer_config.get('name')
            priority = printer_config.get('priority', 0)

            if port:
                self.register_printer(port, name, priority)

        self.logger.info(f"Configuração de múltiplas impressoras carregada: {len(printers_config)} impressoras")

    def save_printer_configuration(self) -> dict:
        """
        Salva configuração atual de múltiplas impressoras.

        Returns:
            Dicionário com configuração das impressoras
        """
        printers_config = []

        for port, device in self.active_printers.items():
            printers_config.append({
                'port': port,
                'name': device.name,
                'priority': self.device_priorities.get(port, 0)
            })

        return {'bluetooth_printers': printers_config}

    def get_printer_status_summary(self) -> dict:
        """
        Retorna resumo do status de todas as impressoras registradas.

        Returns:
            Dicionário com resumo do status
        """
        registered = self.get_registered_printers()
        connected = [d for d in registered if d.is_connected]
        available = [d for d in registered if not d.is_connected and not d.last_error]
        failed = [d for d in registered if d.last_error]

        return {
            'total_registered': len(registered),
            'connected': len(connected),
            'available': len(available),
            'failed': len(failed),
            'primary_available': self.get_primary_printer() is not None,
            'backup_available': len(self.get_backup_printers()) > 0
        }
