# integrations/commands/estoque_commands.py
from .base_command import BaseCommand
from typing import List
import stock_manager

class EstoqueCommand(BaseCommand):
    """Lida com subcomandos relacionados ao estoque."""
    def execute(self) -> str:
        if not self.args:
            return "Uso: /estoque [grupos|criar_grupo|ver|add|baixa|ajustar|baixo]"

        subcommand = self.args[0].lower()
        command_args = self.args[1:]

        if subcommand == 'grupos':
            return self._handle_estoque_grupos()
        elif subcommand == 'criar_grupo':
            return self._handle_estoque_criar_grupo(command_args)
        elif subcommand == 'ver':
            return self._handle_estoque_ver()
        elif subcommand == 'add':
            return self._handle_estoque_add(command_args)
        elif subcommand == 'baixa':
            return self._handle_estoque_baixa(command_args)
        elif subcommand == 'ajustar':
            return self._handle_estoque_ajustar(command_args)
        elif subcommand == 'baixo':
            return self._handle_estoque_baixo()
        else:
            return f"Subcomando '/estoque {subcommand}' não reconhecido. Use '/ajuda' para ver as opções."

    def _handle_estoque_grupos(self) -> str:
        """Lista os grupos de estoque."""
        try:
            grupos = stock_manager.get_all_stock_groups()
            if not grupos:
                return "Nenhum grupo de estoque encontrado."

            response = "📂 *Grupos de Estoque:*\n"
            for grupo in grupos:
                response += f"- {grupo['nome']}\n"
            return response
        except Exception as e:
            self.logging.error(f"Erro ao listar grupos de estoque: {e}", exc_info=True)
            return "❌ Erro ao buscar grupos de estoque."

    def _handle_estoque_criar_grupo(self, args: List[str]) -> str:
        """Cria um novo grupo de estoque."""
        try:
            if not args:
                return "Uso: /estoque criar_grupo <nome_do_grupo>"

            group_name = " ".join(args).strip()

            if not group_name:
                return "❌ Nome do grupo não pode estar vazio."

            if len(group_name) > 100:
                return "❌ Nome do grupo muito longo (máximo 100 caracteres)."

            success, message = stock_manager.add_stock_group(group_name)

            if success:
                return f"✅ Grupo de estoque '{group_name}' criado com sucesso!"
            else:
                return f"❌ Falha ao criar grupo: {message}"

        except Exception as e:
            self.logging.error(f"Erro ao criar grupo de estoque: {e}", exc_info=True)
            return "❌ Erro interno ao criar grupo de estoque."

    def _handle_estoque_ver(self) -> str:
        """Lista todos os itens de estoque, agrupados."""
        try:
            itens = self.db.get_stock_report()['stock_levels']
            if not itens:
                return "Nenhum item no estoque."

            response = "📦 *Itens em Estoque:*\n"
            current_group = None
            for item in itens:
                if item['group_name'] != current_group:
                    current_group = item['group_name']
                    response += f"\n--- *{current_group}* ---\n"
                response += f"({item['codigo']}) {item['nome']}: {item['estoque_atual']} {item['unidade_medida']}\n"
            return response
        except Exception as e:
            self.logging.error(f"Erro ao visualizar estoque: {e}", exc_info=True)
            return "❌ Erro ao buscar itens do estoque."

    def _handle_estoque_add(self, args: List[str]) -> str:
        """Adiciona um ou mais itens ao estoque."""
        try:
            if not args:
                return ('Uso: /estoque add <codigo> "<Nome>" <Grupo> <Qtd> <Unidade>\n\n'
                       'Para adicionar múltiplos produtos, separe-os com ponto e vírgula:\n'
                       '/estoque add GR01 "Granola 500g" Insumos 10 pct ; CP01 "Coco Ralado" Insumos 5 kg')

            # Verifica se há múltiplos produtos (separados por ;)
            args_str = " ".join(args)
            if ";" in args_str:
                # Múltiplos produtos
                return self._handle_estoque_add_multiple(args_str)
            else:
                # Produto único (comportamento original)
                return self._handle_estoque_add_single(args)

        except Exception as e:
            self.logging.error(f"Erro ao adicionar item ao estoque: {e}", exc_info=True)
            return "❌ Erro interno ao adicionar item."

    def _handle_estoque_add_single(self, args: List[str]) -> str:
        """Adiciona um único item ao estoque (método original)."""
        try:
            if len(args) < 4: # Ex: codigo "nome" grupo qtd -> mínimo 4 args
                return 'Uso: /estoque add <codigo> "<Nome>" <Grupo> <Qtd> <Unidade>'

            codigo = args[0]

            # Lógica para extrair o nome do produto que pode conter espaços e estar entre aspas
            args_rest = args[1:]
            nome_parts = []
            in_name = False
            end_name_index = -1

            for i, part in enumerate(args_rest):
                if part.startswith('"') and not in_name:
                    in_name = True
                    # Caso o nome esteja contido em uma única parte (ex: "Nome")
                    if part.endswith('"') and len(part) > 1:
                        nome_parts.append(part[1:-1])
                        end_name_index = i
                        break
                    nome_parts.append(part[1:])
                elif in_name:
                    if part.endswith('"'):
                        nome_parts.append(part[:-1])
                        end_name_index = i
                        break
                    else:
                        nome_parts.append(part)

            if not in_name or end_name_index == -1:
                return 'Uso inválido. O nome do produto deve estar entre aspas. Exemplo: /estoque add GR01 "Granola 500g" Insumos 10 pct'

            nome = " ".join(nome_parts)
            remaining_args = args_rest[end_name_index + 1:]

            if len(remaining_args) < 2: # Ex: grupo qtd -> mínimo 2 args
                return 'Uso: /estoque add <codigo> "<Nome>" <Grupo> <Qtd> <Unidade>'

            grupo_nome = remaining_args[0]
            qtd_inicial = int(remaining_args[1])
            unidade = " ".join(remaining_args[2:]) if len(remaining_args) > 2 else 'un'

            grupos = stock_manager.get_all_stock_groups()
            grupo_id = next((g['id'] for g in grupos if g['nome'].lower() == grupo_nome.lower()), None)
            if not grupo_id:
                return f"❌ Grupo '{grupo_nome}' não encontrado."

            success, message = stock_manager.add_stock_item(
                codigo, nome, grupo_id, qtd_inicial, 0, unidade
            )

            if success:
                return f"✅ Item '{nome}' adicionado ao estoque com {qtd_inicial} {unidade}."
            else:
                return f"❌ {message}"
        except (ValueError, IndexError):
            return 'Uso inválido. Exemplo: /estoque add GR01 "Granola 500g" Insumos 10 pct'
        except Exception as e:
            self.logging.error(f"Erro ao adicionar item único ao estoque: {e}", exc_info=True)
            return "❌ Erro interno ao adicionar item."

    def _handle_estoque_add_multiple(self, args_str: str) -> str:
        """Adiciona múltiplos itens ao estoque separados por ponto e vírgula."""
        try:
            # Divide os produtos por ponto e vírgula
            product_strings = [p.strip() for p in args_str.split(';') if p.strip()]

            if not product_strings:
                return "❌ Nenhum produto válido encontrado."

            if len(product_strings) > 10:
                return "❌ Máximo de 10 produtos por vez. Divida em mensagens menores."

            # Carrega os grupos uma vez para todos os produtos
            grupos = stock_manager.get_all_stock_groups()
            grupo_dict = {g['nome'].lower(): g['id'] for g in grupos}

            responses = []
            success_count = 0
            error_count = 0

            for i, product_str in enumerate(product_strings, 1):
                try:
                    # Converte a string do produto em lista de argumentos
                    # Trata aspas duplas corretamente
                    product_args = self._parse_product_args(product_str)

                    if len(product_args) < 4:
                        responses.append(f"❌ Produto {i}: parâmetros insuficientes")
                        error_count += 1
                        continue

                    codigo = product_args[0]

                    # Extrai nome entre aspas
                    nome = self._extract_name_from_args(product_args[1:])
                    if not nome:
                        responses.append(f"❌ Produto {i}: nome deve estar entre aspas")
                        error_count += 1
                        continue

                    # Remove o nome dos argumentos restantes
                    remaining_args = product_args[len(nome.split()) + 1:]
                    if len(remaining_args) < 2:
                        responses.append(f"❌ Produto {i}: faltam grupo, quantidade ou unidade")
                        error_count += 1
                        continue

                    grupo_nome = remaining_args[0]
                    grupo_id = grupo_dict.get(grupo_nome.lower())
                    if not grupo_id:
                        responses.append(f"❌ Produto {i}: grupo '{grupo_nome}' não encontrado")
                        error_count += 1
                        continue

                    qtd_inicial = int(remaining_args[1])
                    unidade = " ".join(remaining_args[2:]) if len(remaining_args) > 2 else 'un'

                    success, message = stock_manager.add_stock_item(
                        codigo, nome, grupo_id, qtd_inicial, 0, unidade
                    )

                    if success:
                        responses.append(f"✅ {codigo}: '{nome}' (+{qtd_inicial} {unidade})")
                        success_count += 1
                    else:
                        responses.append(f"❌ {codigo}: {message}")
                        error_count += 1

                except (ValueError, IndexError) as e:
                    responses.append(f"❌ Produto {i}: formato inválido - {str(e)}")
                    error_count += 1
                except Exception as e:
                    responses.append(f"❌ Produto {i}: erro interno - {str(e)}")
                    error_count += 1

            # Resumo final
            summary = f"\n📊 *Resumo:* {success_count} adicionados, {error_count} erros"
            responses.append(summary)

            return "\n".join(responses)

        except Exception as e:
            self.logging.error(f"Erro ao adicionar múltiplos itens ao estoque: {e}", exc_info=True)
            return "❌ Erro interno ao processar múltiplos itens."

    def _parse_product_args(self, product_str: str) -> List[str]:
        """Converte uma string de produto em lista de argumentos, tratando aspas corretamente."""
        args = []
        current_arg = ""
        in_quotes = False

        for char in product_str:
            if char == '"' and not in_quotes:
                in_quotes = True
                current_arg += char
            elif char == '"' and in_quotes:
                in_quotes = False
                current_arg += char
            elif char == ' ' and not in_quotes:
                if current_arg:
                    args.append(current_arg)
                    current_arg = ""
            else:
                current_arg += char

        if current_arg:
            args.append(current_arg)

        return args

    def _extract_name_from_args(self, args: List[str]) -> str:
        """Extrai o nome do produto que está entre aspas."""
        if not args or not args[0].startswith('"'):
            return None

        nome_parts = []
        for i, part in enumerate(args):
            if part.startswith('"'):
                if part.endswith('"') and len(part) > 2:
                    # Nome completo em uma parte
                    return part[1:-1]
                else:
                    nome_parts.append(part[1:])
            elif part.endswith('"'):
                nome_parts.append(part[:-1])
                break
            else:
                nome_parts.append(part)

        return " ".join(nome_parts) if nome_parts else None

    def _handle_estoque_baixa(self, args: List[str]) -> str:
        """Dá baixa em um ou mais itens do estoque."""
        if not args:
            return "Uso: /estoque baixa <codigo1> <qtd1>, <codigo2> <qtd2>, ..."
        
        try:
            items_str = " ".join(args)
            items_to_decrease = [item.strip().split() for item in items_str.split(',')]
            
            responses = []
            for item_code, quantity_str in items_to_decrease:
                quantity = int(quantity_str)
                success, message = stock_manager.give_stock_out(item_code, quantity)
                if success:
                    responses.append(f"✅ Baixa de {quantity} em '{item_code}' realizada.")
                else:
                    responses.append(f"❌ Falha na baixa de '{item_code}': {message}")
            
            return "\n".join(responses)
        except (ValueError, IndexError):
            return "Formato inválido. Exemplo: /estoque baixa GR01 1, CP300 50"
        except Exception as e:
            self.logging.error(f"Erro ao dar baixa no estoque: {e}", exc_info=True)
            return "❌ Erro interno ao processar baixa de estoque."

    def _handle_estoque_ajustar(self, args: List[str]) -> str:
        """Ajusta o estoque de um produto."""
        try:
            if len(args) != 2:
                return "Uso: /estoque ajustar <código_item> <nova_quantidade>"

            item_code = args[0]
            new_stock = int(args[1])

            success, message = stock_manager.adjust_stock_quantity(item_code, new_stock)

            if success:
                return f"✅ Estoque do item '{item_code}' ajustado para {new_stock}."
            else:
                return f"❌ {message}"

        except ValueError:
            return "❌ Quantidade inválida. Por favor, insira um número inteiro."
        except Exception as e:
            self.logging.error(f"Erro ao ajustar estoque via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao ajustar o estoque."

    def _handle_estoque_baixo(self) -> str:
        """Retorna uma lista de produtos com estoque baixo."""
        try:
            report = self.db.get_stock_report()
            low_stock_items = report.get('low_stock_items', [])

            if not low_stock_items:
                return "✅ Nenhum produto com estoque baixo encontrado."

            response = "📉 *Produtos com Estoque Baixo*\n\n"
            for item in low_stock_items:
                stock_str = f"{item['stock']:.3f}".replace('.', ',')
                response += f"- `{item['description']}`: `{stock_str}`\n"
            
            return response

        except Exception as e:
            self.logging.error(f"Erro ao buscar produtos com estoque baixo via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao buscar o relatório de estoque."
