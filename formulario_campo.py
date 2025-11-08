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

# --- Inicializa session_state defaults para preservar após rerun
if "data" not in st.session_state:
    st.session_state["data"] = agora_brasilia.date()
if "hora" not in st.session_state:
    st.session_state["hora"] = agora_brasilia.time().replace(microsecond=0)
if "latitude" not in st.session_state:
    st.session_state["latitude"] = ""
if "longitude" not in st.session_state:
    st.session_state["longitude"] = ""
if "preservacao" not in st.session_state:
    st.session_state["preservacao"] = ""
if "vtr" not in st.session_state:
    st.session_state["vtr"] = ""
if "acompanhante" not in st.session_state:
    st.session_state["acompanhante"] = ""
if "fotografo" not in st.session_state:
    st.session_state["fotografo"] = ""
if "materiais" not in st.session_state:
    st.session_state["materiais"] = ""
if "observacoes" not in st.session_state:
    st.session_state["observacoes"] = ""

col1, col2 = st.columns(2)
with col1:
    data = st.date_input("📅 Data do Atendimento", value=st.session_state["data"], key="data")
with col2:
    hora = st.time_input("🕒 Horário", value=st.session_state["hora"], key="hora")

# -------------------------------------------------------
# 📍 GEOLOCALIZAÇÃO
# -------------------------------------------------------
st.markdown("### 📍 Geolocalização do Local do Fato")
latitude = st.text_input("Latitude (use o botão abaixo para capturar automaticamente):", value=st.session_state["latitude"], key="latitude")
longitude = st.text_input("Longitude:", value=st.session_state["longitude"], key="longitude")

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
preservacao = st.text_input("🔒 Preservação (situação do local)", value=st.session_state["preservacao"], key="preservacao")
vtr = st.text_input("🚓 VTR (veículo utilizado)", value=st.session_state["vtr"], key="vtr")
acompanhante = st.text_input("👮 Acompanhante", value=st.session_state["acompanhante"], key="acompanhante")

fotografos = [
    "Adriano Godoi de Lara",
    "Cássio Henrique Reolon Ferreira da Silva",
    "Marcelo Barburino Valente",
    "Marcos Paulo de Souza",
    "Maria Nathalia Bortolotto Beghini",
    "Murilo Carlos de Souza",
    "Sandro Alberto Baracho"
]

# preseleciona index se houver valor salvo
default_idx = 0
if st.session_state["fotografo"] in fotografos:
    default_idx = fotografos.index(st.session_state["fotografo"])
fotografo = st.selectbox("📸 Fotógrafo Responsável", fotografos, index=default_idx, key="fotografo")

materiais = st.text_area("🧪 Materiais Coletados", value=st.session_state["materiais"], key="materiais")
observacoes = st.text_area("🗒️ Observações Gerais", value=st.session_state["observacoes"], key="observacoes")

# -------------------------------------------------------
# 📷 UPLOAD DE FOTOS
# -------------------------------------------------------
st.markdown("## 📷 Upload de Fotografias")
fachada = st.file_uploader("🏠 Fachada (1 foto)", type=["jpg", "jpeg", "png"], accept_multiple_files=False, key="fachada")
acesso = st.file_uploader("🚪 Acesso (até 3 fotos)", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="acesso")
vestigios = st.file_uploader("🧬 Vestígios (até 10 fotos)", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="vestigios")
digitais = st.file_uploader("🧤 Digitais e DNA (até 5 fotos)", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="digitais")

# -------------------------------------------------------
# ☁️ AUTENTICAÇÃO GOOGLE DRIVE (com captura automática do code)
# -------------------------------------------------------
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
creds = None

# tenta carregar token salvo
if TOKEN_PATH.exists():
    try:
        with open(TOKEN_PATH, "rb") as token:
            creds = pickle.load(token)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
    except Exception:
        creds = None

# se não há credenciais válidas, inicia fluxo e trata redirect automaticamente
if not creds or not creds.valid:
    st.info("🔐 É necessário autorizar o acesso ao Google Drive antes de enviar os dados.")
    creds_json = st.secrets.get("oauth_credentials", {}).get("client_json")
    if not creds_json:
        st.error("⚠️ Credenciais OAuth não encontradas em st.secrets. Adicione `oauth_credentials.client_json` no painel de secrets.")
        st.stop()
    creds_info = json.loads(creds_json)

    # redirect_uri EXATO que deve estar cadastrado no Google Cloud Console
    redirect_uri = "https://formulario-campo.streamlit.app"  # ajuste se o seu app tiver outro domínio

    flow = InstalledAppFlow.from_client_config(creds_info, SCOPES, redirect_uri=redirect_uri)

    # Detecta se o Google redirecionou de volta com ?code=...
    query_params = st.experimental_get_query_params()
    code_from_google = query_params.get("code", [None])[0]

    if code_from_google:
        # finaliza o fluxo usando o code retornado no redirect
        try:
            flow.fetch_token(code=code_from_google)
            creds = flow.credentials
            # salva token para próximas execuções
            with open(TOKEN_PATH, "wb") as token:
                pickle.dump(creds, token)
            # limpa params da URL e recarrega (preserva session_state)
            st.experimental_set_query_params()
            st.success("✅ Autenticação concluída com sucesso! Recarregando o app...")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Erro ao trocar code por token: {e}")
            st.stop()
    else:
        # armazena os campos textuais atuais em session_state (será preservado durante redirect)
        st.session_state["data"] = st.session_state.get("data", agora_brasilia.date())
        st.session_state["hora"] = st.session_state.get("hora", agora_brasilia.time().replace(microsecond=0))
        st.session_state["latitude"] = st.session_state.get("latitude", "")
        st.session_state["longitude"] = st.session_state.get("longitude", "")
        st.session_state["preservacao"] = st.session_state.get("preservacao", "")
        st.session_state["vtr"] = st.session_state.get("vtr", "")
        st.session_state["acompanhante"] = st.session_state.get("acompanhante", "")
        st.session_state["fotografo"] = st.session_state.get("fotografo", fotografos[0])
        st.session_state["materiais"] = st.session_state.get("materiais", "")
        st.session_state["observacoes"] = st.session_state.get("observacoes", "")

        # gera URL de autorização e informa que o processo continuará automaticamente quando Google redirecionar
        auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")
        st.markdown("### 🔐 Autenticação necessária")
        st.markdown("1) Clique no link abaixo e permita o acesso à sua conta Google.")
        st.markdown(f"👉 [Autorizar aplicativo]({auth_url})")
        st.markdown("2) Após autorizar, o Google irá redirecionar automaticamente de volta para este app e o envio continuará.")
        st.stop()  # pausa a execução até o usuário autorizar

# -------------------------------------------------------
# 💾 SALVAR DADOS E ENVIAR
# -------------------------------------------------------
if creds and st.button("💾 Salvar Dados"):
    st.info("☁️ Salvando dados e enviando para o Google Drive...")

    # Atualiza session_state com os valores atuais (opcional, mas garante persistência)
    st.session_state["data"] = data
    st.session_state["hora"] = hora
    st.session_state["latitude"] = latitude
    st.session_state["longitude"] = longitude
    st.session_state["preservacao"] = preservacao
    st.session_state["vtr"] = vtr
    st.session_state["acompanhante"] = acompanhante
    st.session_state["fotografo"] = fotografo
    st.session_state["materiais"] = materiais
    st.session_state["observacoes"] = observacoes

    # Criar pastas locais
    PASTA_FOTOS.mkdir(exist_ok=True)
    data_pasta = data.strftime("%Y-%m-%d")
    pasta_atendimento = PASTA_FOTOS / f"{data_pasta}_{hora.strftime('%H-%M')}"
    pasta_atendimento.mkdir(exist_ok=True)

    # Subpastas por categoria e salvar fotos localmente
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

    # Salvar planilha localmente
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

    # Upload para Google Drive
    service = build("drive", "v3", credentials=creds)
    PASTA_ID_DESTINO = "13xQ1pcEjGDWQaj1vqgtkuHxsm8ojJkL7"

    # Upload da planilha
    file_metadata = {"name": "dados_campo.xlsx", "parents": [PASTA_ID_DESTINO]}
    media = MediaFileUpload(str(CAMINHO_PLANILHA), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    service.files().create(body=file_metadata, media_body=media, fields="id").execute()

    # Upload das fotos
    for root, _, files in os.walk(pasta_atendimento):
        for file in files:
            caminho = Path(root) / file
            file_metadata = {"name": file, "parents": [PASTA_ID_DESTINO]}
            media = MediaFileUpload(str(caminho), mimetype="image/jpeg")
            service.files().create(body=file_metadata, media_body=media, fields="id").execute()

    st.success("✅ Dados e fotos enviados com sucesso para o Google Drive!")
    st.balloons()
