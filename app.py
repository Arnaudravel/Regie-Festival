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

# Initialisation des variables d'état
if 'nom_festival' not in st.session_state: st.session_state.nom_festival = "Nouveau Festival"
if 'logo_festival' not in st.session_state: st.session_state.logo_festival = None
if 'planning' not in st.session_state:
    st.session_state.planning = pd.DataFrame(columns=["Scène", "Jour", "Artiste", "Balance", "Show"])
if 'fiches_tech' not in st.session_state:
    st.session_state.fiches_tech = pd.DataFrame(columns=["Scène", "Jour", "Groupe", "Catégorie", "Marque", "Modèle", "Quantité", "Artiste_Apporte"])
if 'riders_stockage' not in st.session_state:
    st.session_state.riders_stockage = {} 
if 'pdf_uploader_key' not in st.session_state:
    st.session_state.pdf_uploader_key = 0 
if 'bibliotheque' not in st.session_state:
    st.session_state.bibliotheque = {
        "MICROS FILAIRE": {"SHURE": ["SM58", "SM57", "BETA52"], "SENNHEISER": ["MD421", "E906"]},
        "REGIE": {"YAMAHA": ["QL1", "CL5"], "MIDAS": ["M32"]},
        "MICROS HF": {"SHURE": ["AD4D"], "SENNHEISER": ["6000 Series"]},
        "EAR MONITOR": {"SHURE": ["PSM1000"]}
    }

# --- FONCTION DE LECTURE EXCEL POUR LA BIBLIOTHÈQUE ---
def charger_bibliotheque_excel(file):
    try:
        dict_final = {}
        # Lecture de tous les onglets
        all_sheets = pd.read_excel(file, sheet_name=None)
        for sheet_name, df in all_sheets.items():
            # On nettoie le nom de l'onglet (ex: "DONNEES MICROS FILAIRE" -> "MICROS FILAIRE")
            cat_name = sheet_name.replace("DONNEES ", "").upper()
            dict_final[cat_name] = {}
            # Chaque colonne est une marque
            for col in df.columns:
                brand_name = col.split('_')[0].upper() # ex: SHURE_FILAIRE -> SHURE
                models = df[col].dropna().astype(str).tolist()
                if models:
                    dict_final[cat_name][brand_name] = models
        return dict_final
    except Exception as e:
        st.error(f"Erreur lors de la lecture de l'Excel : {e}")
        return st.session_state.bibliotheque

# --- 2. MOTEUR DE CALCUL (LOGIQUE N+N+1) ---
def calculer_besoin_journee(df_tech, planning, scene, jour):
    plan = planning[(planning["Scène"] == scene) & (planning["Jour"] == jour)].copy().sort_values(by="Show")
    artistes = plan["Artiste"].tolist()
    if not artistes: return pd.DataFrame()
    matos_regie = df_tech[(df_tech["Scène"] == scene) & (df_tech["Jour"] == jour) & (df_tech["Artiste_Apporte"] == False)]
    if matos_regie.empty: return pd.DataFrame()
    
    if len(artistes) == 1:
        return matos_regie.groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].sum().reset_index()

    besoins_binomes = []
    for i in range(len(artistes) - 1):
        df_binome = matos_regie[matos_regie["Groupe"].isin([artistes[i], artistes[i+1]])]
        besoins_binomes.append(df_binome.groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].sum())
    
    if besoins_binomes:
        res = pd.concat(besoins_binomes, axis=1).max(axis=1).reset_index()
        res.columns = ["Catégorie", "Marque", "Modèle", "Quantité"]
        return res
    return pd.DataFrame()

# --- 3. CLASSES D'EXPORT PDF ---
class FestivalPDF(FPDF):
    def header(self):
        if st.session_state.logo_festival:
            img = st.session_state.logo_festival
            with io.BytesIO() as buf:
                img.save(buf, format='PNG')
                with open("temp_logo.png", "wb") as f: f.write(buf.getvalue())
            self.image("temp_logo.png", 10, 8, 25)
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, st.session_state.nom_festival, 0, 1, 'R')
        self.ln(10)

def export_categorized_pdf(df, title):
    pdf = FestivalPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, title, ln=True, align='C'); pdf.ln(10)
    if df.empty: return pdf.output(dest='S').encode('latin-1')
    for cat in df["Catégorie"].unique():
        pdf.set_fill_color(200, 220, 255); pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, f"Catégorie : {cat}", ln=True, fill=True)
        pdf.set_fill_color(240, 240, 240); pdf.set_font("Arial", 'B', 9)
        pdf.cell(50, 8, "Marque", 1); pdf.cell(100, 8, "Modèle", 1); pdf.cell(30, 8, "Quantité", 1, 1, 'C', True)
        pdf.set_font("Arial", '', 9)
        for _, row in df[df["Catégorie"] == cat].iterrows():
            pdf.cell(50, 7, str(row["Marque"]), 1); pdf.cell(100, 7, str(row["Modèle"]), 1); pdf.cell(30, 7, str(row["Quantité"]), 1, 1, 'C')
        pdf.ln(5)
    return pdf.output(dest='S').encode('latin-1')

def export_planning_structured(df, title):
    pdf = FestivalPDF()
    pdf.add_page(); pdf.set_font("Arial", 'B', 18); pdf.cell(0, 15, title, ln=True, align='C'); pdf.ln(5)
    for jour in sorted(df["Jour"].unique()):
        pdf.set_fill_color(50, 50, 50); pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, f"DATE : {jour}", 1, 1, 'L', True); pdf.set_text_color(0, 0, 0)
        for scene in sorted(df[df["Jour"] == jour]["Scène"].unique()):
            pdf.ln(2); pdf.set_fill_color(220, 230, 255); pdf.set_font("Arial", 'B', 12); pdf.cell(0, 8, f"SCÈNE : {scene}", "L", 1, 'L', True)
            pdf.set_font("Arial", '', 10)
            for _, row in df[(df["Jour"] == jour) & (df["Scène"] == scene)].sort_values(by="Show").iterrows():
                pdf.cell(30, 8, str(row["Show"]), 1); pdf.cell(100, 8, str(row["Artiste"]), 1); pdf.cell(30, 8, str(row["Balance"]), 1, 1, 'C')
        pdf.ln(5)
    return pdf.output(dest='S').encode('latin-1')

# --- 4. INTERFACE ---
c_h1, c_h2 = st.columns([1, 4])
with c_h1: 
    if st.session_state.logo_festival: st.image(st.session_state.logo_festival, width=100)
with c_h2: 
    st.title(st.session_state.nom_festival)

tabs = st.tabs(["🏗️ Configuration", "⚙️ Patch & Régie", "📄 Exports PDF"])

# --- ONGLET 1 : CONFIGURATION ---
with tabs[0]:
    c1, c2 = st.columns(2)
    st.session_state.nom_festival = c1.text_input("Nom du Festival", st.session_state.nom_festival)
    upl_logo = c2.file_uploader("Logo Festival", type=["png", "jpg"])
    if upl_logo: st.session_state.logo_festival = Image.open(upl_logo)

    st.divider()
    col_file1, col_file2 = st.columns(2)
    with col_file1:
        st.subheader("📊 Base Matériel (Excel)")
        base_excel = st.file_uploader("Importer ton catalogue Excel", type=["xlsx"])
        if base_excel and st.button("Mettre à jour la Bibliothèque"):
            st.session_state.bibliotheque = charger_bibliotheque_excel(base_excel)
            st.success("Bibliothèque mise à jour !")

    with col_file2:
        st.subheader("💾 Sauvegarde Projet")
        # Export JSON du state pour sauvegarde
        data_to_save = {
            "planning": st.session_state.planning.to_json(),
            "fiches": st.session_state.fiches_tech.to_json(),
            "nom": st.session_state.nom_festival
        }
        st.download_button("📥 Sauvegarder mon travail", json.dumps(data_to_save), f"projet_{st.session_state.nom_festival}.json")
        load_proj = st.file_uploader("Charger un projet (.json)", type=["json"])
        if load_proj:
            d = json.load(load_proj)
            st.session_state.planning = pd.read_json(io.StringIO(d["planning"]))
            st.session_state.fiches_tech = pd.read_json(io.StringIO(d["fiches"]))
            st.session_state.nom_festival = d["nom"]
            st.rerun()

    st.divider()
    with st.expander("➕ Ajouter un Artiste", expanded=True):
        col1, col2, col3, col4, col5 = st.columns(5)
        in_sc = col1.text_input("Scène", "MainStage")
        in_jo = col2.date_input("Date", datetime.date.today())
        in_art = col3.text_input("Nom Artiste")
        in_bal = col4.text_input("Balance", "14:00")
        in_sho = col5.text_input("Show", "20:00")
        in_files = st.file_uploader("Fiches Techniques (PDF)", accept_multiple_files=True, key=f"pdf_up_{st.session_state.pdf_uploader_key}")
        if st.button("Valider Artiste"):
            if in_art:
                new_row = pd.DataFrame([{"Scène":in_sc, "Jour":in_jo, "Artiste":in_art, "Balance":in_bal, "Show":in_sho}])
                st.session_state.planning = pd.concat([st.session_state.planning, new_row], ignore_index=True)
                st.session_state.riders_stockage[in_art] = {f.name: f.read() for f in in_files} if in_files else {}
                st.session_state.pdf_uploader_key += 1; st.rerun()

    st.subheader("Planning Global")
    if not st.session_state.planning.empty:
        ed_plan = st.data_editor(st.session_state.planning, num_rows="dynamic", use_container_width=True)
        if st.button("Enregistrer Planning"): st.session_state.planning = ed_plan; st.rerun()

    if not st.session_state.planning.empty:
        st.divider()
        st.subheader("📁 Gestion des Fichiers PDF")
        c_p1, c_p2 = st.columns([1, 2])
        sel_art_pdf = c_p1.selectbox("Artiste :", st.session_state.planning["Artiste"].unique())
        files_dict = st.session_state.riders_stockage.get(sel_art_pdf, {})
        for fname in list(files_dict.keys()):
            cc1, cc2 = st.columns([4, 1])
            cc1.text(f"📄 {fname}")
            if cc2.button("❌", key=f"del_{sel_art_pdf}_{fname}"):
                del st.session_state.riders_stockage[sel_art_pdf][fname]; st.rerun()

# --- ONGLET 2 : PATCH ---
with tabs[1]:
    if not st.session_state.planning.empty:
        col_s1, col_s2, col_s3, col_s4 = st.columns([1, 1, 1, 2])
        p_jour = col_s1.selectbox("Jour", sorted(st.session_state.planning["Jour"].unique()), key="pj")
        p_scene = col_s2.selectbox("Scène", st.session_state.planning[st.session_state.planning["Jour"]==p_jour]["Scène"].unique(), key="ps")
        p_art = col_s3.selectbox("Artiste", st.session_state.planning[(st.session_state.planning["Jour"]==p_jour) & (st.session_state.planning["Scène"]==p_scene)]["Artiste"].unique(), key="pa")
        
        pdfs_art = st.session_state.riders_stockage.get(p_art, {})
        with col_s4:
            if pdfs_art:
                to_view = st.selectbox("Voir Rider :", list(pdfs_art.keys()))
                b64 = base64.b64encode(pdfs_art[to_view]).decode('utf-8')
                st.markdown(f'<a href="data:application/pdf;base64,{b64}" target="_blank" download="{to_view}"><button style="background-color:#28a745;color:white;border:none;padding:8px;border-radius:4px;width:100%;cursor:pointer;">📖 OUVRIR {to_view}</button></a>', unsafe_allow_html=True)
            else: st.info("Aucun PDF")

        with st.expander(f"📥 Saisie Matériel : {p_art}", expanded=True):
            ci1, ci2, ci3, ci4, ci5 = st.columns([2, 2, 2, 1, 1])
            m_cat = ci1.selectbox("Catégorie", list(st.session_state.bibliotheque.keys()))
            m_mar = ci2.selectbox("Marque", list(st.session_state.bibliotheque.get(m_cat, {}).keys()))
            m_mod = ci3.selectbox("Modèle", st.session_state.bibliotheque.get(m_cat, {}).get(m_mar, []) + ["+ LIBRE"])
            if m_mod == "+ LIBRE": m_mod = ci3.text_input("Référence Libre")
            m_qte = ci4.number_input("Qté", 1, 200, 1)
            if st.button("Ajouter au Patch"):
                new_line = pd.DataFrame([{"Scène":p_scene, "Jour":p_jour, "Groupe":p_art, "Catégorie":m_cat, "Marque":m_mar, "Modèle":m_mod, "Quantité":m_qte, "Artiste_Apporte":ci5.checkbox("Artiste Apporte")}])
                st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, new_line], ignore_index=True); st.rerun()

        st.divider()
        cl, cr = st.columns([1.3, 0.7])
        with cl:
            st.subheader(f"📋 Patch de {p_art}")
            mask = (st.session_state.fiches_tech["Groupe"] == p_art) & (st.session_state.fiches_tech["Jour"] == p_jour)
            ed_patch = st.data_editor(st.session_state.fiches_tech[mask], num_rows="dynamic", use_container_width=True)
            if st.button("Sauvegarder Patch"):
                st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech[~mask], ed_patch], ignore_index=True); st.rerun()
        with cr:
            st.subheader(f"📊 Besoin {p_scene}")
            st.dataframe(calculer_besoin_journee(st.session_state.fiches_tech, st.session_state.planning, p_scene, p_jour), hide_index=True)

# --- ONGLET 3 : EXPORTS ---
with tabs[2]:
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        st.subheader("📅 Export Planning")
        scope_p = st.radio("Périmètre :", ["Par Scène / Jour", "Toute la Journée", "Tout le Festival"])
        if st.button("Générer PDF Planning"):
            pdf_p = export_planning_structured(st.session_state.planning, "Planning Festival")
            st.download_button("📥 Télécharger Planning", pdf_p, "planning.pdf")
    with col_e2:
        st.subheader("🛠️ Export Matériel")
        scope_m = st.radio("Type :", ["Besoin Journée (N+N+1)", "Besoin Global Scène"])
        if st.button("Générer Rapport Matériel"):
            m_s = st.session_state.planning["Scène"].iloc[0] if not st.session_state.planning.empty else "Scène"
            res = calculer_besoin_journee(st.session_state.fiches_tech, st.session_state.planning, m_s, datetime.date.today())
            st.download_button("📥 Télécharger Rapport", export_categorized_pdf(res, "Besoin Matériel"), "materiel.pdf")