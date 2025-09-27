#!/usr/bin/env python3
"""
Script de demonstração do Sistema PDV Açaí
Mostra as principais funcionalidades implementadas na FASE 0
"""

import database as db
from datetime import datetime

def demonstrar_sistema():
    print("=" * 60)
    print("DEMONSTRAÇÃO - SISTEMA PDV AÇAÍ - FASE 0 COMPLETA")
    print("=" * 60)
    
    # 1. Sistema de Usuários
    print("\n1. SISTEMA DE USUÁRIOS")
    print("-" * 30)
    
    # Listar usuários existentes
    users = db.get_all_users()
    print(f"Usuários cadastrados: {len(users)}")
    for user in users:
        print(f"  - {user['username']} ({user['role']}) - Ativo: {bool(user['active'])}")
    
    # Criar um operador de exemplo
    operador_id = db.create_user("operador1", "123456", "operador")
    if operador_id:
        print(f"✓ Operador criado com ID: {operador_id}")
    
    # Testar autenticação
    admin_auth = db.authenticate_user("admin", "admin123")
    if admin_auth:
        print(f"✓ Autenticação admin bem-sucedida: {admin_auth['username']}")
    
    # 2. Sistema de Controle de Caixa
    print("\n2. SISTEMA DE CONTROLE DE CAIXA")
    print("-" * 30)
    
    # Abrir caixa
    session_id, message = db.open_cash_session(admin_auth['id'], 100.00)
    if session_id:
        print(f"✓ Caixa aberto - Sessão ID: {session_id}")
        print(f"  Valor inicial: R$ 100,00")
        
        # Adicionar movimentações
        suprimento_id = db.add_cash_movement(session_id, admin_auth['id'], 'suprimento', 50.00, 'Reforço de troco')
        print(f"✓ Suprimento registrado - ID: {suprimento_id}")
        
        sangria_id = db.add_cash_movement(session_id, admin_auth['id'], 'sangria', 200.00, 'Pagamento fornecedor')
        print(f"✓ Sangria registrada - ID: {sangria_id}")
        
        # Verificar sessão atual
        current_session = db.get_current_cash_session()
        if current_session:
            print(f"✓ Sessão atual: ID {current_session['id']} - Usuário: {current_session['username']}")
    
    # 3. Sistema de Backup
    print("\n3. SISTEMA DE BACKUP")
    print("-" * 30)
    
    success, backup_file = db.create_backup()
    if success:
        print(f"✓ Backup criado: {backup_file}")
    
    # Listar backups
    backups = db.list_backups()
    print(f"✓ Total de backups disponíveis: {len(backups)}")
    for backup in backups[:3]:  # Mostra apenas os 3 mais recentes
        print(f"  - {backup['filename']} ({backup['size']} bytes)")
    
    # 4. Sistema de Auditoria
    print("\n4. SISTEMA DE AUDITORIA")
    print("-" * 30)
    
    # Registrar algumas ações de auditoria
    db.log_audit(admin_auth['id'], 'DEMO_ACTION', 'demo_table', 1, 'old_value', 'new_value')
    
    # Buscar logs de auditoria
    audit_logs = db.get_audit_log(limit=5)
    print(f"✓ Logs de auditoria encontrados: {len(audit_logs)}")
    for log in audit_logs:
        timestamp = log['timestamp']
        username = log['username'] or 'Sistema'
        print(f"  - {timestamp}: {username} - {log['action']} em {log['table_name']}")
    
    # 5. Funcionalidades de Produtos (existentes)
    print("\n5. SISTEMA DE PRODUTOS (EXISTENTE)")
    print("-" * 30)
    
    # Adicionar grupo de exemplo
    try:
        group_id = db.add_group("Açaí")
        print(f"✓ Grupo 'Açaí' criado com ID: {group_id}")
    except:
        print("ℹ Grupo 'Açaí' já existe")
    
    # Adicionar produto de exemplo
    try:
        db.add_product("Açaí 300ml", "acai300", 8.50, 100, "weight", 1)
        print("✓ Produto 'Açaí 300ml' adicionado")
    except:
        print("ℹ Produto 'Açaí 300ml' já existe")
    
    # Listar produtos
    products = db.get_all_products()
    print(f"✓ Total de produtos cadastrados: {len(products)}")
    
    # 6. Resumo das Funcionalidades
    print("\n6. RESUMO DAS FUNCIONALIDADES IMPLEMENTADAS")
    print("-" * 50)
    print("✓ Sistema de login com autenticação")
    print("✓ Controle de usuários (operador/gerente)")
    print("✓ Controle de sessões de caixa")
    print("✓ Movimentações de caixa (suprimento/sangria)")
    print("✓ Sistema de backup automático")
    print("✓ Log de auditoria completo")
    print("✓ Interface com controle de permissões")
    print("✓ Barra de status com informações em tempo real")
    print("✓ Menu contextual baseado no tipo de usuário")
    print("✓ Modo treinamento (para gerentes)")
    
    print("\n" + "=" * 60)
    print("FASE 0 - FUNDAÇÃO DO SISTEMA: COMPLETA! ✓")
    print("=" * 60)
    
    print("\nPRÓXIMAS FASES:")
    print("- FASE 1: Dashboard Gerencial com KPIs em tempo real")
    print("- FASE 2: Fluxo de venda otimizado com balança Prix 3 Fit")
    print("- FASE 3: Controle de caixa profissional com fechamento cego")
    
    print(f"\nCredenciais de acesso:")
    print(f"Usuário: admin | Senha: admin123 (Gerente)")
    print(f"Usuário: operador1 | Senha: 123456 (Operador)")

if __name__ == "__main__":
    demonstrar_sistema()
