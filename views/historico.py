"""
Página: Histórico de Lotes
Visualização do histórico de envios por endpoint.
"""

import io

import pandas as pd
import streamlit as st

import db


def show() -> None:
    st.title("📊 Histórico de Lotes")

    endpoints = db.listar_endpoints()

    if not endpoints:
        st.info("Nenhum endpoint cadastrado ainda.")
        return

    # Filtro por endpoint
    opcoes = {"Todos os endpoints": None}
    opcoes.update({ep["nome"]: ep["id"] for ep in endpoints})

    ep_sel    = st.selectbox("Filtrar por endpoint", list(opcoes.keys()))
    ep_id_sel = opcoes[ep_sel]

    col_refresh, _ = st.columns([1, 5])
    with col_refresh:
        if st.button("🔄 Atualizar"):
            st.rerun()

    st.markdown("---")

    lotes = db.listar_lotes(ep_id_sel)

    if not lotes:
        st.info("Nenhum lote encontrado para este filtro.")
        return

    for lote in lotes:
        icone = "🟢" if lote["erro"] == 0 else ("🟡" if lote["sucesso"] > 0 else "🔴")
        taxa  = f"{lote['sucesso']}/{lote['total']} ok"

        titulo = (
            f"{icone}  Lote **#{lote['id']}** — "
            f"{lote['endpoint_nome']} · "
            f"{lote['ambiente_nome']} · "
            f"{lote['nome_arquivo']} · "
            f"{lote['data_envio']} · "
            f"por **{lote['usuario_nome']}** · "
            f"{taxa}"
        )

        with st.expander(titulo):
            registros = db.buscar_registros_lote(lote["id"])
            if not registros:
                st.info("Sem registros.")
                continue

            df = pd.DataFrame([dict(r) for r in registros])
            df["Status"] = df["sucesso"].map({1: "✅ Sucesso", 0: "❌ Erro"})
            st.dataframe(
                df[["identificador", "Status", "mensagem"]].rename(columns={
                    "identificador": "Identificador",
                    "mensagem":      "Mensagem",
                }),
                use_container_width=True,
                hide_index=True,
            )

            buf = io.BytesIO()
            df.to_excel(buf, index=False)
            buf.seek(0)
            st.download_button(
                "📥 Exportar lote",
                data=buf,
                file_name=f"lote_{lote['id']}_{lote['nome_arquivo']}",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_hist_{lote['id']}",
            )
