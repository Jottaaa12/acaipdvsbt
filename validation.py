import re
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple, List, Dict, Any
import logging

class ValidationResult:
    """
    Classe para encapsular resultado de validação.
    """

    def __init__(self, is_valid: bool, errors: List[str] = None, warnings: List[str] = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []

    def add_error(self, error: str) -> None:
        """Adiciona erro à lista."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """Adiciona aviso à lista."""
        self.warnings.append(warning)

    def has_errors(self) -> bool:
        """Verifica se há erros."""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Verifica se há avisos."""
        return len(self.warnings) > 0

class InputValidator:
    """
    Sistema centralizado de validação de entrada para o PDV.
    Fornece métodos seguros para validação de diferentes tipos de dados.
    """

    # Padrões regex para validação
    BARCODE_PATTERN = re.compile(r'^[0-9]{8,18}$')  # Código de barras: 8-18 dígitos
    CPF_PATTERN = re.compile(r'^[0-9]{11}$')  # CPF: 11 dígitos
    CNPJ_PATTERN = re.compile(r'^[0-9]{14}$')  # CNPJ: 14 dígitos
    PHONE_PATTERN = re.compile(r'^[0-9]{10,11}$')  # Telefone: 10-11 dígitos
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    # Constantes de validação
    MIN_PASSWORD_LENGTH = 6
    MAX_PASSWORD_LENGTH = 50
    MIN_PRODUCT_NAME_LENGTH = 2
    MAX_PRODUCT_NAME_LENGTH = 100
    MIN_PRICE = 0.01
    MAX_PRICE = 10000.00
    MIN_QUANTITY = 0.001
    MAX_QUANTITY = 10000.000

    @staticmethod
    def validate_barcode(barcode: str) -> Tuple[bool, str]:
        """
        Valida código de barras.

        Args:
            barcode: Código de barras a ser validado

        Returns:
            Tuple[bool, str]: (válido, mensagem de erro)
        """
        if not barcode:
            return False, "Código de barras é obrigatório"

        if not isinstance(barcode, str):
            return False, "Código de barras deve ser texto"

        barcode = barcode.strip()

        if not InputValidator.BARCODE_PATTERN.match(barcode):
            return False, "Código de barras deve conter apenas números (8-18 dígitos)"

        return True, ""

    @staticmethod
    def safe_decimal_convert(value: str, field_name: str = "valor") -> Tuple[Optional[Decimal], str]:
        """
        Conversão segura para Decimal com tratamento de erro.

        Args:
            value: Valor a ser convertido
            field_name: Nome do campo para mensagem de erro

        Returns:
            Tuple[Optional[Decimal], str]: (valor convertido, mensagem de erro)
        """
        if not value:
            return None, f"{field_name} é obrigatório"

        try:
            # Remove pontos e vírgulas inadequados
            cleaned_value = value.strip().replace('.', '').replace(',', '.')

            # Converte para Decimal
            decimal_value = Decimal(cleaned_value)

            # Valida se não é negativo para valores que não podem ser
            if field_name.lower() in ['preço', 'quantidade', 'peso', 'valor']:
                if decimal_value <= 0:
                    return None, f"{field_name} deve ser maior que zero"

            return decimal_value, ""

        except InvalidOperation:
            return None, f"{field_name} deve ser um número válido"
        except Exception as e:
            logging.error(f"Erro na conversão decimal de {field_name}: {e}")
            return None, f"Erro interno na validação de {field_name}"

    @staticmethod
    def validate_product_data(data: Dict[str, Any]) -> ValidationResult:
        """
        Valida dados completos do produto.

        Args:
            data: Dicionário com dados do produto

        Returns:
            ValidationResult: Resultado da validação
        """
        result = ValidationResult(True)

        # Validação obrigatória de descrição
        description = data.get('description', '').strip()
        if not description:
            result.add_error("Descrição do produto é obrigatória")
        elif len(description) < InputValidator.MIN_PRODUCT_NAME_LENGTH:
            result.add_error(f"Descrição deve ter pelo menos {InputValidator.MIN_PRODUCT_NAME_LENGTH} caracteres")
        elif len(description) > InputValidator.MAX_PRODUCT_NAME_LENGTH:
            result.add_error(f"Descrição deve ter no máximo {InputValidator.MAX_PRODUCT_NAME_LENGTH} caracteres")

        # Validação de código de barras
        barcode = data.get('barcode', '').strip()
        if barcode:
            is_valid, error_msg = InputValidator.validate_barcode(barcode)
            if not is_valid:
                result.add_error(f"Código de barras: {error_msg}")

        # Validação de preço
        price = data.get('price')
        if price is not None:
            price_decimal, price_error = InputValidator.safe_decimal_convert(str(price), "Preço")
            if price_error:
                result.add_error(f"Preço: {price_error}")
            elif price_decimal < InputValidator.MIN_PRICE or price_decimal > InputValidator.MAX_PRICE:
                result.add_error(f"Preço deve estar entre R$ {InputValidator.MIN_PRICE:.2f} e R$ {InputValidator.MAX_PRICE:.2f}")

        # Validação de estoque
        stock = data.get('stock')
        if stock is not None:
            stock_decimal, stock_error = InputValidator.safe_decimal_convert(str(stock), "Estoque")
            if stock_error:
                result.add_error(f"Estoque: {stock_error}")
            elif stock_decimal < 0:
                result.add_error("Estoque não pode ser negativo")

        # Validação de tipo de venda
        sale_type = data.get('sale_type')
        if sale_type and sale_type not in ['unit', 'weight']:
            result.add_error("Tipo de venda deve ser 'unit' ou 'weight'")

        return result

    @staticmethod
    def validate_user_data(data: Dict[str, Any]) -> ValidationResult:
        """
        Valida dados de usuário.

        Args:
            data: Dicionário com dados do usuário

        Returns:
            ValidationResult: Resultado da validação
        """
        result = ValidationResult(True)

        # Validação obrigatória de username
        username = data.get('username', '').strip()
        if not username:
            result.add_error("Nome de usuário é obrigatório")
        elif len(username) < 3:
            result.add_error("Nome de usuário deve ter pelo menos 3 caracteres")
        elif len(username) > 30:
            result.add_error("Nome de usuário deve ter no máximo 30 caracteres")
        elif not re.match(r'^[a-zA-Z0-9_]+$', username):
            result.add_error("Nome de usuário deve conter apenas letras, números e underscore")

        # Validação de senha
        password = data.get('password', '').strip()
        if password:
            if len(password) < InputValidator.MIN_PASSWORD_LENGTH:
                result.add_error(f"Senha deve ter pelo menos {InputValidator.MIN_PASSWORD_LENGTH} caracteres")
            elif len(password) > InputValidator.MAX_PASSWORD_LENGTH:
                result.add_error(f"Senha deve ter no máximo {InputValidator.MAX_PASSWORD_LENGTH} caracteres")

        # Validação de role
        role = data.get('role')
        if role and role not in ['operador', 'gerente']:
            result.add_error("Cargo deve ser 'operador' ou 'gerente'")

        return result

    @staticmethod
    def validate_payment_data(data: Dict[str, Any]) -> ValidationResult:
        """
        Valida dados de pagamento.

        Args:
            data: Dicionário com dados de pagamento

        Returns:
            ValidationResult: Resultado da validação
        """
        result = ValidationResult(True)

        # Validação obrigatória de método de pagamento
        payment_method = data.get('payment_method', '').strip()
        if not payment_method:
            result.add_error("Método de pagamento é obrigatório")

        # Validação de valor
        amount = data.get('amount')
        if amount is not None:
            amount_decimal, amount_error = InputValidator.safe_decimal_convert(str(amount), "Valor")
            if amount_error:
                result.add_error(f"Valor: {amount_error}")
            elif amount_decimal <= 0:
                result.add_error("Valor deve ser maior que zero")

        return result

    @staticmethod
    def validate_cash_session_data(data: Dict[str, Any]) -> ValidationResult:
        """
        Valida dados de sessão de caixa.

        Args:
            data: Dicionário com dados da sessão

        Returns:
            ValidationResult: Resultado da validação
        """
        result = ValidationResult(True)

        # Validação obrigatória de valor inicial
        initial_amount = data.get('initial_amount')
        if initial_amount is not None:
            amount_decimal, amount_error = InputValidator.safe_decimal_convert(str(initial_amount), "Valor inicial")
            if amount_error:
                result.add_error(f"Valor inicial: {amount_error}")
            elif amount_decimal < 0:
                result.add_error("Valor inicial não pode ser negativo")

        return result

    @staticmethod
    def validate_sale_data(data: Dict[str, Any]) -> ValidationResult:
        """
        Valida dados de venda.

        Args:
            data: Dicionário com dados da venda

        Returns:
            ValidationResult: Resultado da validação
        """
        result = ValidationResult(True)

        # Validação de itens
        items = data.get('items', [])
        if not items:
            result.add_error("Venda deve conter pelo menos um item")
        else:
            for i, item in enumerate(items):
                item_result = InputValidator.validate_sale_item_data(item, i + 1)
                if not item_result.is_valid:
                    result.errors.extend([f"Item {i+1}: {error}" for error in item_result.errors])
                    result.is_valid = False

        # Validação de pagamentos
        payments = data.get('payments', [])
        if not payments:
            result.add_error("Venda deve conter pelo menos uma forma de pagamento")
        else:
            total_payments = sum(Decimal(str(p.get('amount', 0))) for p in payments)
            total_sale = sum(Decimal(str(item.get('total_price', 0))) for item in items)

            if total_payments != total_sale:
                result.add_warning(f"Total de pagamentos (R$ {total_payments:.2f}) difere do total da venda (R$ {total_sale:.2f})")

        return result

    @staticmethod
    def validate_sale_item_data(item: Dict[str, Any], item_number: int = 1) -> ValidationResult:
        """
        Valida dados de item de venda.

        Args:
            item: Dicionário com dados do item
            item_number: Número do item para mensagens de erro

        Returns:
            ValidationResult: Resultado da validação
        """
        result = ValidationResult(True)

        # Validação obrigatória de produto
        if not item.get('id'):
            result.add_error(f"Produto do item {item_number} é obrigatório")

        # Validação de quantidade
        quantity = item.get('quantity')
        if quantity is not None:
            try:
                quantity_decimal = Decimal(str(quantity))
                if quantity_decimal <= 0:
                    result.add_error(f"Quantidade do item {item_number} deve ser maior que zero")
                elif quantity_decimal > InputValidator.MAX_QUANTITY:
                    result.add_error(f"Quantidade do item {item_number} deve ser menor que {InputValidator.MAX_QUANTITY}")
            except (InvalidOperation, ValueError, TypeError):
                result.add_error(f"Quantidade do item {item_number} deve ser um número válido")

        # Validação de preço unitário
        unit_price = item.get('unit_price')
        if unit_price is not None:
            price_decimal, price_error = InputValidator.safe_decimal_convert(str(unit_price), f"Preço unitário do item {item_number}")
            if price_error:
                result.add_error(f"Preço unitário do item {item_number}: {price_error}")

        return result

    @staticmethod
    def validate_phone_number(phone: str) -> Tuple[bool, str]:
        """
        Valida número de telefone.

        Args:
            phone: Número de telefone a ser validado

        Returns:
            Tuple[bool, str]: (válido, mensagem de erro)
        """
        if not phone:
            return True, ""  # Telefone é opcional

        if not isinstance(phone, str):
            return False, "Telefone deve ser texto"

        phone = re.sub(r'[^0-9]', '', phone)  # Remove caracteres não numéricos

        if not InputValidator.PHONE_PATTERN.match(phone):
            return False, "Telefone deve conter 10 ou 11 dígitos"

        return True, ""

    @staticmethod
    def validate_email(email: str) -> Tuple[bool, str]:
        """
        Valida endereço de email.

        Args:
            email: Email a ser validado

        Returns:
            Tuple[bool, str]: (válido, mensagem de erro)
        """
        if not email:
            return True, ""  # Email é opcional

        if not isinstance(email, str):
            return False, "Email deve ser texto"

        email = email.strip()

        if not InputValidator.EMAIL_PATTERN.match(email):
            return False, "Email deve ter formato válido (exemplo@dominio.com)"

        return True, ""

    @staticmethod
    def validate_cpf_cnpj(document: str) -> Tuple[bool, str]:
        """
        Valida CPF ou CNPJ.

        Args:
            document: CPF ou CNPJ a ser validado

        Returns:
            Tuple[bool, str]: (válido, mensagem de erro)
        """
        if not document:
            return True, ""  # Documento é opcional

        if not isinstance(document, str):
            return False, "Documento deve ser texto"

        document = re.sub(r'[^0-9]', '', document)  # Remove caracteres não numéricos

        if len(document) == 11:
            # Validação de CPF
            if not InputValidator._validate_cpf_digits(document):
                return False, "CPF inválido"
        elif len(document) == 14:
            # Validação de CNPJ
            if not InputValidator._validate_cnpj_digits(document):
                return False, "CNPJ inválido"
        else:
            return False, "Documento deve ter 11 dígitos (CPF) ou 14 dígitos (CNPJ)"

        return True, ""

    @staticmethod
    def _validate_cpf_digits(cpf: str) -> bool:
        """Valida dígitos verificadores do CPF."""
        if len(cpf) != 11 or cpf == cpf[0] * 11:
            return False

        # Calcula primeiro dígito verificador
        soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
        digito1 = (11 - (soma % 11)) % 10

        # Calcula segundo dígito verificador
        soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
        digito2 = (11 - (soma % 11)) % 10

        return int(cpf[9]) == digito1 and int(cpf[10]) == digito2

    @staticmethod
    def _validate_cnpj_digits(cnpj: str) -> bool:
        """Valida dígitos verificadores do CNPJ."""
        if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
            return False

        # Calcula primeiro dígito verificador
        pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        soma1 = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
        digito1 = 11 - (soma1 % 11)
        if digito1 >= 10:
            digito1 = 0

        # Calcula segundo dígito verificador
        pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        soma2 = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
        digito2 = 11 - (soma2 % 11)
        if digito2 >= 10:
            digito2 = 0

        return int(cnpj[12]) == digito1 and int(cnpj[13]) == digito2

    @staticmethod
    def validate_percentage(value: str) -> Tuple[bool, str]:
        """
        Valida valor percentual (0-100).

        Args:
            value: Valor percentual a ser validado

        Returns:
            Tuple[bool, str]: (válido, mensagem de erro)
        """
        if not value:
            return False, "Percentual é obrigatório"

        try:
            percent = Decimal(value.replace(',', '.'))
            if percent < 0 or percent > 100:
                return False, "Percentual deve estar entre 0 e 100"
            return True, ""
        except (InvalidOperation, ValueError, TypeError):
            return False, "Percentual deve ser um número válido"

    @staticmethod
    def validate_text_length(text: str, field_name: str, min_length: int = 0,
                           max_length: int = None) -> Tuple[bool, str]:
        """
        Valida comprimento de texto.

        Args:
            text: Texto a ser validado
            field_name: Nome do campo para mensagem de erro
            min_length: Comprimento mínimo
            max_length: Comprimento máximo

        Returns:
            Tuple[bool, str]: (válido, mensagem de erro)
        """
        if not isinstance(text, str):
            return False, f"{field_name} deve ser texto"

        text = text.strip()

        if min_length > 0 and len(text) < min_length:
            return False, f"{field_name} deve ter pelo menos {min_length} caracteres"

        if max_length and len(text) > max_length:
            return False, f"{field_name} deve ter no máximo {max_length} caracteres"

        return True, ""

    @staticmethod
    def sanitize_numeric_input(value: str) -> str:
        """
        Sanitiza entrada numérica, removendo caracteres inválidos.

        Args:
            value: Valor a ser sanitizado

        Returns:
            str: Valor sanitizado
        """
        if not value:
            return ""

        # Remove tudo que não for dígito, ponto ou vírgula
        sanitized = re.sub(r'[^\d.,]', '', value)

        # Remove múltiplos pontos ou vírgulas
        while '..' in sanitized:
            sanitized = sanitized.replace('..', '.')
        while ',,' in sanitized:
            sanitized = sanitized.replace(',,', ',')

        return sanitized

    @staticmethod
    def format_currency(value: Decimal) -> str:
        """
        Formata valor para exibição em moeda.

        Args:
            value: Valor a ser formatado

        Returns:
            str: Valor formatado
        """
        return f"R$ {value:.2f}".replace('.', ',')

    @staticmethod
    def format_quantity(value: Decimal, sale_type: str = 'unit') -> str:
        """
        Formata quantidade para exibição.

        Args:
            value: Valor a ser formatado
            sale_type: Tipo de venda ('unit' ou 'weight')

        Returns:
            str: Quantidade formatada
        """
        if sale_type == 'weight':
            return f"{value:.3f} kg"
        else:
            return str(int(value))

# Funções de conveniência para uso direto
def validate_barcode_safe(barcode: str) -> bool:
    """Valida código de barras de forma segura."""
    return InputValidator.validate_barcode(barcode)[0]

def validate_product_safe(data: Dict[str, Any]) -> bool:
    """Valida dados de produto de forma segura."""
    return InputValidator.validate_product_data(data).is_valid

def safe_decimal(value: str, field_name: str = "valor") -> Optional[Decimal]:
    """Converte string para Decimal de forma segura."""
    result, _ = InputValidator.safe_decimal_convert(value, field_name)
    return result
