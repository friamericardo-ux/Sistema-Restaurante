import os
import re

def run_migrations(get_connection, is_mysql):
    conn = get_connection()
    cursor = conn.cursor()

    if is_mysql:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id INT PRIMARY KEY AUTO_INCREMENT,
                filename VARCHAR(255) UNIQUE NOT NULL,
                executado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE NOT NULL,
                executado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    conn.commit()

    cursor.execute("SELECT filename FROM schema_migrations")
    rows = cursor.fetchall()
    ja_executadas = {r[0] if isinstance(r, tuple) else r['filename'] for r in rows}

    migrations_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migrations')

    if not os.path.isdir(migrations_dir):
        conn.close()
        return

    arquivos = sorted([
        f for f in os.listdir(migrations_dir)
        if (f.endswith('.sql') or f.endswith('.py')) and re.match(r'^\d+_', f)
    ])

    for filename in arquivos:
        if filename in ja_executadas:
            continue

        filepath = os.path.join(migrations_dir, filename)
        
        try:
            if filename.endswith('.sql'):
                with open(filepath, 'r', encoding='utf-8') as f:
                    sql = f.read()
                statements = [s.strip() for s in sql.split(';') if s.strip()]
                for statement in statements:
                    try:
                        cursor.execute(statement)
                    except Exception as e:
                        msg = str(e).lower()
                        if 'duplicate column' in msg or 'already exists' in msg:
                            continue
                        raise
            elif filename.endswith('.py'):
                import importlib.util
                spec = importlib.util.spec_from_file_location("migration_module", filepath)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, 'upgrade'):
                    module.upgrade(cursor, conn)
            
            conn.commit()

            if is_mysql:
                cursor.execute("INSERT IGNORE INTO schema_migrations (filename) VALUES (%s)", (filename,))
            else:
                cursor.execute("INSERT OR IGNORE INTO schema_migrations (filename) VALUES (?)", (filename,))
            conn.commit()
            print(f"[migrations] OK {filename} executada com sucesso")
            
        except Exception as e:
            print(f"[migrations] ERRO em {filename}: {e}")
            conn.rollback()
            raise Exception(f"Erro na migration {filename}: {e}")

    conn.close()
