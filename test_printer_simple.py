#!/usr/bin/env python3
"""
Script simples de teste para verificar se a impressora Bluetooth funciona sem sobrecarregá-la.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from hardware.printer_handler import PrinterHandler
from config_manager import ConfigManager

def test_printer_simple():
    """Testa a impressora de forma simples e segura."""
    print("=== TESTE SIMPLES DA IMPRESSORA BLUETOOTH ===\n")

    # Carrega configuração
    config_manager = ConfigManager()
    config = config_manager.get_config()
    printer_config = config.get('printer', {})

    print(f"Configuração da impressora: {printer_config}")
    print()

    # Inicializa handler da impressora
    printer = PrinterHandler(printer_config)

    # Testa apenas uma impressão simples
    print("Testando impressão simples...")

    store_info = {
        'name': 'TESTE AÇAI',
        'address': 'RUA DE TESTE, 123',
        'phone': '(88) 99999-9999'
    }

    sale_details = {
        'items': [
            {
                'description': 'Açai 200g',
                'quantity': 1,
                'unit_price': 10.00,
                'total_price': 10.00,
                'sale_type': 'unit'
            }
        ],
        'total_amount': 10.00,
        'payment_method': 'Dinheiro'
    }

    success, message = printer.print_receipt(store_info, sale_details)
    print(f"Resultado: {'OK' if success else 'FALHA'}")
    print(f"Mensagem: {message}")
    print()

    print("=== TESTE CONCLUÍDO ===")

if __name__ == "__main__":
    test_printer_simple()
