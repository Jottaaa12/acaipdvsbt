from datetime import datetime
from escpos.printer import Usb, Serial, Network, Dummy
from escpos.exceptions import DeviceNotFoundError
import serial.tools.list_ports
import win32print
import win32api
import logging
import threading
import time
import tempfile
import os
from .bluetooth_manager import BluetoothManager, BluetoothDevice

class PrinterHandler:
    """
    Gerencia a comunicação com impressoras de múltiplos tipos (USB, Serial, Network, Sistema).
    Funciona como uma fábrica que instancia o tipo correto de conexão baseado na configuração.
    """

    def __init__(self, printer_config):
        """
        Inicializa o handler com a configuração da impressora.

        Args:
            printer_config (dict): Dicionário com as configurações da impressora
        """
        self.printer_config = printer_config
        self.printer = None
        self.error_message = None
        self.printer_type = printer_config.get('type', 'disabled')

        # Gerenciador Bluetooth para dispositivos avançados
        self.bluetooth_manager = None
        self.bluetooth_monitoring = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = printer_config.get('bluetooth_max_reconnect_attempts', 3)
        self.connection_timeout = printer_config.get('bluetooth_connection_timeout', 10)
        self.reconnect_thread = None
        self.reconnect_active = False

        # Inicializa BluetoothManager se for impressora Bluetooth
        if self.printer_type == 'thermal_bluetooth':
            self._init_bluetooth_manager()

        # Tenta conectar se não estiver desabilitada
        if self.printer_type != 'disabled':
            self.connect()

    def connect(self):
        """
        Conecta à impressora baseada no tipo especificado na configuração.
        Retorna (status, mensagem).
        """
        try:
            if self.printer_type == 'thermal_usb':
                return self._connect_usb()
            elif self.printer_type in ['thermal_bluetooth', 'thermal_serial']:
                return self._connect_serial()
            elif self.printer_type == 'thermal_network':
                return self._connect_network()
            elif self.printer_type == 'system_printer':
                return self._connect_system_printer()
            else:
                self.error_message = "Tipo de impressora não reconhecido"
                return False, self.error_message

        except DeviceNotFoundError as e:
            self.error_message = f"Dispositivo não encontrado: {e}"
            self.printer = None
            return False, self.error_message
        except Exception as e:
            self.error_message = f"Erro ao conectar: {e}"
            self.printer = None
            return False, self.error_message

    def _connect_usb(self):
        """Conecta a uma impressora USB."""
        vendor_id = self.printer_config.get('usb_vendor_id')
        product_id = self.printer_config.get('usb_product_id')

        if not vendor_id or not product_id:
            self.error_message = "Vendor ID e Product ID são obrigatórios para impressora USB"
            return False, self.error_message

        try:
            # Converte de hex string para int
            vendor_id_int = int(vendor_id, 16)
            product_id_int = int(product_id, 16)

            logging.info(f"Impressora USB: Conectando ao dispositivo {vendor_id}/{product_id}")
            self.printer = Usb(vendor_id_int, product_id_int)
            logging.info("Impressora USB: Conectada com sucesso")
            return True, "Impressora USB conectada"

        except ValueError as e:
            import logging
            logging.warning(f"Erro ao converter Vendor ID/Product ID de USB: {e}")
            self.error_message = f"Configuração da impressora USB inválida. Vendor ID e Product ID devem estar no formato hexadecimal válido (ex: 0x04b8, 0x0202)"
            return False, self.error_message
            self.error_message = "Vendor ID e Product ID devem estar no formato hexadecimal (ex: 0x04b8)"
            return False, self.error_message

    def _connect_serial(self):
        """Conecta a uma impressora serial (Bluetooth ou Serial)."""
        if self.printer_type == 'thermal_bluetooth':
            port = self.printer_config.get('bluetooth_port')
            timeout = self.connection_timeout
        else:
            port = self.printer_config.get('serial_port')
            timeout = 5  # Timeout padrão para serial

        baudrate = self.printer_config.get('serial_baudrate', 9600)

        if not port:
            self.error_message = "Porta COM é obrigatória para impressora serial"
            return False, self.error_message

        try:
            logging.info(f"Impressora Serial: Conectando à porta {port} ({baudrate} baud, timeout={timeout}s)")

            # Configura conexão serial com timeout configurável
            self.printer = Serial(
                port,
                baudrate=baudrate,
                timeout=timeout,
                write_timeout=timeout
            )

            # Para Bluetooth, remove validação que pode causar problemas
            if self.printer_type == 'thermal_bluetooth':
                logging.info("Impressora Bluetooth: Conexão estabelecida (sem validação adicional)")

            logging.info("Impressora Serial: Conectada com sucesso")
            return True, f"Impressora Serial conectada na porta {port}"

        except serial.SerialException as e:
            error_msg = self._format_bluetooth_error(e, port)

            # Se é erro de permissão, marca timestamp para evitar tentativas frequentes
            if "acesso negado" in error_msg.lower() or "permission denied" in error_msg.lower():
                self.last_permission_error_time = datetime.now()
                logging.warning(f"Impressora Serial: Erro de permissão na porta {port}. Evitando tentativas frequentes.")

            logging.error(f"Impressora Serial: Erro de porta serial {port}: {error_msg}")
            self.error_message = error_msg
            self.printer = None
            return False, error_msg
        except OSError as e:
            error_msg = f"Erro de sistema ao acessar porta {port}: {e}"
            logging.error(f"Impressora Serial: {error_msg}")
            self.error_message = error_msg
            self.printer = None
            return False, error_msg
        except Exception as e:
            error_msg = f"Erro inesperado ao conectar à porta {port}: {e}"
            logging.error(f"Impressora Serial: {error_msg}", exc_info=True)
            self.error_message = error_msg
            self.printer = None
            return False, error_msg

    def _connect_network(self):
        """Conecta a uma impressora de rede."""
        host = self.printer_config.get('network_ip')
        port = self.printer_config.get('network_port', 9100)

        if not host:
            self.error_message = "Endereço IP é obrigatório para impressora de rede"
            return False, self.error_message

        try:
            logging.info(f"Impressora de Rede: Conectando a {host}:{port}")
            self.printer = Network(host, port=port)
            logging.info("Impressora de Rede: Conectada com sucesso")
            return True, f"Impressora de rede conectada em {host}:{port}"

        except Exception as e:
            self.error_message = f"Erro ao conectar à impressora de rede {host}:{port}: {e}"
            return False, self.error_message

    def _connect_system_printer(self):
        """Usa a impressora padrão do sistema Windows."""
        try:
            # Obtém a impressora padrão
            printer_name = win32print.GetDefaultPrinter()
            logging.info(f"Impressora do Sistema: Usando impressora padrão '{printer_name}'")
            return True, f"Impressora do sistema configurada: {printer_name}"

        except Exception as e:
            self.error_message = f"Erro ao configurar impressora do sistema: {e}"
            return False, self.error_message

    def reconfigure(self, printer_config):
        """
        Reconfigura o handler com uma nova configuração de impressora.

        Args:
            printer_config (dict): Nova configuração da impressora
        """
        logging.info(f"Impressora: Reconfigurando para tipo '{printer_config.get('type', 'disabled')}'")

        # Fecha conexão anterior
        if self.printer and hasattr(self.printer, 'close'):
            try:
                self.printer.close()
            except Exception as e:
                logging.error(f"Impressora: Erro ao fechar conexão anterior: {e}")

        self.printer_config = printer_config
        self.printer = None
        self.error_message = None
        self.printer_type = printer_config.get('type', 'disabled')

        # Reinicializa BluetoothManager se necessário
        if self.printer_type == 'thermal_bluetooth':
            if not self.bluetooth_manager:
                self._init_bluetooth_manager()
        else:
            # Para outros tipos, para monitoramento Bluetooth se ativo
            if self.bluetooth_monitoring:
                self.stop_bluetooth_monitoring()
            self.bluetooth_manager = None

        # Reconecta se não estiver desabilitada
        if self.printer_type != 'disabled':
            self.connect()

    def print_receipt(self, store_info, sale_details):
        """
        Imprime o recibo baseado no tipo de impressora configurada.
        Retorna uma tupla (status, mensagem).
        """
        # Se desabilitada, retorna sucesso sem imprimir
        if self.printer_type == 'disabled':
            self._format_and_print_simulated(store_info, sale_details)
            return True, "Impressão desabilitada - recibo simulado"

        # Validação específica para Bluetooth antes da impressão (apenas loga, não falha)
        if self.printer_type == 'thermal_bluetooth':
            success, message = self.validate_bluetooth_connectivity()
            if not success:
                logging.warning(f"Impressora Bluetooth: Validação falhou, mas tentando imprimir mesmo assim: {message}")
            else:
                logging.info("Impressora Bluetooth: Validação OK")

        # Sempre tenta conectar/imprimir, independente de erros anteriores
        # Remove o bloqueio baseado em error_message para Bluetooth
        if self.printer_type != 'thermal_bluetooth' and self.error_message:
            logging.warning(f"Impressora: Pulando impressão devido a erro de conexão: {self.error_message}")
            return False, f"Erro de conexão: {self.error_message}"

        # Se não há conexão, tenta conectar
        if not self.printer:
            logging.info("Impressora: Tentando conectar para impressão...")
            success, message = self.connect()
            if not success:
                logging.error(f"Impressora: Falha na conexão para impressão: {message}")
                return False, message

        try:
            if self.printer_type == 'system_printer':
                return self._print_system_printer(store_info, sale_details)
            else:
                return self._print_thermal_printer(store_info, sale_details)

        except Exception as e:
            error_message = f"Erro ao imprimir: {e}"
            logging.error(f"Impressora: {error_message}", exc_info=True)
            # Define erro de conexão para evitar tentativas futuras (exceto Bluetooth)
            if self.printer_type != 'thermal_bluetooth':
                self.error_message = f"Erro durante impressão: {e}"
            self.printer = None

            # Para Bluetooth, tenta reconexão automática
            if self.printer_type == 'thermal_bluetooth' and self.printer_config.get('bluetooth_auto_reconnect', True):
                port = self.printer_config.get('bluetooth_port')
                if port:
                    self._start_auto_reconnect(BluetoothDevice(name="Printer", address="", port=port))

            return False, error_message

    def _print_thermal_printer(self, store_info, sale_details):
        """Imprime em impressora térmica (USB, Serial, Network)."""
        
        # WORKAROUND FINAL para impressoras bluetooth problemáticas
        if self.printer_type == 'thermal_bluetooth':
            logging.info("WORKAROUND: Redirecionando impressão para método de arquivo temporário.")
            receipt_text = self._format_receipt_text(store_info, sale_details)
            return self._print_via_temp_file(receipt_text, "Recibo de Venda")

        # Lógica original para outras impressoras
        p = self.printer
        try:
            p.set(align='center', bold=True)
            if store_info.get('name'): p.text(f"{store_info['name']}\n")
            if store_info.get('address'): p.text(f"{store_info['address']}\n")
            if store_info.get('phone'): p.text(f"{store_info['phone']}\n")
            p.text("---" * 14 + "\n")
            p.set(align='center')
            p.text("RECIBO - SEM VALOR FISCAL\n")
            p.text(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            p.text("---" * 14 + "\n")
            p.set(align='left', bold=True)
            p.text(f"{'DESC':<20}{'QTD':>7}{'VL.UN':>7}{'VL.TOT':>8}\n")
            for item in sale_details['items']:
                desc = item['description'][:19]
                if item['sale_type'] == 'weight':
                    qtd_str = f"{item['quantity']:.3f}"
                    unit_price_str = f"{item['unit_price']:.2f}"
                else:
                    qtd_str = f"{int(item['quantity'])}"
                    unit_price_str = f"{item['unit_price']:.2f}"
                total_price_str = f"{item['total_price']:.2f}"
                p.text(f"{desc:<20}{qtd_str:>7}{unit_price_str:>7}{total_price_str:>8}\n")
            p.text("---" * 14 + "\n")
            p.set(align='right')
            total_str = f"R$ {sale_details['total_amount']:.2f}"
            p.text(f"TOTAL: {total_str}\n")
            p.set(bold=True)
            p.text(f"Forma de Pagamento: {sale_details['payment_method']}\n")
            p.text("---" * 14 + "\n")
            p.set(align='center')
            p.text("OBRIGADO PELA PREFERÊNCIA!\n\n")
            p.cut()
            return True, "Recibo impresso com sucesso"
        except Exception as e:
            error_message = f"Erro na impressão térmica: {e}"
            logging.error(error_message, exc_info=True)
            return False, error_message

    def _print_via_temp_file(self, receipt_text: str, document_title: str) -> tuple:
        """
        Imprime um texto salvando-o em um arquivo temporário e usando ShellExecute.
        Este é um workaround robusto para drivers problemáticos.
        """
        path = None  # Inicializa o path para o bloco finally
        try:
            # Usar delete=False para garantir que o arquivo exista para o ShellExecute
            with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False, encoding='utf-8') as tmp:
                path = tmp.name
                tmp.write(receipt_text)
            
            logging.info(f"WORKAROUND: Recibo salvo em arquivo temporário: {path}")

            # Imprimir o arquivo usando a ação 'print' do shell do Windows
            win32api.ShellExecute(0, "print", path, None, ".", 0)
            
            logging.info(f"WORKAROUND: Comando de impressão enviado para o arquivo: {path}")
            
            # Dar um tempo para o spooler de impressão pegar o arquivo
            time.sleep(2)

            return True, "Comando de impressão enviado ao sistema via arquivo temporário."

        except Exception as e:
            logging.error(f"WORKAROUND: Erro ao imprimir via arquivo temporário: {e}", exc_info=True)
            return False, f"Erro no workaround de impressão: {e}"
        finally:
            # Garante que o arquivo temporário seja removido
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    logging.info(f"WORKAROUND: Arquivo temporário removido: {path}")
                except Exception as e:
                    logging.error(f"WORKAROUND: Falha ao remover arquivo temporário {path}: {e}")

    def _send_raw_bytes_to_system_printer(self, raw_bytes: bytes, document_title: str) -> tuple:
        """
        Envia bytes brutos (ex: ESC/POS) para a impressora padrão do sistema Windows.

        Args:
            raw_bytes (bytes): Os bytes brutos a serem impressos.
            document_title (str): O título do documento na fila de impressão.

        Returns:
            Tupla (status, mensagem).
        """
        try:
            printer_name = win32print.GetDefaultPrinter()
            h_printer = win32print.OpenPrinter(printer_name)
            try:
                # O driver da KP1025 espera "RAW"
                h_job = win32print.StartDocPrinter(h_printer, 1, (document_title, None, "RAW"))
                try:
                    win32print.StartPagePrinter(h_printer)
                    win32print.WritePrinter(h_printer, raw_bytes)
                    win32print.EndPagePrinter(h_printer)
                finally:
                    win32print.EndDocPrinter(h_printer)
            finally:
                win32print.ClosePrinter(h_printer)

            return True, f"'{document_title}' enviado para a impressora do sistema: {printer_name}"

        except Exception as e:
            logging.error(f"Erro ao enviar para a impressora do sistema (RAW): {e}", exc_info=True)
            return False, f"Erro ao imprimir no sistema (RAW): {e}"

    def _print_system_printer(self, store_info, sale_details):
        """Gera comandos ESC/POS e os envia para a impressora do sistema como dados RAW."""
        try:
            # Usa uma impressora 'Dummy' para capturar os bytes ESC/POS
            dummy_printer = Dummy()

            # Lógica de impressão (copiada de _print_thermal_printer)
            dummy_printer.set(align='center', bold=True)
            if store_info.get('name'): dummy_printer.text(f"{store_info['name']}\n")
            if store_info.get('address'): dummy_printer.text(f"{store_info['address']}\n")
            if store_info.get('phone'): dummy_printer.text(f"{store_info['phone']}\n")
            dummy_printer.text("---" * 14 + "\n")
            dummy_printer.set(align='center')
            dummy_printer.text("RECIBO - SEM VALOR FISCAL\n")
            dummy_printer.set(align='center')
            dummy_printer.text(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            dummy_printer.text("---" * 14 + "\n")

            dummy_printer.set(align='left', bold=True)
            dummy_printer.text(f"{'DESC':<20}{'QTD':>7}{'VL.UN':>7}{'VL.TOT':>8}\n")
            for item in sale_details['items']:
                desc = item['description'][:19]
                if item['sale_type'] == 'weight':
                    qtd_str = f"{item['quantity']:.3f}"
                    unit_price_str = f"{item['unit_price']:.2f}"
                else:
                    qtd_str = f"{int(item['quantity'])}"
                    unit_price_str = f"{item['unit_price']:.2f}"
                total_price_str = f"{item['total_price']:.2f}"
                dummy_printer.text(f"{desc:<20}{qtd_str:>7}{unit_price_str:>7}{total_price_str:>8}\n")

            dummy_printer.text("---" * 14 + "\n")
            dummy_printer.set(align='right')
            total_str = f"R$ {sale_details['total_amount']:.2f}"
            dummy_printer.text(f"TOTAL: {total_str}\n")
            dummy_printer.set(bold=True)
            dummy_printer.text(f"Forma de Pagamento: {sale_details['payment_method']}\n")
            dummy_printer.text("---" * 14 + "\n")

            dummy_printer.set(align='center')
            dummy_printer.text("OBRIGADO PELA PREFERÊNCIA!\n\n")

            # Obtém os bytes brutos
            raw_bytes = dummy_printer.output

            # Envia os bytes para a impressora do sistema
            return self._send_raw_bytes_to_system_printer(raw_bytes, "Recibo de Venda")

        except Exception as e:
            logging.error(f"Erro ao gerar ESC/POS para impressão via sistema: {e}", exc_info=True)
            return False, f"Erro ao gerar recibo para impressão: {e}"

    def _format_receipt_text(self, store_info, sale_details):
        """Formata o recibo como texto para impressora do sistema."""
        lines = []

        # Cabeçalho
        if store_info.get('name'):
            lines.append(store_info['name'].center(40))
        if store_info.get('address'):
            lines.append(store_info['address'].center(40))
        if store_info.get('phone'):
            lines.append(store_info['phone'].center(40))

        lines.append("=" * 40)
        lines.append("RECIBO - SEM VALOR FISCAL".center(40))
        lines.append(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}".center(40))
        lines.append("=" * 40)

        # Itens
        lines.append(f"{'DESC':<18} {'QTD':>6} {'VL. UNIT.':>8} {'VL. TOTAL':>8}")
        lines.append("-" * 40)

        for item in sale_details['items']:
            desc = item['description'][:17]
            if item['sale_type'] == 'weight':
                qtd_str = f"{item['quantity']:.3f}kg"
                unit_price_str = f"R${item['unit_price']:.2f}/kg"
            else:
                qtd_str = f"{int(item['quantity'])} un"
                unit_price_str = f"R${item['unit_price']:.2f}"

            total_price_str = f"R${item['total_price']:.2f}"
            lines.append(f"{desc:<18} {qtd_str:>6} {unit_price_str:>8} {total_price_str:>8}")

        # Total
        lines.append("=" * 40)
        total_str = f"R$ {sale_details['total_amount']:.2f}"
        lines.append(f"{'TOTAL:':<32}{total_str:>8}")
        payment_method_str = f"{sale_details['payment_method']}"
        lines.append(f"{'Forma de Pagamento:':<32}{payment_method_str:>8}")
        lines.append("=" * 40)

        # Rodapé
        lines.append("OBRIGADO PELA PREFERÊNCIA!".center(40))
        lines.append("")

        return "\n".join(lines)

    def _format_and_print_simulated(self, store_info, sale_details):
        """Formata e imprime o recibo no console (modo simulado)."""
        receipt = []
        receipt.append("--- INÍCIO DO RECIBO SIMULADO ---")

        # Cabeçalho
        if store_info.get('name'): receipt.append(f"{store_info['name'].center(40)}")
        if store_info.get('address'): receipt.append(f"{store_info['address'].center(40)}")
        if store_info.get('phone'): receipt.append(f"{store_info['phone'].center(40)}")
        receipt.append("---" * 13 + "\n")
        receipt.append("RECIBO - SEM VALOR FISCAL".center(40))
        receipt.append(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}".center(40))
        receipt.append("---" * 13 + "\n")

        # Itens
        receipt.append(f"{'DESC':<18} {'QTD':>6} {'VL. UNIT.':>8} {'VL. TOTAL':>8}")
        for item in sale_details['items']:
            desc = item['description'][:17]
            if item['sale_type'] == 'weight':
                qtd_str = f"{item['quantity']:.3f}kg"
                unit_price_str = f"R${item['unit_price']:.2f}/kg"
            else:
                qtd_str = f"{int(item['quantity'])} un"
                unit_price_str = f"R${item['unit_price']:.2f}"

            total_price_str = f"R${item['total_price']:.2f}"
            receipt.append(f"{desc:<18} {qtd_str:>6} {unit_price_str:>8} {total_price_str:>8}")

        # Total
        receipt.append("---" * 13 + "\n")
        total_str = f"R$ {sale_details['total_amount']:.2f}"
        receipt.append(f"{'TOTAL:':<31}{total_str:>9}")
        payment_method_str = f"{sale_details['payment_method']}"
        receipt.append(f"{'Forma de Pagamento:':<31}{payment_method_str:>9}")
        receipt.append("---" * 13 + "\n")

        # Rodapé
        receipt.append("OBRIGADO PELA PREFERÊNCIA!".center(40))
        receipt.append("--- FIM DO RECIBO SIMULADO ---")

        logging.info("\n".join(receipt))

    def test_print(self):
        """
        Imprime um recibo de teste para verificar a conexão.
        Retorna (status, mensagem).
        """
        if self.printer_type == 'disabled':
            return True, "Impressão desabilitada - teste simulado"

        if self.error_message:
            return False, f"Erro de conexão: {self.error_message}"

        if not self.printer:
            success, message = self.connect()
            if not success:
                return False, message

        try:
            if self.printer_type == 'system_printer':
                # Teste para impressora do sistema
                test_text = "\n" + "="*48 + "\n" + "TESTE DE IMPRESSÃO".center(48) + "\n" + f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}".center(48) + "\n" + "IMPRESSORA DO SISTEMA".center(48) + "\n" + "="*48 + "\n\n"
                win32api.ShellExecute(0, "print", test_text, None, ".", 0)
                return True, "Teste enviado para impressora do sistema"
            else:
                # Teste para impressoras térmicas
                p = self.printer
                p.set(align='center', bold=True)
                p.text("\n" + "="*16 + "\n")
                p.text("TESTE DE IMPRESSÃO\n")
                p.text(f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
                p.text(f"Tipo: {self.printer_type.upper()}\n")
                p.text("="*16 + "\n")
                p.cut()
                return True, "Teste de impressão enviado"

        except Exception as e:
            return False, f"Erro no teste de impressão: {e}"

    def check_status(self):
        """Verifica o status da impressora. Retorna (status, mensagem)."""
        if self.printer_type == 'disabled':
            return True, "Impressão desabilitada"

        if self.error_message:
            return False, self.error_message

        if not self.printer:
            return False, "Impressora desconectada"

        return True, f"Impressora {self.printer_type.replace('_', ' ').title()} conectada"

    def _init_bluetooth_manager(self):
        """Inicializa o gerenciador Bluetooth para impressoras Bluetooth."""
        try:
            logging.info("Inicializando BluetoothManager...")
            self.bluetooth_manager = BluetoothManager()
            self.bluetooth_manager.configure(
                connection_timeout=self.connection_timeout,
                reconnect_attempts=self.max_reconnect_attempts
            )
            self.bluetooth_manager.add_status_callback(self._bluetooth_status_callback)

            # Registra a impressora Bluetooth configurada para monitoramento
            port = self.printer_config.get('bluetooth_port')
            if port:
                self.bluetooth_manager.register_printer(port, "Impressora Bluetooth Configurada", 0)
                logging.info(f"Impressora Bluetooth registrada na porta {port} para monitoramento")

            # NÃO inicia monitoramento automaticamente para evitar loops em background
            # O monitoramento será iniciado apenas quando necessário
            # if self.printer_config.get('bluetooth_auto_monitoring', False):
            #     self.start_bluetooth_monitoring()

            logging.info("BluetoothManager inicializado com sucesso para impressora Bluetooth")

        except Exception as e:
            logging.error(f"Erro ao inicializar BluetoothManager: {e}", exc_info=True)
            self.bluetooth_manager = None

    def _bluetooth_status_callback(self, device: BluetoothDevice, status: str, message: str):
        """Callback para notificações de status do Bluetooth."""
        logging.info(f"Bluetooth status - {device.name} ({device.port}): {status} - {message}")

        if status == "connection_failed" and self.printer_config.get('bluetooth_auto_reconnect', True):
            # Inicia reconexão automática se falhar
            self._start_auto_reconnect(device)

    def _start_auto_reconnect(self, device: BluetoothDevice):
        """Inicia processo de reconexão automática."""
        if self.reconnect_active:
            return

        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logging.warning(f"Máximo de tentativas de reconexão atingido para {device.port}")
            return

        self.reconnect_active = True
        self.reconnect_thread = threading.Thread(
            target=self._reconnect_loop,
            args=(device,),
            daemon=True
        )
        self.reconnect_thread.start()
        logging.info(f"Iniciando reconexão automática para {device.port}")

    def _reconnect_loop(self, device: BluetoothDevice):
        """Loop de reconexão automática."""
        while self.reconnect_active and self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                self.reconnect_attempts += 1
                logging.info(f"Tentativa de reconexão {self.reconnect_attempts}/{self.max_reconnect_attempts} para {device.port}")

                # Testa conectividade
                success, message = self.bluetooth_manager.test_connectivity(device.port, timeout=5)
                if success:
                    # Tenta reconectar
                    success, message = self.connect()
                    if success:
                        logging.info(f"Reconexão bem-sucedida para {device.port}")
                        self.reconnect_attempts = 0
                        self.reconnect_active = False
                        return

                # Aguarda antes da próxima tentativa
                time.sleep(3)

            except Exception as e:
                logging.error(f"Erro na reconexão automática: {e}")

        self.reconnect_active = False
        logging.warning(f"Falha em todas as tentativas de reconexão para {device.port}")

    def start_bluetooth_monitoring(self):
        """Inicia monitoramento de dispositivos Bluetooth."""
        if self.bluetooth_manager and not self.bluetooth_monitoring:
            self.bluetooth_manager.start_monitoring()
            self.bluetooth_monitoring = True
            logging.info("Monitoramento Bluetooth iniciado")

    def stop_bluetooth_monitoring(self):
        """Para monitoramento de dispositivos Bluetooth."""
        if self.bluetooth_manager and self.bluetooth_monitoring:
            self.bluetooth_manager.stop_monitoring()
            self.bluetooth_monitoring = False
            logging.info("Monitoramento Bluetooth parado")

    def scan_bluetooth_devices(self) -> list:
        """
        Escaneia dispositivos Bluetooth disponíveis.

        Returns:
            Lista de dispositivos Bluetooth encontrados
        """
        if self.bluetooth_manager:
            devices = self.bluetooth_manager.scan_bluetooth_devices()
            return [device.__dict__ for device in devices]  # Converte para dict para compatibilidade
        return []

    def validate_bluetooth_connectivity(self) -> tuple:
        """
        Valida conectividade Bluetooth antes da impressão.

        Returns:
            Tupla (sucesso, mensagem)
        """
        if self.printer_type != 'thermal_bluetooth':
            return True, "Não é impressora Bluetooth"

        # Tenta reinicializar BluetoothManager se não estiver disponível
        if not self.bluetooth_manager:
            logging.warning("BluetoothManager não inicializado, tentando reinicializar...")
            self._init_bluetooth_manager()

            # Se ainda não conseguiu inicializar, falha
            if not self.bluetooth_manager:
                return False, "Gerenciador Bluetooth não inicializado"

        port = self.printer_config.get('bluetooth_port')
        if not port:
            return False, "Porta Bluetooth não configurada"

        # Testa conectividade
        success, message = self.bluetooth_manager.test_connectivity(port)
        if not success:
            # Verifica se é erro de permissão
            is_permission_error = "acesso negado" in message.lower() or "permission denied" in message.lower()

            # Para erros de permissão, ainda tenta reconectar (não bloqueia completamente)
            if self.printer_config.get('bluetooth_auto_reconnect', True):
                self._start_auto_reconnect(
                    BluetoothDevice(name="Configured Printer", address="", port=port)
                )
            elif is_permission_error:
                logging.warning(f"Impressora Bluetooth: Porta {port} em uso. Tentando reconexão automática.")

            return False, f"Conectividade Bluetooth falhou: {message}"

        return True, "Conectividade Bluetooth OK"

    def get_bluetooth_devices_info(self) -> dict:
        """
        Retorna informações sobre dispositivos Bluetooth.

        Returns:
            Dicionário com informações dos dispositivos
        """
        if not self.bluetooth_manager:
            return {"error": "Gerenciador Bluetooth não inicializado"}

        devices = self.bluetooth_manager.get_available_devices()
        connected = self.bluetooth_manager.get_connected_devices()

        return {
            "available_devices": len(devices),
            "connected_devices": len(connected),
            "devices": [device.__dict__ for device in devices],
            "monitoring_active": self.bluetooth_monitoring,
            "reconnect_active": self.reconnect_active,
            "reconnect_attempts": self.reconnect_attempts
        }

    def configure_bluetooth_settings(self, settings: dict):
        """
        Configura parâmetros Bluetooth.

        Args:
            settings: Dicionário com configurações Bluetooth
        """
        if self.bluetooth_manager:
            self.bluetooth_manager.configure(**settings)

        # Atualiza configurações locais
        if 'connection_timeout' in settings:
            self.connection_timeout = settings['connection_timeout']
        if 'reconnect_attempts' in settings:
            self.max_reconnect_attempts = settings['reconnect_attempts']

        logging.info(f"Configurações Bluetooth atualizadas: {settings}")

    def _format_bluetooth_error(self, exception: Exception, port: str) -> str:
        """
        Formata mensagens de erro específicas do Bluetooth.

        Args:
            exception: Exceção ocorrida
            port: Porta onde ocorreu o erro

        Returns:
            Mensagem de erro formatada
        """
        error_str = str(exception).lower()

        # Erros comuns de Bluetooth no Windows
        if "access is denied" in error_str or "acesso negado" in error_str:
            return f"Porta {port} em uso por outro programa ou dispositivo Bluetooth desconectado"

        elif "device is not ready" in error_str or "dispositivo não está pronto" in error_str:
            return f"Dispositivo Bluetooth na porta {port} não está pronto ou foi desconectado"

        elif "the device does not recognize the command" in error_str:
            return f"Comando não reconhecido pelo dispositivo na porta {port} - possível incompatibilidade"

        elif "timeout" in error_str.lower() or "semaphore" in error_str.lower() or "tempo limite" in error_str.lower():
            return f"Impressora Bluetooth na porta {port} não responde - verifique se está ligada e conectada"

        elif "port not found" in error_str or "porta não encontrada" in error_str:
            return f"Porta {port} não encontrada - dispositivo Bluetooth pode ter sido desconectado"

        elif "permission denied" in error_str or "permissão negada" in error_str:
            return f"Permissão negada para acessar porta {port} - verifique permissões do sistema"

        else:
            # Erro genérico
            return f"Erro de conexão Bluetooth na porta {port}: {exception}"

    def print_customer_copy(self, store_info, sale_details):
        """
        Imprime a via do cliente baseado no tipo de impressora configurada.
        Retorna uma tupla (status, mensagem).
        """
        # Se desabilitada, retorna sucesso sem imprimir
        if self.printer_type == 'disabled':
            self._format_and_print_customer_copy_simulated(store_info, sale_details)
            return True, "Impressão desabilitada - via do cliente simulada"

        # Verifica se há erro de conexão persistente
        if self.error_message:
            logging.warning(f"Impressora: Pulando impressão devido a erro de conexão: {self.error_message}")
            return False, f"Erro de conexão: {self.error_message}"

        # Se não há conexão, tenta conectar uma única vez
        if not self.printer:
            logging.info("Impressora: Tentando conectar para impressão...")
            success, message = self.connect()
            if not success:
                logging.error(f"Impressora: Falha na conexão para impressão: {message}")
                return False, message

        try:
            if self.printer_type == 'system_printer':
                return self._print_customer_copy_system_printer(store_info, sale_details)
            else:
                return self._print_customer_copy_thermal_printer(store_info, sale_details)

        except Exception as e:
            error_message = f"Erro ao imprimir via do cliente: {e}"
            logging.error(f"Impressora: {error_message}", exc_info=True)
            # Define erro de conexão para evitar tentativas futuras
            self.error_message = f"Erro durante impressão: {e}"
            self.printer = None

            # Para Bluetooth, tenta reconexão automática
            if self.printer_type == 'thermal_bluetooth' and self.printer_config.get('bluetooth_auto_reconnect', True):
                port = self.printer_config.get('bluetooth_port')
                if port:
                    self._start_auto_reconnect(BluetoothDevice(name="Printer", address="", port=port))

            return False, error_message

    def _print_customer_copy_thermal_printer(self, store_info, sale_details):
        """Imprime via do cliente em impressora térmica (USB, Serial, Network)."""

        # WORKAROUND FINAL para impressoras bluetooth problemáticas
        if self.printer_type == 'thermal_bluetooth':
            logging.info("WORKAROUND (Via Cliente): Redirecionando impressão para método de arquivo temporário.")
            receipt_text = self._format_customer_copy_text(store_info, sale_details)
            return self._print_via_temp_file(receipt_text, "Via do Cliente")

        # Lógica original para outras impressoras
        p = self.printer
        try:
            p.set(align='center', bold=True)
            if store_info.get('name'): p.text(f"{store_info['name']}\n")
            if store_info.get('address'): p.text(f"{store_info['address']}\n")
            if store_info.get('phone'): p.text(f"{store_info['phone']}\n")
            p.text("---" * 14 + "\n")
            p.set(align='center')
            p.text("VIA DO CLIENTE\n")
            p.text(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            p.text("---" * 14 + "\n")
            p.set(align='left', bold=True)
            p.text(f"{'DESC':<20}{'QTD':>7}{'VL.UN':>7}{'VL.TOT':>8}\n")
            for item in sale_details['items']:
                desc = item['description'][:19]
                if item['sale_type'] == 'weight':
                    qtd_str = f"{item['quantity']:.3f}"
                    unit_price_str = f"{item['unit_price']:.2f}"
                else:
                    qtd_str = f"{int(item['quantity'])}"
                    unit_price_str = f"{item['unit_price']:.2f}"
                total_price_str = f"{item['total_price']:.2f}"
                p.text(f"{desc:<20}{qtd_str:>7}{unit_price_str:>7}{total_price_str:>8}\n")
            p.text("---" * 14 + "\n")
            p.set(align='right')
            total_str = f"R$ {sale_details['total_amount']:.2f}"
            p.text(f"TOTAL: {total_str}\n")
            p.set(bold=True)
            p.text(f"Forma de Pagamento: {sale_details['payment_method']}\n")
            p.text("---" * 14 + "\n")
            p.set(align='center')
            p.text("OBRIGADO PELA PREFERÊNCIA!\n\n")
            p.cut()
            return True, "Via do cliente impressa com sucesso"
        except Exception as e:
            error_message = f"Erro na impressão térmica da via do cliente: {e}"
            logging.error(error_message, exc_info=True)
            return False, error_message

    def _print_customer_copy_system_printer(self, store_info, sale_details):
        """Gera comandos ESC/POS para a via do cliente e os envia como dados RAW."""
        try:
            dummy_printer = Dummy()

            # Lógica de impressão (copiada de _print_customer_copy_thermal_printer)
            dummy_printer.set(align='center', bold=True)
            if store_info.get('name'): dummy_printer.text(f"{store_info['name']}\n")
            if store_info.get('address'): dummy_printer.text(f"{store_info['address']}\n")
            if store_info.get('phone'): dummy_printer.text(f"{store_info['phone']}\n")
            dummy_printer.text("---" * 14 + "\n")
            dummy_printer.set(align='center')
            dummy_printer.text("VIA DO CLIENTE\n")
            dummy_printer.set(align='center')
            dummy_printer.text(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            dummy_printer.text("---" * 14 + "\n")

            dummy_printer.set(align='left', bold=True)
            dummy_printer.text(f"{'DESC':<20}{'QTD':>7}{'VL.UN':>7}{'VL.TOT':>8}\n")
            for item in sale_details['items']:
                desc = item['description'][:19]
                if item['sale_type'] == 'weight':
                    qtd_str = f"{item['quantity']:.3f}"
                    unit_price_str = f"{item['unit_price']:.2f}"
                else:
                    qtd_str = f"{int(item['quantity'])}"
                    unit_price_str = f"{item['unit_price']:.2f}"
                total_price_str = f"{item['total_price']:.2f}"
                dummy_printer.text(f"{desc:<20}{qtd_str:>7}{unit_price_str:>7}{total_price_str:>8}\n")

            dummy_printer.text("---" * 14 + "\n")
            dummy_printer.set(align='right')
            total_str = f"R$ {sale_details['total_amount']:.2f}"
            dummy_printer.text(f"TOTAL: {total_str}\n")
            dummy_printer.set(bold=True)
            dummy_printer.text(f"Forma de Pagamento: {sale_details['payment_method']}\n")
            dummy_printer.text("---" * 14 + "\n")

            dummy_printer.set(align='center')
            dummy_printer.text("OBRIGADO PELA PREFERÊNCIA!\n\n")

            raw_bytes = dummy_printer.output
            return self._send_raw_bytes_to_system_printer(raw_bytes, "Via do Cliente")

        except Exception as e:
            logging.error(f"Erro ao gerar ESC/POS para via do cliente: {e}", exc_info=True)
            return False, f"Erro ao gerar via do cliente para impressão: {e}"

    def _format_customer_copy_text(self, store_info, sale_details):
        """Formata a via do cliente como texto para impressora do sistema."""
        lines = []

        # Cabeçalho
        if store_info.get('name'):
            lines.append(store_info['name'].center(40))
        if store_info.get('address'):
            lines.append(store_info['address'].center(40))
        if store_info.get('phone'):
            lines.append(store_info['phone'].center(40))

        lines.append("=" * 40)
        lines.append("VIA DO CLIENTE".center(40))
        lines.append(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}".center(40))
        lines.append("=" * 40)

        # Itens
        lines.append(f"{'DESC':<18} {'QTD':>6} {'VL. UNIT.':>8} {'VL. TOTAL':>8}")
        lines.append("-" * 40)

        for item in sale_details['items']:
            desc = item['description'][:17]
            if item['sale_type'] == 'weight':
                qtd_str = f"{item['quantity']:.3f}kg"
                unit_price_str = f"R${item['unit_price']:.2f}/kg"
            else:
                qtd_str = f"{int(item['quantity'])} un"
                unit_price_str = f"R${item['unit_price']:.2f}"

            total_price_str = f"R${item['total_price']:.2f}"
            lines.append(f"{desc:<18} {qtd_str:>6} {unit_price_str:>8} {total_price_str:>8}")

        # Total
        lines.append("=" * 40)
        total_str = f"R$ {sale_details['total_amount']:.2f}"
        lines.append(f"{'TOTAL:':<32}{total_str:>8}")
        payment_method_str = f"{sale_details['payment_method']}"
        lines.append(f"{'Forma de Pagamento:':<32}{payment_method_str:>8}")
        lines.append("=" * 40)

        # Rodapé
        lines.append("OBRIGADO PELA PREFERÊNCIA!".center(40))
        lines.append("")

        return "\n".join(lines)

    def _format_and_print_customer_copy_simulated(self, store_info, sale_details):
        """Formata e imprime a via do cliente no console (modo simulado)."""
        customer_copy = []
        customer_copy.append("--- INÍCIO DA VIA DO CLIENTE SIMULADA ---")

        # Cabeçalho
        if store_info.get('name'): customer_copy.append(f"{store_info['name'].center(40)}")
        if store_info.get('address'): customer_copy.append(f"{store_info['address'].center(40)}")
        if store_info.get('phone'): customer_copy.append(f"{store_info['phone'].center(40)}")
        customer_copy.append("---" * 13 + "\n")
        customer_copy.append("VIA DO CLIENTE".center(40))
        customer_copy.append(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}".center(40))
        customer_copy.append("---" * 13 + "\n")

        # Itens
        customer_copy.append(f"{'DESC':<18} {'QTD':>6} {'VL. UNIT.':>8} {'VL. TOTAL':>8}")
        for item in sale_details['items']:
            desc = item['description'][:17]
            if item['sale_type'] == 'weight':
                qtd_str = f"{item['quantity']:.3f}kg"
                unit_price_str = f"R${item['unit_price']:.2f}/kg"
            else:
                qtd_str = f"{int(item['quantity'])} un"
                unit_price_str = f"R${item['unit_price']:.2f}"

            total_price_str = f"R${item['total_price']:.2f}"
            customer_copy.append(f"{desc:<18} {qtd_str:>6} {unit_price_str:>8} {total_price_str:>8}")

        # Total
        customer_copy.append("---" * 13 + "\n")
        total_str = f"R$ {sale_details['total_amount']:.2f}"
        customer_copy.append(f"{'TOTAL:':<31}{total_str:>9}")
        payment_method_str = f"{sale_details['payment_method']}"
        customer_copy.append(f"{'Forma de Pagamento:':<31}{payment_method_str:>9}")
        customer_copy.append("---" * 13 + "\n")

        # Rodapé
        customer_copy.append("OBRIGADO PELA PREFERÊNCIA!".center(40))
        customer_copy.append("--- FIM DA VIA DO CLIENTE SIMULADA ---")

        logging.info("\n".join(customer_copy))

    @staticmethod
    def get_available_com_ports():
        """Retorna uma lista das portas COM disponíveis no sistema."""
        try:
            ports = serial.tools.list_ports.comports()
            return [port.device for port in ports]
        except Exception as e:
            logging.error(f"Erro ao listar portas COM: {e}", exc_info=True)
            return []
