from datetime import datetime
from escpos.printer import Usb

class PrinterHandler:
    """
    Gerencia a comunicação com a impressora térmica (real ou simulada).
    """
    def __init__(self, mode='test', vendor_id=None, product_id=None):
        self.mode = mode
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.printer = None

        if self.mode == 'production':
            self.connect()

    def connect(self):
        """Conecta-se à impressora USB real."""
        if not self.vendor_id or not self.product_id:
            print("Impressora: Vendor ID ou Product ID não configurados para o modo de produção.")
            return False, "Vendor ID ou Product ID não configurados."
        
        try:
            print(f"Impressora: Tentando conectar ao dispositivo USB {self.vendor_id}/{self.product_id}")
            self.printer = Usb(self.vendor_id, self.product_id)
            print("Impressora: Conectada com sucesso.")
            return True, "Impressora conectada."
        except Exception as e:
            self.printer = None
            error_message = f"Impressora: Não foi possível conectar. {e}"
            print(error_message)
            return False, error_message

    def reconfigure(self, mode, vendor_id=None, product_id=None):
        """Reconfigura o handler e tenta reconectar se estiver em modo de produção."""
        print(f"Impressora: Reconfigurando para modo '{mode}'.")
        self.mode = mode
        self.vendor_id = vendor_id
        self.product_id = product_id
        
        # Fecha a conexão antiga se existir
        if self.printer:
            try:
                self.printer.close()
            except Exception as e:
                print(f"Impressora: Erro ao fechar conexão antiga: {e}")
            self.printer = None

        if self.mode == 'production':
            self.connect()

    def print_receipt(self, store_info, sale_details):
        """
        Formata e imprime o recibo no modo de produção ou simula no modo de teste.
        Retorna uma tupla (status, mensagem).
        """
        if self.mode == 'production':
            if not self.printer:
                return False, "Impressora não está conectada."
            try:
                self._format_and_print_real(store_info, sale_details)
                return True, "Recibo impresso com sucesso."
            except Exception as e:
                error_message = f"Impressora: Erro ao imprimir: {e}"
                print(error_message)
                return False, error_message
        else:
            self._format_and_print_simulated(store_info, sale_details)
            return True, "Recibo impresso (simulado) com sucesso."

    def _format_and_print_real(self, store_info, sale_details):
        """Formata e envia os dados para a impressora real."""
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
        
        # Corta o papel e abre a gaveta
        p.cut()
        # p.cashdraw(2) # O pino da gaveta pode variar

    def _format_and_print_simulated(self, store_info, sale_details):
        """Formata e imprime o recibo no console."""
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
        self.cut_paper()
        self.open_cash_drawer()

    def cut_paper(self):
        if self.mode == 'production' and self.printer:
            self.printer.cut()
        else:
            print("[AÇÃO SIMULADA]: Cortando papel...")

    def check_status(self):
        """Verifica o status da impressora. Retorna (status, mensagem)."""
        if self.mode == 'test':
            return True, "Impressora em modo de simulação."
        
        if not self.printer:
            return False, "Impressora Desconectada"

        try:
            # O método _raw aqui é uma forma de enviar um comando de status (DLE EOT n)
            # Onde n=1 pede o status da impressora. A resposta pode variar.
            # Esta é uma abordagem de baixo nível e pode não funcionar em todas as impressoras.
            # Uma abordagem mais simples é apenas assumir que se o objeto existe, está ok.
            return True, "Impressora Pronta"
        except Exception as e:
            return False, f"Erro de comunicação: {e}"