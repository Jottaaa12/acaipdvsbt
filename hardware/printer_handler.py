from datetime import datetime
from escpos.printer import Usb, Serial, Network
from escpos.exceptions import DeviceNotFoundError
import serial.tools.list_ports
import win32print
import win32api

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

            print(f"Impressora USB: Conectando ao dispositivo {vendor_id}/{product_id}")
            self.printer = Usb(vendor_id_int, product_id_int)
            print("Impressora USB: Conectada com sucesso")
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
        else:
            port = self.printer_config.get('serial_port')

        baudrate = self.printer_config.get('serial_baudrate', 9600)

        if not port:
            self.error_message = "Porta COM é obrigatória para impressora serial"
            return False, self.error_message

        try:
            print(f"Impressora Serial: Conectando à porta {port} ({baudrate} baud)")
            self.printer = Serial(port, baudrate=baudrate)
            print("Impressora Serial: Conectada com sucesso")
            return True, f"Impressora Serial conectada na porta {port}"

        except Exception as e:
            self.error_message = f"Erro ao conectar à porta {port}: {e}"
            return False, self.error_message

    def _connect_network(self):
        """Conecta a uma impressora de rede."""
        host = self.printer_config.get('network_ip')
        port = self.printer_config.get('network_port', 9100)

        if not host:
            self.error_message = "Endereço IP é obrigatório para impressora de rede"
            return False, self.error_message

        try:
            print(f"Impressora de Rede: Conectando a {host}:{port}")
            self.printer = Network(host, port=port)
            print("Impressora de Rede: Conectada com sucesso")
            return True, f"Impressora de rede conectada em {host}:{port}"

        except Exception as e:
            self.error_message = f"Erro ao conectar à impressora de rede {host}:{port}: {e}"
            return False, self.error_message

    def _connect_system_printer(self):
        """Usa a impressora padrão do sistema Windows."""
        try:
            # Obtém a impressora padrão
            printer_name = win32print.GetDefaultPrinter()
            print(f"Impressora do Sistema: Usando impressora padrão '{printer_name}'")
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
        print(f"Impressora: Reconfigurando para tipo '{printer_config.get('type', 'disabled')}'")

        # Fecha conexão anterior
        if self.printer and hasattr(self.printer, 'close'):
            try:
                self.printer.close()
            except Exception as e:
                print(f"Impressora: Erro ao fechar conexão anterior: {e}")

        self.printer_config = printer_config
        self.printer = None
        self.error_message = None
        self.printer_type = printer_config.get('type', 'disabled')

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

        # Verifica se há erro de conexão
        if self.error_message:
            return False, f"Erro de conexão: {self.error_message}"

        # Se não há conexão, tenta conectar
        if not self.printer:
            success, message = self.connect()
            if not success:
                return False, message

        try:
            if self.printer_type == 'system_printer':
                return self._print_system_printer(store_info, sale_details)
            else:
                return self._print_thermal_printer(store_info, sale_details)

        except Exception as e:
            error_message = f"Erro ao imprimir: {e}"
            print(f"Impressora: {error_message}")
            return False, error_message

    def _print_thermal_printer(self, store_info, sale_details):
        """Imprime em impressora térmica (USB, Serial, Network)."""
        p = self.printer

        # Cabeçalho
        p.set(align='center', text_type='B')
        if store_info.get('name'): p.text(f"{store_info['name']}\n")
        if store_info.get('address'): p.text(f"{store_info['address']}\n")
        if store_info.get('phone'): p.text(f"{store_info['phone']}\n")
        p.text("---" * 14 + "\n")
        p.set(align='center', text_type='A')
        p.text("RECIBO - SEM VALOR FISCAL\n")
        p.set(align='center')
        p.text(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        p.text("---" * 14 + "\n")

        # Itens
        p.set(align='left', text_type='B')
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

        # Total
        p.text("---" * 14 + "\n")
        p.set(align='right', text_type='A')
        total_str = f"R$ {sale_details['total_amount']:.2f}"
        p.text(f"TOTAL: {total_str}\n")
        p.set(text_type='B')
        p.text(f"Forma de Pagamento: {sale_details['payment_method']}\n")
        p.text("---" * 14 + "\n")

        # Rodapé
        p.set(align='center')
        p.text("OBRIGADO PELA PREFERÊNCIA!\n\n")

        # Corta o papel
        p.cut()

        return True, "Recibo impresso com sucesso"

    def _print_system_printer(self, store_info, sale_details):
        """Imprime usando a impressora padrão do sistema Windows."""
        try:
            # Obtém a impressora padrão
            printer_name = win32print.GetDefaultPrinter()

            # Formata o recibo como texto
            receipt_text = self._format_receipt_text(store_info, sale_details)

            # Imprime o texto
            win32api.ShellExecute(
                0,
                "print",
                receipt_text,
                f'/d:"{printer_name}"',
                ".",
                0
            )

            return True, f"Recibo enviado para impressora do sistema: {printer_name}"

        except Exception as e:
            return False, f"Erro ao imprimir no sistema: {e}"

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

        print("\n".join(receipt))

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
                p.set(align='center', text_type='B')
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

    @staticmethod
    def get_available_com_ports():
        """Retorna uma lista das portas COM disponíveis no sistema."""
        try:
            ports = serial.tools.list_ports.comports()
            return [port.device for port in ports]
        except Exception as e:
            print(f"Erro ao listar portas COM: {e}")
            return []
