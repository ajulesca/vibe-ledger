import streamlit as st
from streamlit_gsheets import GSheetsConnection
import google.genai as genai
import datetime
import pandas as pd
import plotly.express as px
import json

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="VibeLedger", page_icon="💰", layout="wide")

# Tentar carregar a chave da API do segredo
api_key = st.secrets.get("GEMINI_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key)

# Conexão com Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    return conn.read(ttl="1m")

# --- SIDEBAR / QUEM É VOCÊ? ---
st.sidebar.title("Configurações")
usuario = st.sidebar.selectbox("Quem está lançando?", ["Daniele", "Juliana"])
limite_mensal = st.sidebar.number_input("Meta de Gasto Mensal (R$)", value=5000)

# --- ABA DE LANÇAMENTO ---
st.title("💰 VibeLedger")
st.subheader(f"Olá, {usuario}! Qual é a vibe financeira de hoje?")

vibe_input = st.text_input("Ex: 'Gastei 150 no jantar com a Ju' ou 'Ração dos gatos 200'", placeholder="Digite aqui...")

if st.button("Registrar Gasto"):
    if vibe_input:
        with st.spinner("O Gemini está processando..."):
            prompt = f"""
            Você é um assistente financeiro. Extraia os dados desta frase: "{vibe_input}"
            Retorne APENAS um JSON com:
            - Data (YYYY-MM-DD) - hoje é {datetime.date.today()}
            - Descricao
            - Valor (número)
            - Categoria (Alimentação, Gatos, Viagem, Casa, Lazer, Outros)
            """
            response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
            
            # Limpeza do JSON
            clean_res = response.text.strip().replace('```json', '').replace('```', '')
            data = json.loads(clean_res)
            
            # Adicionar o dono do gasto
            data['Dono'] = usuario
            
            # Salvar no Sheets
            df_existente = get_data()
            novo_df = pd.concat([df_existente, pd.DataFrame([data])], ignore_index=True)
            conn.update(data=novo_df)
            st.success("Gasto registrado com sucesso!")
            st.rerun()

# --- DASHBOARD ---
st.divider()
st.header("📊 Dashboard de Vibes")

df = get_data()

if not df.empty:
    # Garantir que Valor é numérico
    df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce')
    total_gasto = df['Valor'].sum()
    
    # Métricas Principais
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Gasto", f"R$ {total_gasto:,.2f}")
    col2.metric("Meta Mensal", f"R$ {limite_mensal:,.2f}")
    
    restante = limite_mensal - total_gasto
    cor_metric = "normal" if restante > 0 else "inverse"
    col3.metric("Restante", f"R$ {restante:,.2f}", delta=f"{restante}", delta_color=cor_metric)

    # Gráficos
    c1, c2 = st.columns(2)
    
    with c1:
        st.write("### Gastos por Categoria")
        fig_cat = px.pie(df, values='Valor', names='Categoria', hole=0.4)
        st.plotly_chart(fig_cat, use_container_width=True)
        
    with c2:
        st.write("### Gastos por Dono(a)")
        fig_dono = px.bar(df.groupby('Dono')['Valor'].sum().reset_index(), 
                          x='Dono', y='Valor', color='Dono',
                          labels={'Valor': 'Total Gasto (R$)'})
        st.plotly_chart(fig_dono, use_container_width=True)

    # Tabela Recente
    st.write("### Últimos Lançamentos")
    st.dataframe(df.tail(10).iloc[::-1], use_container_width=True, hide_index=True)
else:
    st.info("Ainda não há dados para exibir no dashboard.")
