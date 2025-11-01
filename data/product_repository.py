import sqlite3
from decimal import Decimal, InvalidOperation
from utils import to_cents, to_reais
import logging
import functools
from typing import Optional, Dict, Any
from .connection import get_db_connection
from .audit_repository import log_audit

def add_product(description, barcode, price, stock, sale_type, group_id):
    """Adiciona um novo produto ao banco de dados."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        price_decimal = Decimal(str(price)).quantize(Decimal('0.01'))
        price_in_cents = to_cents(price_decimal)

        # Converte o estoque para INTEGER (multiplicando por 1000 para 3 casas decimais)
        stock_decimal = Decimal(str(stock))
        stock_integer = int(stock_decimal * 1000)

        cursor.execute(
            'INSERT INTO products (description, barcode, price, stock, quantity, sale_type, group_id) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (description, barcode, price_in_cents, stock_integer, stock_integer, sale_type, group_id)
        )
        conn.commit()
        return True, cursor.lastrowid
    except sqlite3.IntegrityError:
        return False, "Erro: Já existe um produto com este código de barras."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados ao adicionar produto: {e}"
    finally:
        conn.close()

def get_all_products():
    conn = get_db_connection()
    rows = conn.execute('SELECT p.*, g.name as group_name FROM products p LEFT JOIN product_groups g ON p.group_id = g.id ORDER BY p.description').fetchall()
    conn.close()
    products = []
    for row in rows:
        product = dict(row)
        if product['price'] is not None:
            product['price'] = to_reais(product['price'])
        # Converte stock de INTEGER para decimal (dividindo por 1000)
        if product['stock'] is not None:
            product['stock'] = Decimal(product['stock']) / Decimal('1000')
        products.append(product)
    return products

@functools.lru_cache(maxsize=100)
def get_product_by_barcode_cached(barcode: str):
    """Busca produto por código de barras com cache LRU."""
    return get_product_by_barcode(barcode)

def get_product_by_barcode(barcode):
    """Busca produto por código de barras."""
    conn = get_db_connection()
    row = conn.execute('SELECT p.*, g.name as group_name FROM products p LEFT JOIN product_groups g ON p.group_id = g.id WHERE p.barcode = ?', (barcode,)).fetchone()
    conn.close()
    if row:
        product = dict(row)
        if product['price'] is not None:
            product['price'] = to_reais(product['price'])
        if product['stock'] is not None:
            product['stock'] = Decimal(product['stock']) / Decimal('1000')
        return product
    return None

def get_product_by_barcode_or_name(identifier: str):
    """Busca um produto pelo código de barras (exato) ou pelo nome (parcial)."""
    # Tenta primeiro pelo código de barras
    product = get_product_by_barcode(identifier)
    if product:
        return product

    # Se não encontrar, busca pelo nome
    conn = get_db_connection()
    row = conn.execute(
        'SELECT p.*, g.name as group_name FROM products p LEFT JOIN product_groups g ON p.group_id = g.id WHERE p.description LIKE ? LIMIT 1',
        (f'%{identifier}%',)
    ).fetchone()
    conn.close()
    
    if row:
        product = dict(row)
        if product['price'] is not None:
            product['price'] = to_reais(product['price'])
        if product['stock'] is not None:
            product['stock'] = Decimal(product['stock']) / Decimal('1000')
        return product
        
    return None

def clear_product_cache():
    """Limpa cache de produtos."""
    get_product_by_barcode_cached.cache_clear()
    logging.info("Cache de produtos limpo")

def get_cache_stats() -> Dict[str, Any]:
    """Retorna estatísticas do cache."""
    cache_info = get_product_by_barcode_cached.cache_info()
    return {
        'cache_hits': cache_info.hits,
        'cache_misses': cache_info.misses,
        'cache_size': cache_info.currsize,
        'max_size': cache_info.maxsize
    }

def update_product(product_id, description, barcode, price, stock, sale_type, group_id):
    """Atualiza os dados de um produto existente."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        price_decimal = Decimal(str(price)).quantize(Decimal('0.01'))
        price_in_cents = to_cents(price_decimal)

        # Converte o estoque para INTEGER (multiplicando por 1000 para 3 casas decimais)
        stock_decimal = Decimal(str(stock))
        stock_integer = int(stock_decimal * 1000)

        cursor.execute('''
            UPDATE products
            SET description = ?, barcode = ?, price = ?, stock = ?, quantity = ?, sale_type = ?, group_id = ?,
                sync_status = CASE WHEN sync_status = 'pending_create' THEN 'pending_create' ELSE 'pending_update' END
            WHERE id = ?
        ''', (description, barcode, price_in_cents, stock_integer, stock_integer, sale_type, group_id, product_id))
        conn.commit()
        return True, "Produto atualizado com sucesso."
    except sqlite3.IntegrityError:
        return False, "Erro: O código de barras informado já pertence a outro produto."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados ao atualizar produto: {e}"
    finally:
        conn.close()

def delete_product(product_id):
    """Deleta um produto do banco de dados."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
        conn.commit()
        if cursor.rowcount > 0:
            return True, "Produto deletado com sucesso."
        return False, "Produto não encontrado."
    except sqlite3.IntegrityError:
        return False, "Erro: Este produto não pode ser deletado pois está associado a vendas existentes."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados ao deletar produto: {e}"
    finally:
        conn.close()

def update_stock_by_barcode(barcode: str, new_stock: float, user_id: int):
    """Atualiza o estoque de um produto pelo código de barras."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Converte o novo estoque para o formato de inteiro
        stock_decimal = Decimal(str(new_stock))
        stock_integer = int(stock_decimal * 1000)

        # Busca o produto para log de auditoria
        old_product = get_product_by_barcode(barcode)
        if not old_product:
            return False, "Produto não encontrado."

        cursor.execute(
            'UPDATE products SET stock = ?, quantity = ?, sync_status = CASE WHEN sync_status = \'pending_create\' THEN \'pending_create\' ELSE \'pending_update\' END WHERE barcode = ?',
            (stock_integer, stock_integer, barcode)
        )
        conn.commit()

        if cursor.rowcount > 0:
            log_audit(
                user_id,
                'STOCK_ADJUSTMENT',
                'products',
                old_product['id'],
                old_values=f"Estoque anterior: {old_product['stock']}",
                new_values=f"Novo estoque: {new_stock}"
            )
            return True, "Estoque atualizado com sucesso."
        
        return False, "Produto com o código de barras não encontrado."
    except (ValueError, InvalidOperation):
        return False, "Valor de estoque inválido."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Erro de banco de dados: {e}"
    finally:
        conn.close()

def update_product_price(barcode, new_price):
    """Atualiza o preço de um produto pelo código de barras."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        price_decimal = Decimal(str(new_price)).quantize(Decimal('0.01'))
        price_in_cents = to_cents(price_decimal)
        cursor.execute('UPDATE products SET price = ?, sync_status = CASE WHEN sync_status = \'pending_create\' THEN \'pending_create\' ELSE \'pending_update\' END WHERE barcode = ?', (price_in_cents, barcode))
        conn.commit()
        if cursor.rowcount > 0:
            return True, "Preço atualizado com sucesso."
        return False, "Produto com o código de barras não encontrado."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Erro de banco de dados ao atualizar preço: {e}"
    finally:
        conn.close()
