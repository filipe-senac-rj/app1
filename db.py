"""
Camada de acesso ao banco de dados (SQLite).

Tabelas:
  usuarios       — usuários do sistema (perfis: admin | operador)
  ambientes      — URL base + variáveis de autenticação por ambiente
  endpoints      — configuração de cada endpoint da API
  lotes          — cada envio de planilha = um lote
  lote_registros — resultado por registro dentro do lote
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(ROOT_DIR, "data", "app.db")

# ─── Admin padrão ──────────────────────────────────────────────────────────────
_ADMIN_NOME  = "Administrador TI"
_ADMIN_EMAIL = "admin@rj.senac.br"
_ADMIN_CPF   = "00000000021"
_ADMIN_PERFIL = "admin"


# ─── Conexão ───────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                nome      TEXT NOT NULL,
                email     TEXT NOT NULL UNIQUE,
                cpf_hash  TEXT NOT NULL,
                perfil    TEXT NOT NULL DEFAULT 'operador'
            );

            CREATE TABLE IF NOT EXISTS ambientes (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                nome      TEXT NOT NULL,
                base_url  TEXT NOT NULL,
                auth_vars TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS endpoints (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                nome   TEXT NOT NULL,
                metodo TEXT NOT NULL DEFAULT 'POST',
                path   TEXT NOT NULL,
                campos TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS lotes (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint_id  INTEGER NOT NULL,
                ambiente_id  INTEGER NOT NULL,
                usuario_id   INTEGER,
                nome_arquivo TEXT,
                data_envio   TEXT,
                total        INTEGER DEFAULT 0,
                sucesso      INTEGER DEFAULT 0,
                erro         INTEGER DEFAULT 0,
                FOREIGN KEY (endpoint_id) REFERENCES endpoints(id),
                FOREIGN KEY (ambiente_id) REFERENCES ambientes(id),
                FOREIGN KEY (usuario_id)  REFERENCES usuarios(id)
            );

            CREATE TABLE IF NOT EXISTS lote_registros (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                lote_id       INTEGER NOT NULL,
                identificador TEXT,
                sucesso       INTEGER DEFAULT 0,
                mensagem      TEXT,
                FOREIGN KEY (lote_id) REFERENCES lotes(id)
            );
        """)

        _migrar(conn)
        _criar_admin_padrao(conn)


def _migrar(conn: sqlite3.Connection) -> None:
    """Adiciona colunas ausentes sem apagar dados existentes."""
    colunas_lotes = {r["name"] for r in conn.execute("PRAGMA table_info(lotes)")}
    for col, ddl in [
        ("ambiente_id", "INTEGER DEFAULT 0"),
        ("endpoint_id", "INTEGER DEFAULT 0"),
        ("usuario_id",  "INTEGER"),
    ]:
        if col not in colunas_lotes:
            conn.execute(f"ALTER TABLE lotes ADD COLUMN {col} {ddl}")

    colunas_reg = {r["name"] for r in conn.execute("PRAGMA table_info(lote_registros)")}
    for col, ddl in [
        ("identificador", "TEXT"),
        ("sucesso",        "INTEGER DEFAULT 0"),
        ("mensagem",       "TEXT"),
    ]:
        if col not in colunas_reg:
            conn.execute(f"ALTER TABLE lote_registros ADD COLUMN {col} {ddl}")


def _criar_admin_padrao(conn: sqlite3.Connection) -> None:
    """Garante que o admin padrão existe (INSERT OR IGNORE)."""
    conn.execute(
        "INSERT OR IGNORE INTO usuarios (nome, email, cpf_hash, perfil) VALUES (?,?,?,?)",
        (_ADMIN_NOME, _ADMIN_EMAIL, _hash_cpf(_ADMIN_CPF), _ADMIN_PERFIL),
    )


# ─── Utilitário interno ────────────────────────────────────────────────────────

def _hash_cpf(cpf: str) -> str:
    """Remove caracteres não numéricos e retorna SHA-256 do CPF."""
    cpf_limpo = "".join(c for c in cpf if c.isdigit())
    return hashlib.sha256(cpf_limpo.encode()).hexdigest()


def _limpar_cpf(cpf: str) -> str:
    return "".join(c for c in cpf if c.isdigit())


# ─── Usuários ──────────────────────────────────────────────────────────────────

def autenticar(email: str, cpf: str):
    """Retorna o usuário se email + CPF forem válidos, None caso contrário."""
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM usuarios WHERE email = ? AND cpf_hash = ?",
            (email.strip().lower(), _hash_cpf(cpf)),
        ).fetchone()


def listar_usuarios() -> list:
    with get_db() as conn:
        return conn.execute(
            "SELECT id, nome, email, perfil FROM usuarios ORDER BY nome"
        ).fetchall()


def buscar_usuario(id_: int):
    with get_db() as conn:
        return conn.execute(
            "SELECT id, nome, email, perfil FROM usuarios WHERE id = ?", (id_,)
        ).fetchone()


def salvar_usuario(nome: str, email: str, cpf: str, perfil: str,
                   id_: int | None = None) -> None:
    cpf_limpo = _limpar_cpf(cpf)
    if len(cpf_limpo) != 11:
        raise ValueError("CPF deve ter 11 dígitos.")

    with get_db() as conn:
        if id_:
            # Edição: atualiza tudo menos o CPF se for vazio
            if cpf_limpo:
                conn.execute(
                    "UPDATE usuarios SET nome=?, email=?, cpf_hash=?, perfil=? WHERE id=?",
                    (nome, email.strip().lower(), _hash_cpf(cpf_limpo), perfil, id_),
                )
            else:
                conn.execute(
                    "UPDATE usuarios SET nome=?, email=?, perfil=? WHERE id=?",
                    (nome, email.strip().lower(), perfil, id_),
                )
        else:
            conn.execute(
                "INSERT INTO usuarios (nome, email, cpf_hash, perfil) VALUES (?,?,?,?)",
                (nome, email.strip().lower(), _hash_cpf(cpf_limpo), perfil),
            )


def excluir_usuario(id_: int) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM usuarios WHERE id = ?", (id_,))


# ─── Ambientes ─────────────────────────────────────────────────────────────────

def listar_ambientes() -> list:
    with get_db() as conn:
        return conn.execute("SELECT * FROM ambientes ORDER BY nome").fetchall()


def buscar_ambiente(id_: int):
    with get_db() as conn:
        return conn.execute("SELECT * FROM ambientes WHERE id = ?", (id_,)).fetchone()


def salvar_ambiente(nome: str, base_url: str, auth_vars: dict,
                    id_: int | None = None) -> None:
    auth_json = json.dumps(auth_vars, ensure_ascii=False)
    with get_db() as conn:
        if id_:
            conn.execute(
                "UPDATE ambientes SET nome=?, base_url=?, auth_vars=? WHERE id=?",
                (nome, base_url, auth_json, id_),
            )
        else:
            conn.execute(
                "INSERT INTO ambientes (nome, base_url, auth_vars) VALUES (?,?,?)",
                (nome, base_url, auth_json),
            )


def excluir_ambiente(id_: int) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM ambientes WHERE id = ?", (id_,))


# ─── Endpoints ─────────────────────────────────────────────────────────────────

def listar_endpoints() -> list:
    with get_db() as conn:
        return conn.execute("SELECT * FROM endpoints ORDER BY nome").fetchall()


def buscar_endpoint(id_: int):
    with get_db() as conn:
        return conn.execute("SELECT * FROM endpoints WHERE id = ?", (id_,)).fetchone()


def salvar_endpoint(nome: str, metodo: str, path: str, campos: list,
                    id_: int | None = None) -> None:
    campos_json = json.dumps(campos, ensure_ascii=False)
    with get_db() as conn:
        if id_:
            conn.execute(
                "UPDATE endpoints SET nome=?, metodo=?, path=?, campos=? WHERE id=?",
                (nome, metodo, path, campos_json, id_),
            )
        else:
            conn.execute(
                "INSERT INTO endpoints (nome, metodo, path, campos) VALUES (?,?,?,?)",
                (nome, metodo, path, campos_json),
            )


def excluir_endpoint(id_: int) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM endpoints WHERE id = ?", (id_,))


# ─── Lotes ─────────────────────────────────────────────────────────────────────

def salvar_lote(endpoint_id: int, ambiente_id: int, nome_arquivo: str,
                resultados: list[dict], usuario_id: int | None = None) -> int:
    n_ok  = sum(1 for r in resultados if r["sucesso"])
    n_err = len(resultados) - n_ok
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO lotes
                   (endpoint_id, ambiente_id, usuario_id, nome_arquivo, data_envio, total, sucesso, erro)
               VALUES (?,?,?,?,?,?,?,?)""",
            (endpoint_id, ambiente_id, usuario_id, nome_arquivo,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             len(resultados), n_ok, n_err),
        )
        lote_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO lote_registros (lote_id, identificador, sucesso, mensagem) VALUES (?,?,?,?)",
            [(lote_id, r["identificador"], 1 if r["sucesso"] else 0, r["mensagem"])
             for r in resultados],
        )
    return lote_id


def listar_lotes(endpoint_id: int | None = None) -> list:
    sql = """
        SELECT l.*,
               e.nome AS endpoint_nome,
               a.nome AS ambiente_nome,
               COALESCE(u.nome, '—') AS usuario_nome
        FROM lotes l
        JOIN endpoints e  ON l.endpoint_id = e.id
        JOIN ambientes a  ON l.ambiente_id  = a.id
        LEFT JOIN usuarios u ON l.usuario_id = u.id
        {where}
        ORDER BY l.id DESC
    """
    with get_db() as conn:
        if endpoint_id:
            return conn.execute(
                sql.format(where="WHERE l.endpoint_id = ?"), (endpoint_id,)
            ).fetchall()
        return conn.execute(sql.format(where="")).fetchall()


def buscar_registros_lote(lote_id: int) -> list:
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM lote_registros WHERE lote_id = ?", (lote_id,)
        ).fetchall()
