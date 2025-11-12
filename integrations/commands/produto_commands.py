# integrations/commands/produto_commands.py
from .base_command import BaseCommand
from typing import List

class ProdutoCommand(BaseCommand):
    """Lida com subcomandos relacionados a produtos."""
    def execute(self) -> str:
        if not self.args:
            return "Uso: /produto [consultar|alterar_preco] <argumentos>"

        subcommand = self.args[0].lower()
        command_args = self.args[1:]

        if subcommand == 'consultar':
            return self._handle_produto_consultar(command_args)
        elif subcommand == 'alterar_preco':
            return self._handle_produto_alterar_preco(command_args)
        else:
            return self._handle_produto_consultar(self.args)

    def _handle_produto_consultar(self, args: List[str]) -> str:
        """Busca e retorna informações de um produto."""
        if not args:
            return "Uso: /produto consultar <código de barras ou nome>"

        identifier = " ".join(args)
        try:
            product = self.db.get_product_by_barcode_or_name(identifier)

            if not product:
                return f"🔎 Nenhum produto encontrado com o identificador '{identifier}'."

            stock_str = f"{product['stock']:.3f}".replace('.', ',')
            sale_type_str = "Unidade" if product['sale_type'] == 'unit' else "Peso"

            response = (
                f"📦 *Detalhes do Produto*\n\n"
                f"📝 *Descrição:* `{product['description']}`\n"
                f"🔢 *Cód. Barras:* `{product['barcode'] or 'N/A'}`\n"
                f"💰 *Preço:* `R$ {product['price']:.2f}`\n"
                f"🗃️ *Estoque:* `{stock_str}`\n"
                f"⚖️ *Vendido por:* `{sale_type_str}`\n"
                f"📂 *Grupo:* `{product['group_name'] or 'Nenhum'}`"
            )
            return response

        except Exception as e:
            self.logging.error(f"Erro ao buscar produto via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao buscar o produto."

    def _handle_produto_alterar_preco(self, args: List[str]) -> str:
        """Altera o preço de um produto."""
        try:
            if len(args) != 2:
                return "Uso: /produto alterar_preco <código_de_barras> <novo_preço>"

            barcode = args[0]
            new_price_str = args[1].replace(',', '.')
            new_price = float(new_price_str)

            old_product = self.db.get_product_by_barcode(barcode)
            if not old_product:
                return f"❌ Produto com código de barras '{barcode}' não encontrado."

            success, message = self.db.update_product_price(barcode, new_price)

            if success:
                return (
                    f"✅ Preço do produto `{old_product['description']}` alterado com sucesso!\n\n"
                    f"Preço anterior: `R$ {old_product['price']:.2f}`\n"
                    f"Novo preço: `R$ {new_price:.2f}`"
                )
            else:
                return f"❌ Falha ao alterar o preço: {message}"

        except ValueError:
            return "❌ Preço inválido. Por favor, insira um número (ex: 25.99)."
        except Exception as e:
            self.logging.error(f"Erro ao alterar preço via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao alterar o preço."
