from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import locale
import os

# Configura o locale para o formato de moeda brasileiro
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil.1252')
    except locale.Error:
        print("Aviso: Locale 'pt_BR.UTF-8' ou 'Portuguese_Brazil.1252' não encontrado. A formatação pode não ser a ideal.")

def to_cents(value: Decimal) -> int:
    """Converte um valor Decimal para centavos (inteiro) de forma segura."""
    return int(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) * 100)

def to_reais(value: int) -> Decimal:
    """Converte um valor inteiro em centavos para um Decimal em reais."""
    if value is None:
        return Decimal('0.00')
    return (Decimal(value) / 100).quantize(Decimal('0.01'))

def format_currency(value, is_negative=False) -> str:
    """Formata um valor Decimal para uma string de moeda BRL (R$ 1.234,56)."""
    if value is None:
        value = Decimal('0.00')
    
    value = Decimal(value)

    if is_negative:
        value = -abs(value)

    try:
        return locale.currency(value, symbol=True, grouping=True)
    except (NameError, AttributeError):
        # Fallback manual caso o locale falhe
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parse_currency(value_str: str) -> Decimal:
    """Converte uma string de moeda BRL para um valor Decimal."""
    if not isinstance(value_str, str) or not value_str.strip():
        return Decimal('0.00')
        
    cleaned_str = value_str.replace("R$", "").strip().replace(".", "").replace(",", ".")
    
    try:
        return Decimal(cleaned_str)
    except InvalidOperation:
        raise InvalidOperation(f"Valor monetário inválido: '{value_str}'")

def get_data_path(filename):
    app_data_path = os.getenv('APPDATA')
    folder_name = 'PDV Moderno'
    data_path = os.path.join(app_data_path, folder_name)
    
    if not os.path.exists(data_path):
        os.makedirs(data_path)
        
    return os.path.join(data_path, filename)

def safe_decimal(value, default='0.0'):
    """Converte um valor para Decimal de forma segura, retornando um padrão se o valor for None ou vazio."""
    if value is None or value == '':
        value = default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return Decimal(default)