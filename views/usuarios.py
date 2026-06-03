"""
Página: Usuários (somente admin).
CRUD de usuários: nome, e-mail, CPF, perfil.
"""

import streamlit as st
import db

PERFIS = ["operador", "admin"]


def show() -> None:
    st.title("👥 Usuários")
    st.caption("Gerencie os usuários do sistema.")

    view = st.session_state.get("_usr_view", "list")

    if view == "list":
        _lista()
    else:
        _formulario()


# ─── Lista ─────────────────────────────────────────────────────────────────────

def _lista() -> None:
    usuarios = db.listar_usuarios()
    user_logado = st.session_state.get("_user", {})

    col_titulo, col_btn = st.columns([5, 1])
    with col_titulo:
        st.subheader("Usuários cadastrados")
    with col_btn:
        if st.button("➕ Novo", use_container_width=True, type="primary"):
            _ir_form(None)

    if not usuarios:
        st.info("Nenhum usuário encontrado.")
        return

    for u in usuarios:
        perfil_icon = "🔑" if u["perfil"] == "admin" else "👤"
        eh_voce     = u["id"] == user_logado.get("id")
        label       = f"{perfil_icon} **{u['nome']}** — {u['email']}" + (" *(você)*" if eh_voce else "")

        with st.expander(label):
            st.caption(f"Perfil: **{u['perfil'].capitalize()}**")

            col_ed, col_del = st.columns([1, 1])
            with col_ed:
                if st.button("✏️ Editar", key=f"ed_usr_{u['id']}", use_container_width=True):
                    _ir_form(u["id"])
            with col_del:
                # Impede excluir a si mesmo ou o admin padrão
                pode_excluir = not eh_voce and u["email"] != "admin@rj.senac.br"
                if st.button("🗑️ Excluir", key=f"del_usr_{u['id']}",
                             use_container_width=True, disabled=not pode_excluir):
                    db.excluir_usuario(u["id"])
                    st.success("Usuário excluído.")
                    st.rerun()
                if not pode_excluir:
                    st.caption("Não é possível excluir este usuário.")


# ─── Formulário ────────────────────────────────────────────────────────────────

def _formulario() -> None:
    edit_id = st.session_state.get("_usr_edit_id")
    titulo  = "Editar usuário" if edit_id else "Novo usuário"
    st.subheader(titulo)

    u = db.buscar_usuario(edit_id) if edit_id else None

    nome  = st.text_input("Nome *",   value=u["nome"]  if u else "")
    email = st.text_input("E-mail *", value=u["email"] if u else "",
                          placeholder="nome@dominio.com")

    if edit_id:
        st.caption("🔒 Deixe o CPF em branco para manter o atual.")
    cpf = st.text_input(
        "CPF *" if not edit_id else "CPF (novo, opcional)",
        placeholder="00000000000",
        help="Somente números. É usado como credencial de acesso.",
    )

    perfil_idx = PERFIS.index(u["perfil"]) if u and u["perfil"] in PERFIS else 0
    perfil = st.selectbox("Perfil *", PERFIS,
                          index=perfil_idx,
                          format_func=lambda p: p.capitalize())

    st.markdown("---")
    col_salvar, col_cancelar = st.columns([1, 1])

    with col_salvar:
        if st.button("💾 Salvar", type="primary", use_container_width=True):
            erros = []
            if not nome.strip():
                erros.append("Nome é obrigatório.")
            if not email.strip():
                erros.append("E-mail é obrigatório.")
            cpf_limpo = "".join(c for c in cpf if c.isdigit())
            if not edit_id and len(cpf_limpo) != 11:
                erros.append("CPF deve ter 11 dígitos.")
            if edit_id and cpf.strip() and len(cpf_limpo) != 11:
                erros.append("CPF inválido — deve ter 11 dígitos ou deixe em branco.")

            if erros:
                for e in erros:
                    st.error(f"❌ {e}")
            else:
                try:
                    # Se edição e CPF em branco, passa qualquer coisa — db.salvar_usuario ignora
                    cpf_para_salvar = cpf_limpo if cpf_limpo else ("0" * 11 if edit_id else "")
                    db.salvar_usuario(nome.strip(), email.strip(), cpf_para_salvar, perfil, edit_id)
                    st.success("✅ Usuário salvo!")
                    _ir_lista()
                except Exception as ex:
                    st.error(f"❌ {ex}")

    with col_cancelar:
        if st.button("Cancelar", use_container_width=True):
            _ir_lista()


# ─── Navegação interna ─────────────────────────────────────────────────────────

def _ir_form(id_: int | None) -> None:
    st.session_state["_usr_view"]    = "form"
    st.session_state["_usr_edit_id"] = id_
    st.rerun()


def _ir_lista() -> None:
    st.session_state["_usr_view"]    = "list"
    st.session_state["_usr_edit_id"] = None
    st.rerun()
