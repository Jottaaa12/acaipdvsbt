

import random
from datetime import datetime

class PrinterHandler:
    """
    Classe simulada para formatar e "imprimir" recibos.
    Em um cenário real, esta classe usaria a biblioteca python-escpos
    para se comunicar com uma impressora térmica.
    """
    def __init__(self, vendor_id=None, product_id=None):
        # Ex: self.printer = Usb(vendor_id, product_id)
        self.vendor_id = vendor_id
        self.product_id = product_id
        print(f"Simulador de Impressora: Configurado para o dispositivo USB {vendor_id}/{product_id}")

    def reconfigure(self, vendor_id=None, product_id=None):
        self.vendor_id = vendor_id
        self.product_id = product_id
        print(f"Simulador de Impressora: Reconfigurado para o dispositivo USB {vendor_id}/{product_id}")

    def print_receipt(self, store_info, sale_details):
        """
        Formata e imprime o recibo. Retorna uma tupla (status, mensagem).
        `store_info` é um dicionário com dados da loja (nome, endereço).
        `sale_details` é um dicionário com os dados da venda (itens, total, etc.).
        """
        try:
            # Simula uma falha aleatória (ex: impressora offline)
            if self.vendor_id and random.random() < 0.1: # 10% de chance de falha se não for modo simulação puro
                raise IOError("A impressora não está respondendo.")

            receipt = []
            receipt.append("--- INÍCIO DO RECIBO SIMULADO ---")
            
            # Cabeçalho
            if store_info.get('name'):
                receipt.append(f"{store_info['name'].center(40)}")
            if store_info.get('address'):
                receipt.append(f"{store_info['address'].center(40)}")
            if store_info.get('phone'):
                receipt.append(f"{store_info['phone'].center(40)}")
            receipt.append("-" * 40)
            receipt.append("RECIBO - SEM VALOR FISCAL".center(40))
            receipt.append(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}".center(40))
            receipt.append("-" * 40)

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
            receipt.append("-" * 40)
            total_str = f"R$ {sale_details['total_amount']:.2f}"
            receipt.append(f"{'TOTAL:':<31}{total_str:>9}")
            payment_method_str = f"{sale_details['payment_method']}"
            receipt.append(f"{'Forma de Pagamento:':<31}{payment_method_str:>9}")
            receipt.append("-" * 40)

            # Rodapé
            receipt.append("OBRIGADO PELA PREFERÊNCIA!".center(40))
            receipt.append("--- FIM DO RECIBO SIMULADO ---")
            
            # Imprime tudo de uma vez no console
            print("\n".join(receipt))

            # Simula o corte do papel e abertura da gaveta
            self.cut_paper()
            self.open_cash_drawer()
            
            return True, "Recibo impresso (simulado) com sucesso."

        except Exception as e:
            error_message = f"Erro ao imprimir recibo: {e}"
            print(error_message)
            return False, error_message

    def cut_paper(self):
        print("[AÇÃO SIMULADA]: Cortando papel...")

    def open_cash_drawer(self):
        print("[AÇÃO SIMULADA]: Abrindo gaveta de dinheiro...")

    def check_status(self):
        """Verifica o status da impressora. Retorna (status, mensagem)."""
        # Em um cenário real, isso poderia usar `self.printer.get_status()`
        # Para o simulador, vamos retornar um status aleatório.
        if self.vendor_id is None:
            return True, "Impressora em modo de simulação pura."

        if random.random() < 0.1: # 10% de chance de erro
            return False, "Impressora Offline ou Sem Papel"
        
        return True, "Impressora Pronta"
if __name__ == '__main__':
    # Exemplo de uso
    printer = PrinterHandler('0x1234', '0x5678')
    
    mock_store_info = {
        "name": "Mercado do Zé",
        "address": "Rua das Flores, 123",
        "phone": "(11) 1234-5678"
    }

    mock_sale = {
        'items': [
            {'description': 'Pão Francês', 'quantity': 5, 'unit_price': 0.50, 'total_price': 2.50, 'sale_type': 'unit'},
            {'description': 'Queijo Mussarela Fatiado', 'quantity': 0.350, 'unit_price': 40.00, 'total_price': 14.00, 'sale_type': 'weight'},
            {'description': 'Refrigerante 2L', 'quantity': 1, 'unit_price': 8.00, 'total_price': 8.00, 'sale_type': 'unit'}
        ],
        'total_amount': 24.50,
        'payment_method': 'Dinheiro'
    }

    printer.print_receipt(mock_store_info, mock_sale)
