"""
Tela de login — email + CPF.
Não exige senha: o CPF funciona como credencial de acesso.
"""

import streamlit as st
import db


def show() -> None:
    # Centraliza o formulário na página
    _, col, _ = st.columns([1, 2, 1])

    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("## 🏢 MXM Integrador")
        st.markdown("Faça login para continuar. (Atualizado: 2026-08-06 10:40)")
        st.markdown("---")

        with st.form("form_login"):
            email = st.text_input("E-mail", placeholder="seu@email.com")
            cpf   = st.text_input("CPF", placeholder="000.000.000-00",
                                  help="Digite apenas os números ou no formato 000.000.000-00")
            submitted = st.form_submit_button("Entrar", use_container_width=True, type="primary")

        if submitted:
            if not email.strip() or not cpf.strip():
                st.error("Preencha e-mail e CPF.")
                return

            usuario = db.autenticar(email.strip(), cpf.strip())
            if usuario:
                st.session_state["_user"] = {
                    "id":     usuario["id"],
                    "nome":   usuario["nome"],
                    "email":  usuario["email"],
                    "perfil": usuario["perfil"],
                }
                st.rerun()
            else:
                st.error("❌ E-mail ou CPF inválidos.")
