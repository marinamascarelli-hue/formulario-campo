import streamlit as st
import pandas as pd
from datetime import datetime
import os
from pathlib import Path

# 📁 Caminhos
PASTA_BASE = Path(r"C:\Users\Marina\Desktop\Formulario de Campo")
CAMINHO_PLANILHA = PASTA_BASE / "dados_campo.xlsx"
PASTA_FOTOS = PASTA_BASE / "fotos"

st.set_page_config(page_title="Formulário de Atendimento", page_icon="📋", layout="centered")
st.title("🧾 Formulário de Atendimento de Campo - Polícia Científica")
st.write("Preencha as informações e anexe as fotografias correspondentes ao atendimento.")

# 📅 Data e horário automáticos
col1, col2 = st.columns(2)
with col1:
    data = st.date_input("📅 Data do Atendimento", datetime.today())
with col2:
    hora = st.time_input("🕒 Horário", datetime.now().time())

# 📍 Geolocalização
st.markdown("### 📍 Geolocalização do Local do Fato")
latitude = st.text_input("Latitude (use o botão abaixo para capturar automaticamente):")
longitude = st.text_input("Longitude:")

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

# 🧩 Campos do atendimento
preservacao = st.text_input("🔒 Preservação (situação do local)")
vtr = st.text_input("🚓 VTR (veículo utilizado)")
acompanhante = st.text_input("👮 Acompanhante")

fotografos = [
    "Adriano Godoi de Lara",
    "Cássio Henrique Reolon Ferreira da Silva",
    "Marcelo Barburino Valente",
    "Marcos Paulo de Souza",
    "Maria Nathalia Bortolotto Beghini",
    "Murilo Carlos de Souza",
    "Sandro Alberto Baracho"
]
fotografo = st.selectbox("📸 Fotógrafo Responsável", fotografos)

materiais = st.text_area("🧪 Materiais Coletados")
observacoes = st.text_area("🗒️ Observações Gerais")

# 🖼️ Upload de fotos
st.markdown("## 📷 Upload de Fotografias")

fachada = st.file_uploader("🏠 Fachada (1 foto)", type=["jpg", "jpeg", "png"], accept_multiple_files=False)
acesso = st.file_uploader("🚪 Acesso (até 3 fotos)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
vestigios = st.file_uploader("🧬 Vestígios (até 10 fotos)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
digitais = st.file_uploader("🧤 Digitais e DNA (até 5 fotos)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

# 🔘 Botão de salvar
if st.button("💾 Salvar Dados"):
    # Criar pasta base e de fotos
    PASTA_FOTOS.mkdir(exist_ok=True)
    data_pasta = data.strftime("%Y-%m-%d")
    pasta_atendimento = PASTA_FOTOS / f"{data_pasta}_{hora.strftime('%H-%M')}"
    pasta_atendimento.mkdir(exist_ok=True)

    # Subpastas por categoria
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

    # Registrar no Excel
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

    st.success("✅ Dados e fotos salvos com sucesso!")
    st.balloons()
