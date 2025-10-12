from .connection import get_db_connection

def log_audit(user_id, action, table_name, record_id, old_values=None, new_values=None):
    """Registra ação na auditoria."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO audit_log (user_id, action, table_name, record_id, old_values, new_values)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, action, table_name, record_id, old_values, new_values))
    
    conn.commit()
    conn.close()

def get_audit_log(limit=100, user_id=None, action=None):
    """Retorna log de auditoria."""
    conn = get_db_connection()
    
    query = '''
        SELECT al.*, u.username 
        FROM audit_log al
        LEFT JOIN users u ON al.user_id = u.id
        WHERE 1=1
    '''
    params = []
    
    if user_id:
        query += ' AND al.user_id = ?'
        params.append(user_id)
    
    if action:
        query += ' AND al.action = ?'
        params.append(action)
    
    query += ' ORDER BY al.timestamp DESC LIMIT ?'
    params.append(limit)
    
    logs = conn.execute(query, params).fetchall()
    conn.close()
    
    return [dict(log) for log in logs]
