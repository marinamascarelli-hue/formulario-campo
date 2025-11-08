import streamlit as st
import pandas as pd
import os
from pathlib import Path
from datetime import datetime
import shutil
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
import json
import google.auth.exceptions

# ---------------- CONFIGURAÇÕES INICIAIS ----------------
st.set_page_config(page_title="Formulário de Campo", page_icon="🌿", layout="wide")
st.title("📋 Formulário de Campo")

# Caminho da planilha principal
CAMINHO_PLANILHA = Path("dados_campo.xlsx")

# Cria planilha se não existir
if not CAMINHO_PLANILHA.exists():
    df_vazio = pd.DataFrame(columns=[
        "Data", "Nome", "Endereço", "Telefone", "Email",
        "Descrição", "Fotos", "Observações"
    ])
    df_vazio.to_excel(CAMINHO_PLANILHA, index=False)

# ---------------- FORMULÁRIO ----------------
with st.form("formulario_campo"):
    st.subheader("Informações do Atendimento")

    data = st.date_input("Data do Atendimento", datetime.today())
    nome = st.text_input("Nome Completo")
    endereco = st.text_input("Endereço")
    telefone = st.text_input("Telefone")
    email = st.text_input("E-mail")
    descricao = st.text_area("Descrição do Atendimento")
    observacoes = st.text_area("Observações Adicionais")

    fotos = st.file_uploader(
        "📸 Envie fotos relacionadas (opcional)",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True
    )

    enviado = st.form_submit_button("Salvar Dados")

# ---------------- PROCESSAMENTO ----------------
if enviado:
    if not nome:
        st.error("⚠️ O campo 'Nome Completo' é obrigatório.")
    else:
        st.success("✅ Dados salvos com sucesso!")

        # Cria pasta para o atendimento
        pasta_atendimento = Path("atendimentos") / f"{nome}_{data.strftime('%Y%m%d')}"
        pasta_atendimento.mkdir(parents=True, exist_ok=True)

        # Salva fotos
        caminhos_fotos = []
        for foto in fotos:
            caminho_foto = pasta_atendimento / foto.name
            with open(caminho_foto, "wb") as f:
                f.write(foto.getbuffer())
            caminhos_fotos.append(str(caminho_foto))

        # Atualiza planilha de dados
        df = pd.read_excel(CAMINHO_PLANILHA)
        novo_registro = pd.DataFrame([{
            "Data": data,
            "Nome": nome,
            "Endereço": endereco,
            "Telefone": telefone,
            "Email": email,
            "Descrição": descricao,
            "Fotos": "; ".join(caminhos_fotos) if caminhos_fotos else "",
            "Observações": observacoes
        }])
        df_final = pd.concat([df, novo_registro], ignore_index=True)
        df_final.to_excel(CAMINHO_PLANILHA, index=False)

        st.info("☁️ Iniciando upload para o Google Drive...")

        # ---------------- GOOGLE DRIVE UPLOAD (SEGURO E COMPATÍVEL) ----------------
        SCOPES = ["https://www.googleapis.com/auth/drive.file"]

        try:
            # 1️⃣ Lê o conteúdo das credenciais diretamente do painel de segredos do Streamlit
            creds_json = st.secrets["oauth_credentials"]["client_json"]
            creds_info = json.loads(creds_json)

            # 2️⃣ Cria o fluxo OAuth com base nas credenciais seguras
            flow = InstalledAppFlow.from_client_config(creds_info, SCOPES)
            creds = flow.run_local_server(port=0)

            # 3️⃣ Cria o serviço de conexão com o Google Drive
            service = build("drive", "v3", credentials=creds)

            # 4️⃣ ID da pasta de destino no seu Google Drive
            PASTA_ID_DESTINO = "13xQ1pcEjGDWQaj1vqgtkuHxsm8ojJkL7"

            # ---------------- Upload da planilha ----------------
            try:
                file_metadata = {"name": "dados_campo.xlsx", "parents": [PASTA_ID_DESTINO]}
                media = MediaFileUpload(
                    str(CAMINHO_PLANILHA),
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields="id"
                ).execute()
            except Exception as e:
                st.error(f"❌ Erro ao enviar planilha: {e}")

            # ---------------- Upload das fotos ----------------
            try:
                for root, _, files in os.walk(pasta_atendimento):
                    for file in files:
                        caminho = Path(root) / file
                        file_metadata = {"name": file, "parents": [PASTA_ID_DESTINO]}
                        media = MediaFileUpload(str(caminho), mimetype="image/jpeg")
                        service.files().create(
                            body=file_metadata,
                            media_body=media,
                            fields="id"
                        ).execute()
            except Exception as e:
                st.error(f"❌ Erro ao enviar fotos: {e}")

            st.success("✅ Dados e fotos enviados com sucesso para o Google Drive!")
            st.balloons()

        except KeyError:
            st.error("⚠️ Credenciais OAuth não encontradas em `st.secrets`. Vá em 'Edit secrets' no Streamlit Cloud e adicione suas credenciais.")
        except google.auth.exceptions.RefreshError:
            st.error("⚠️ Erro de autenticação no Google. Tente novamente ou gere novas credenciais OAuth.")
        except Exception as e:
            st.error(f"❌ Ocorreu um erro inesperado: {e}")
