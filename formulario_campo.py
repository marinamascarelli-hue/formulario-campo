import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path
import os
import pytz
import json
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

# -------------------------------------------------------
# 📁 CONFIGURAÇÃO DE CAMINHOS (local e nuvem)
# -------------------------------------------------------
if os.getenv("HOME", "").startswith("/home/appuser"):
    PASTA_BASE = Path("/tmp/formulario_campo")
else:
    PASTA_BASE = Path(r"C:\Users\Marina\Desktop\Formulario de Campo")

PASTA_BASE.mkdir(exist_ok=True)
CAMINHO_PLANILHA = PASTA_BASE / "dados_campo.xlsx"
PASTA_FOTOS = PASTA_BASE / "fotos"
TOKEN_PATH = PASTA_BASE / "token_drive.pkl"

# -------------------------------------------------------
# 🧾 CONFIGURAÇÃO INICIAL DO APP
# -------------------------------------------------------
st.set_page_config(page_title="Formulário de Atendimento", page_icon="📋", layout="centered")
st.title("🧾 Formulário de Atendimento de Campo - Polícia Científica")
st.write("Preencha as informações e anexe as fotografias correspondentes ao atendimento.")

# -------------------------------------------------------
# 🕒 DATA E HORA (ajustada para horário de Brasília)
# -------------------------------------------------------
fuso_brasilia = pytz.timezone("America/Sao_Paulo")
agora_brasilia = datetime.now(fuso_brasilia)

# -------------------------------------------------------
# 🧠 CONTROLE DE SESSÃO (impede reset após login)
# -------------------------------------------------------
if "form_data" not in st.session_state:
    st.session_state["form_data"] = {
        "data": agora_brasilia.strftime("%Y-%m-%d"),
        "hora": agora_brasilia.strftime("%H:%M"),
        "latitude": "",
        "longitude": "",
        "preservacao": "",
        "vtr": "",
        "acompanhante": "",
        "fotografo": "",
        "materiais": "",
        "observacoes": ""
    }

# -------------------------------------------------------
# CAMPOS DE DATA E HORA
# -------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    data = st.date_input("📅 Data do Atendimento", datetime.strptime(st.session_state["form_data"]["data"], "%Y-%m-%d").date())
with col2:
    hora = st.time_input("🕒 Horário", datetime.strptime(st.session_state["form_data"]["hora"], "%H:%M").time())

# -------------------------------------------------------
# 📍 GEOLOCALIZAÇÃO
# -------------------------------------------------------
st.markdown("### 📍 Geolocalização do Local do Fato")
latitude = st.text_input("Latitude (use o botão abaixo para capturar automaticamente):", st.session_state["form_data"]["latitude"])
longitude = st.text_input("Longitude:", st.session_state["form_data"]["longitude"])

geo_script = """
<script>
navigator.geolocation.getCurrentPosition(
    (pos) => {
        const lat = pos.coords.latitude.toFixed(6);
        const lon = pos.coords.longitude.toFixed(6);
        const latField = window.parent.document.querySelector('input[aria-label="Latitude (use o botão abaixo para capturar automaticamente):"]');
        const lonField = window.parent.document.querySelector('input[aria-label="Longitude:"]');
        if (latField && lonField) {
            latField.value = lat;
            lonField.value = lon;
            latField.dispatchEvent(new Event('input', { bubbles: true }));
            lonField.dispatchEvent(new Event('input', { bubbles: true }));
        }
        alert("📍 Localização capturada com sucesso!");
    },
    (err) => alert("❌ Não foi possível capturar a localização. Verifique as permissões do navegador.")
);
</script>
"""
if st.button("📍 Capturar minha localização"):
    st.components.v1.html(geo_script, height=0)

# -------------------------------------------------------
# 🧩 CAMPOS DO ATENDIMENTO
# -------------------------------------------------------
preservacao = st.text_input("🔒 Preservação (situação do local)", st.session_state["form_data"]["preservacao"])
vtr = st.text_input("🚓 VTR (veículo utilizado)", st.session_state["form_data"]["vtr"])
acompanhante = st.text_input("👮 Acompanhante", st.session_state["form_data"]["acompanhante"])

fotografos = [
    "Adriano Godoi de Lara",
    "Cássio Henrique Reolon Ferreira da Silva",
    "Marcelo Barburino Valente",
    "Marcos Paulo de Souza",
    "Maria Nathalia Bortolotto Beghini",
    "Murilo Carlos de Souza",
    "Sandro Alberto Baracho"
]
fotografo = st.selectbox("📸 Fotógrafo Responsável", fotografos, 
                         index=fotografos.index(st.session_state["form_data"]["fotografo"]) 
                         if st.session_state["form_data"]["fotografo"] in fotografos else 0)

materiais = st.text_area("🧪 Materiais Coletados", st.session_state["form_data"]["materiais"])
observacoes = st.text_area("🗒️ Observações Gerais", st.session_state["form_data"]["observacoes"])

# -------------------------------------------------------
# 📷 UPLOAD DE FOTOS
# -------------------------------------------------------
st.markdown("## 📷 Upload de Fotografias")

fachada = st.file_uploader("🏠 Fachada (1 foto)", type=["jpg", "jpeg", "png"], accept_multiple_files=False)
acesso = st.file_uploader("🚪 Acesso (até 3 fotos)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
vestigios = st.file_uploader("🧬 Vestígios (até 10 fotos)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
digitais = st.file_uploader("🧤 Digitais e DNA (até 5 fotos)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

# -------------------------------------------------------
# ☁️ AUTENTICAÇÃO GOOGLE DRIVE
# -------------------------------------------------------
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
creds = None

if TOKEN_PATH.exists():
    with open(TOKEN_PATH, "rb") as token:
        creds = pickle.load(token)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

if not creds or not creds.valid:
    st.warning("🔐 É necessário autorizar o acesso ao Google Drive antes de enviar os dados.")
    creds_json = st.secrets["oauth_credentials"]["client_json"]
    creds_info = json.loads(creds_json)
    redirect_uri = "https://formulario-campo.streamlit.app"

    flow = InstalledAppFlow.from_client_config(creds_info, SCOPES, redirect_uri=redirect_uri)
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")

    st.markdown("1️⃣ Clique no link abaixo para autorizar:")
    st.markdown(f"👉 [Autorizar aplicativo]({auth_url})")

    auth_code = st.text_input("2️⃣ Após autorizar, cole aqui o código mostrado pelo Google:")

    if auth_code:
        flow.fetch_token(code=auth_code)
        creds = flow.credentials
        with open(TOKEN_PATH, "wb") as token:
            pickle.dump(creds, token)
        st.success("✅ Autorização concluída! Agora você pode salvar os dados.")
        st.stop()

# -------------------------------------------------------
# 💾 SALVAR DADOS E ENVIAR
# -------------------------------------------------------
if creds and st.button("💾 Salvar Dados"):
    st.session_state["form_data"].update({
        "data": data.strftime("%Y-%m-%d"),
        "hora": hora.strftime("%H:%M"),
        "latitude": latitude,
        "longitude": longitude,
        "preservacao": preservacao,
        "vtr": vtr,
        "acompanhante": acompanhante,
        "fotografo": fotografo,
        "materiais": materiais,
        "observacoes": observacoes
    })

    st.info("☁️ Salvando dados e enviando para o Google Drive...")

    PASTA_FOTOS.mkdir(exist_ok=True)
    data_pasta = data.strftime("%Y-%m-%d")
    pasta_atendimento = PASTA_FOTOS / f"{data_pasta}_{hora.strftime('%H-%M')}"
    pasta_atendimento.mkdir(exist_ok=True)

    subpastas = {
        "fachada": fachada,
        "acesso": acesso[:3] if acesso else [],
        "vestigios": vestigios[:10] if vestigios else [],
        "digitais": digitais[:5] if digitais else []
    }

    for categoria, arquivos in subpastas.items():
        pasta = pasta_atendimento / categoria
        pasta.mkdir(exist_ok=True)
        if arquivos:
            if not isinstance(arquivos, list):
                arquivos = [arquivos]
            for i, arquivo in enumerate(arquivos, 1):
                caminho_arquivo = pasta / f"{categoria}_{i}.jpg"
                with open(caminho_arquivo, "wb") as f:
                    f.write(arquivo.getbuffer())

    if CAMINHO_PLANILHA.exists():
        df_existente = pd.read_excel(CAMINHO_PLANILHA)
    else:
        df_existente = pd.DataFrame()

    nova_linha = pd.DataFrame([{
        "Data": data.strftime("%d/%m/%Y"),
        "Hora": hora.strftime("%H:%M"),
        "Latitude": latitude,
        "Longitude": longitude,
        "Preservação": preservacao,
        "VTR": vtr,
        "Acompanhante": acompanhante,
        "Fotógrafo": fotografo,
        "Materiais": materiais,
        "Observações": observacoes,
        "Pasta_Fotos": str(pasta_atendimento)
    }])

    df_final = pd.concat([df_existente, nova_linha], ignore_index=True)
    df_final.to_excel(CAMINHO_PLANILHA, index=False)

    service = build("drive", "v3", credentials=creds)
    PASTA_ID_DESTINO = "13xQ1pcEjGDWQaj1vqgtkuHxsm8ojJkL7"

    file_metadata = {"name": "dados_campo.xlsx", "parents": [PASTA_ID_DESTINO]}
    media = MediaFileUpload(str(CAMINHO_PLANILHA), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    service.files().create(body=file_metadata, media_body=media, fields="id").execute()

    for root, _, files in os.walk(pasta_atendimento):
        for file in files:
            caminho = Path(root) / file
            file_metadata = {"name": file, "parents": [PASTA_ID_DESTINO]}
            media = MediaFileUpload(str(caminho), mimetype="image/jpeg")
            service.files().create(body=file_metadata, media_body=media, fields="id").execute()

    st.success("✅ Dados e fotos enviados com sucesso para o Google Drive!")
    st.balloons()
