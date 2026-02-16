import streamlit as st
import pandas as pd
from fpdf import FPDF
from PIL import Image
import base64
import io
import datetime
import json

# --- 1. CONFIGURATION & STATE ---
st.set_page_config(page_title="Régie Festival Pro", layout="wide")

if 'nom_festival' not in st.session_state: st.session_state.nom_festival = "Mon Festival"
if 'logo_festival' not in st.session_state: st.session_state.logo_festival = None
if 'planning' not in st.session_state:
    st.session_state.planning = pd.DataFrame(columns=["Scène", "Jour", "Artiste", "Balance", "Show"])
if 'fiches_tech' not in st.session_state:
    st.session_state.fiches_tech = pd.DataFrame(columns=["Scène", "Jour", "Groupe", "Catégorie", "Marque", "Modèle", "Quantité", "Artiste_Apporte"])
if 'riders_stockage' not in st.session_state:
    st.session_state.riders_stockage = {} 
if 'pdf_uploader_key' not in st.session_state:
    st.session_state.pdf_uploader_key = 0

# --- 2. LOGIQUE DE CALCUL N+N+1 ---
def calculer_besoin_max_scene(df_tech, planning, scene, jour):
    plan = planning[(planning["Scène"] == scene) & (planning["Jour"] == str(jour))].copy().sort_values(by="Show")
    if plan.empty: return pd.DataFrame()
    artistes_ord = plan["Artiste"].tolist()
    matos = df_tech[(df_tech["Scène"] == scene) & (df_tech["Jour"] == str(jour)) & (df_tech["Artiste_Apporte"] == False)]
    if matos.empty: return pd.DataFrame()
    
    scenarios = []
    if len(artistes_ord) == 1:
        scenarios.append(matos.groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].sum().reset_index())
    else:
        for i in range(len(artistes_ord) - 1):
            binome = matos[matos["Groupe"].isin([artistes_ord[i], artistes_ord[i+1]])]
            scenarios.append(binome.groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].sum().reset_index())
        scenarios.append(matos[matos["Groupe"] == artistes_ord[-1]].groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].sum().reset_index())
    
    if not scenarios: return pd.DataFrame()
    return pd.concat(scenarios).groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].max().reset_index()

# --- 3. MOTEUR PDF ---
class FestivalPDF(FPDF):
    def header(self):
        if st.session_state.logo_festival:
            with io.BytesIO() as buf:
                st.session_state.logo_festival.save(buf, format='PNG')
                with open("temp_logo.png", "wb") as f: f.write(buf.getvalue())
            self.image("temp_logo.png", 10, 8, 25)
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, st.session_state.nom_festival, 0, 1, 'R')
        self.ln(10)

def generer_pdf(df, titre):
    pdf = FestivalPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, titre, ln=True, align='C')
    pdf.ln(5)
    
    if "Catégorie" in df.columns: # Format Matériel
        for cat in df["Catégorie"].unique():
            pdf.set_fill_color(230, 230, 230)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, f" CATEGORIE : {cat}", ln=True, fill=True)
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(60, 8, "Marque", 1); pdf.cell(90, 8, "Modele", 1); pdf.cell(30, 8, "Qte", 1, ln=True)
            pdf.set_font("Arial", '', 10)
            for _, r in df[df["Catégorie"] == cat].iterrows():
                pdf.cell(60, 7, str(r["Marque"]), 1); pdf.cell(90, 7, str(r["Modèle"]), 1); pdf.cell(30, 7, str(r["Quantité"]), 1, ln=True)
            pdf.ln(5)
    else: # Format Planning
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(40, 8, "Scene", 1); pdf.cell(80, 8, "Artiste", 1); pdf.cell(30, 8, "Balance", 1); pdf.cell(30, 8, "Show", 1, ln=True)
        pdf.set_font("Arial", '', 10)
        for _, r in df.iterrows():
            pdf.cell(40, 7, str(r["Scène"]), 1); pdf.cell(80, 7, str(r["Artiste"]), 1); pdf.cell(30, 7, str(r["Balance"]), 1); pdf.cell(30, 7, str(r["Show"]), 1, ln=True)
            
    return pdf.output(dest='S').encode('latin-1')

# --- 4. INTERFACE ---
c_l, c_t = st.columns([1, 4])
with c_l:
    if st.session_state.logo_festival: st.image(st.session_state.logo_festival, width=100)
with c_t: st.title(st.session_state.nom_festival)

t1, t2, t3 = st.tabs(["🏗️ Configuration & Planning", "⚙️ Patch & Régie", "📄 Exports PDF"])

# --- ONGLET 1 ---
with t1:
    with st.expander("🛠️ Paramètres"):
        st.session_state.nom_festival = st.text_input("Nom", st.session_state.nom_festival)
        u_l = st.file_uploader("Logo", type=["png", "jpg"])
        if u_l: st.session_state.logo_festival = Image.open(u_l)

    st.subheader("➕ Ajouter un Artiste")
    with st.container(border=True):
        cA, cB, cC, cD, cE = st.columns([1.5, 1.5, 3, 1, 1])
        n_sc = cA.text_input("Scène", "MainStage")
        n_jo = cB.date_input("Date", datetime.date.today())
        n_art = cC.text_input("Artiste")
        n_bal = cD.time_input("Balance", datetime.time(14, 0))
        n_sho = cE.time_input("Show", datetime.time(20, 0))
        n_pdf = st.file_uploader("PDF", accept_multiple_files=True, key=f"p_{st.session_state.pdf_uploader_key}")
        
        if st.button("Valider"):
            row = pd.DataFrame([{"Scène": n_sc, "Jour": str(n_jo), "Artiste": n_art, "Balance": n_bal.strftime("%H:%M"), "Show": n_sho.strftime("%H:%M")}])
            st.session_state.planning = pd.concat([st.session_state.planning, row], ignore_index=True)
            if n_pdf: st.session_state.riders_stockage[n_art] = {f.name: f.read() for f in n_pdf}
            st.session_state.pdf_uploader_key += 1
            st.rerun()

    st.subheader("📅 Gestion du Planning")
    if not st.session_state.planning.empty:
        df_p = st.session_state.planning.copy()
        df_p.insert(0, "PDF", df_p["Artiste"].apply(lambda x: "✅" if st.session_state.riders_stockage.get(x) else "❌"))
        # TABLEAU EDITABLE ET SUPPRIMABLE
        ed_p = st.data_editor(df_p, use_container_width=True, num_rows="dynamic", hide_index=True)
        if st.button("Sauvegarder les modifications"):
            st.session_state.planning = ed_p.drop(columns=["PDF"])
            st.rerun()

    st.divider()
    st.subheader("📁 Gestion des Fichiers PDF")
    if st.session_state.riders_stockage:
        a_s = st.selectbox("Artiste", list(st.session_state.riders_stockage.keys()))
        for fn in list(st.session_state.riders_stockage[a_s].keys()):
            cf1, cf2 = st.columns([4, 1])
            cf1.write(f"📄 {fn}")
            if cf2.button("Supprimer", key=f"d_{fn}"):
                del st.session_state.riders_stockage[a_s][fn]
                st.rerun()

# --- ONGLET 2 ---
with t2:
    if not st.session_state.planning.empty:
        s1, s2, s3, s4 = st.columns([1, 1, 1, 2])
        sj = s1.selectbox("Jour ", sorted(st.session_state.planning["Jour"].unique()))
        ss = s2.selectbox("Scène ", st.session_state.planning[st.session_state.planning["Jour"]==sj]["Scène"].unique())
        sa = s3.selectbox("Artiste ", st.session_state.planning[(st.session_state.planning["Jour"]==sj) & (st.session_state.planning["Scène"]==ss)]["Artiste"].unique())
        
        with s4:
            pdf_art = st.session_state.riders_stockage.get(sa, {})
            if pdf_art:
                fn = st.selectbox("Ouvrir", list(pdf_art.keys()), label_visibility="collapsed")
                b64 = base64.b64encode(pdf_art[fn]).decode('utf-8')
                st.markdown(f'<a href="data:application/pdf;base64,{b64}" target="_blank" download="{fn}"><div style="background-color:#28a745;color:white;padding:10px;text-align:center;border-radius:5px;font-weight:bold;">📄 OUVRIR LA FICHE TECHNIQUE</div></a>', unsafe_allow_html=True)

        st.divider()
        colL, colR = st.columns(2)
        with colL:
            st.subheader(f"📥 Saisie : {sa}")
            with st.container(border=True):
                # ... (Reste de la saisie patch identique au précédent avec cumul auto)
                cat = st.selectbox("Catégorie", ["MICROS FILAIRE", "REGIE", "DI / LINE", "STANDS"])
                mod = st.text_input("Référence Modèle")
                qte = st.number_input("Quantité", 1, 100, 1)
                app = st.checkbox("Amené par l'Artiste")
                if st.button("Ajouter"):
                    mask = (st.session_state.fiches_tech["Groupe"]==sa) & (st.session_state.fiches_tech["Modèle"]==mod) & (st.session_state.fiches_tech["Artiste_Apporte"]==app)
                    if not st.session_state.fiches_tech[mask].empty:
                        st.session_state.fiches_tech.loc[mask, "Quantité"] += qte
                    else:
                        nl = pd.DataFrame([{"Scène":ss,"Jour":sj,"Groupe":sa,"Catégorie":cat,"Marque":"-","Modèle":mod,"Quantité":qte,"Artiste_Apporte":app}])
                        st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, nl], ignore_index=True)
                    st.rerun()
            st.data_editor(st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"]==sa], use_container_width=True, num_rows="dynamic")

        with colR:
            st.subheader(f"📊 Besoin {sj} - {ss}")
            res = calculer_besoin_max_scene(st.session_state.fiches_tech, st.session_state.planning, ss, sj)
            st.dataframe(res, use_container_width=True, hide_index=True)

# --- ONGLET 3 : EXPORTS ---
with t3:
    st.header("📄 Exports PDF")
    
    cE1, cE2 = st.columns(2)
    with cE1:
        st.subheader("📅 Planning")
        if st.button("Exporter TOUT le Planning"):
            st.download_button("Télécharger", generer_pdf(st.session_state.planning, "Planning Complet"), "planning_complet.pdf")
        
        exp_j = st.selectbox("Par Jour", sorted(st.session_state.planning["Jour"].unique()))
        if st.button("Exporter Planning du " + exp_j):
            st.download_button("Télécharger ", generer_pdf(st.session_state.planning[st.session_state.planning["Jour"]==exp_j], "Planning "+exp_j), "planning_"+exp_j+".pdf")

    with cE2:
        st.subheader("🛠️ Matériel (Régie)")
        exp_s = st.selectbox("Scène", st.session_state.planning["Scène"].unique())
        if st.button("Besoin TOTAL sur " + exp_s):
            # Cumul de tous les jours pour cette scène
            all_days = []
            for j in st.session_state.planning[st.session_state.planning["Scène"]==exp_s]["Jour"].unique():
                all_days.append(calculer_besoin_max_scene(st.session_state.fiches_tech, st.session_state.planning, exp_s, j))
            total_mat = pd.concat(all_days).groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].max().reset_index()
            st.download_button("Télécharger TOTAL", generer_pdf(total_mat, "Matériel Total "+exp_s), "total_"+exp_s+".pdf")
