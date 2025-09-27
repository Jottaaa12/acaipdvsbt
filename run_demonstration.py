
import database as db
import os
import time

def run_demo():
    """Executa uma sequência de testes para demonstrar a lógica do backend."""
    
    print("--- INICIANDO PAINEL DE TESTE ---")
    
    # 1. Limpar o banco de dados
    if os.path.exists(db.DB_FILE):
        os.remove(db.DB_FILE)
        print(f"[PASSO 1] Banco de dados antigo ('{db.DB_FILE}') removido.")
    
    time.sleep(1)
    db.create_tables()
    print("[PASSO 2] Tabelas do banco de dados criadas do zero.")
    
    time.sleep(1)
    # 2. Adicionar produtos
    print("\n[PASSO 3] Adicionando produtos de exemplo...")
    products_to_add = [
        ("Pão Francês", "78900001", 0.75, 100, "unit"),
        ("Leite Integral", "78900002", 5.50, 50, "unit"),
        ("Queijo Mussarela", "78900003", 45.90, 10.0, "weight"), # 10 kg de estoque
        ("Presunto Cozido", "78900004", 38.50, 8.5, "weight")
    ]
    for p in products_to_add:
        db.add_product(*p)
        print(f"  - Produto '{p[0]}' adicionado.")

    time.sleep(1)
    # 3. Mostrar estoque inicial
    print("\n[PASSO 4] Verificando estoque inicial:")
    initial_stock = db.get_all_products()
    for product in initial_stock:
        print(f"  - {product['description']:<18} | Estoque: {product['stock']}")

    time.sleep(1)
    # 4. Simular uma venda
    print("\n[PASSO 5] Simulando uma venda...")
    pao = db.get_product_by_barcode("78900001")
    queijo = db.get_product_by_barcode("78900003")
    
    sale_items = [
        {'id': pao['id'], 'quantity': 10, 'unit_price': pao['price'], 'total_price': 10 * pao['price']},
        {'id': queijo['id'], 'quantity': 0.545, 'unit_price': queijo['price'], 'total_price': 0.545 * queijo['price']}
    ]
    total = sum(item['total_price'] for item in sale_items)
    print(f"  - Venda: 10x '{pao['description']}' e 0.545kg de '{queijo['description']}'.")
    print(f"  - Total da Venda: R$ {total:.2f}")

    time.sleep(1)
    # 5. Registrar a venda
    db.register_sale(total, "Dinheiro", sale_items)
    print("\n[PASSO 6] Venda registrada no banco de dados. Estoque será atualizado.")

    time.sleep(1)
    # 6. Mostrar estoque final
    print("\n[PASSO 7] Verificando estoque final:")
    final_stock = db.get_all_products()
    for product in final_stock:
        stock_change = product['stock'] - next(p['stock'] for p in initial_stock if p['id'] == product['id'])
        print(f"  - {product['description']:<18} | Estoque: {product['stock']:.3f} (Alteração: {stock_change:.3f})")

    print("\n--- DEMONSTRAÇÃO CONCLUÍDA ---")

if __name__ == '__main__':
    run_demo()
    input("\nPressione Enter para sair...")
