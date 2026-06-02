"""
Página: Ambientes
Cadastro de ambientes (URL base + variáveis de autenticação).

FUTURE (login): restringir a perfil "admin".
"""

import json

import pandas as pd
import streamlit as st

import db


def show() -> None:
    st.title("🌐 Ambientes")
    st.caption("Cadastre as URLs base e as variáveis de autenticação de cada ambiente.")

    view = st.session_state.get("_amb_view", "list")

    if view == "list":
        _lista()
    else:
        _formulario()


# ─── Lista ─────────────────────────────────────────────────────────────────────

def _lista() -> None:
    ambientes = db.listar_ambientes()

    col_titulo, col_btn = st.columns([5, 1])
    with col_titulo:
        st.subheader("Ambientes cadastrados")
    with col_btn:
        if st.button("➕ Novo", use_container_width=True, type="primary"):
            _ir_form(None)

    if not ambientes:
        st.info("Nenhum ambiente cadastrado ainda. Clique em **➕ Novo** para começar.")
        return

    for amb in ambientes:
        auth = json.loads(amb["auth_vars"] or "{}")
        vars_preview = " • ".join(f"`{k}`" for k in auth)

        with st.expander(f"**{amb['nome']}** — {amb['base_url']}"):
            st.caption(f"Variáveis de auth: {vars_preview or '—'}")

            col_ed, col_del = st.columns([1, 1])
            with col_ed:
                if st.button("✏️ Editar", key=f"ed_amb_{amb['id']}", use_container_width=True):
                    _ir_form(amb["id"])
            with col_del:
                if st.button("🗑️ Excluir", key=f"del_amb_{amb['id']}", use_container_width=True):
                    db.excluir_ambiente(amb["id"])
                    st.success("Ambiente excluído.")
                    st.rerun()


# ─── Formulário ────────────────────────────────────────────────────────────────

def _formulario() -> None:
    edit_id = st.session_state.get("_amb_edit_id")
    titulo  = "Editar ambiente" if edit_id else "Novo ambiente"

    st.subheader(titulo)

    # Carrega dados existentes (edição)
    amb = db.buscar_ambiente(edit_id) if edit_id else None

    nome    = st.text_input("Nome *", value=amb["nome"]    if amb else "")
    base_url = st.text_input("Base URL *", value=amb["base_url"] if amb else "",
                             placeholder="https://api.exemplo.com")

    # Variáveis de autenticação — tabela editável
    st.markdown("**Variáveis de autenticação**")
    st.caption(
        "Defina as variáveis que serão referenciadas pelos campos de autenticação dos endpoints. "
        "Ex.: Username, Password, EnvironmentName."
    )

    auth_atual: dict = json.loads(amb["auth_vars"] if amb else "{}")
    df_auth = pd.DataFrame(
        [{"Variável": k, "Valor": v} for k, v in auth_atual.items()]
        or [{"Variável": "", "Valor": ""}]
    )
    df_editado = st.data_editor(
        df_auth,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="_amb_auth_editor",
    )

    st.markdown("---")
    col_salvar, col_cancelar = st.columns([1, 1])

    with col_salvar:
        if st.button("💾 Salvar", type="primary", use_container_width=True):
            if not nome.strip() or not base_url.strip():
                st.error("❌ Nome e Base URL são obrigatórios.")
            else:
                # Converte tabela para dict filtrando linhas vazias
                auth_vars = {
                    str(row["Variável"]).strip(): str(row["Valor"]).strip()
                    for _, row in df_editado.iterrows()
                    if str(row["Variável"]).strip()
                }
                db.salvar_ambiente(nome.strip(), base_url.strip(), auth_vars, edit_id)
                st.success("✅ Ambiente salvo!")
                _ir_lista()

    with col_cancelar:
        if st.button("Cancelar", use_container_width=True):
            _ir_lista()


# ─── Navegação interna ─────────────────────────────────────────────────────────

def _ir_form(id_: int | None) -> None:
    st.session_state["_amb_view"]    = "form"
    st.session_state["_amb_edit_id"] = id_
    # Limpa o editor de auth para não herdar dados de outra edição
    for key in list(st.session_state.keys()):
        if key == "_amb_auth_editor":
            del st.session_state[key]
    st.rerun()


def _ir_lista() -> None:
    st.session_state["_amb_view"]    = "list"
    st.session_state["_amb_edit_id"] = None
    st.rerun()
