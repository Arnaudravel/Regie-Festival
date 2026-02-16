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

# --- FONCTIONS ---
def charger_bibliotheque_excel(file):
    try:
        dict_final = {}
        all_sheets = pd.read_excel(file, sheet_name=None)
        for sheet_name, df in all_sheets.items():
            cat_name = sheet_name.replace("DONNEES ", "").upper()
            dict_final[cat_name] = {}
            for col in df.columns:
                brand_name = col.split('_')[0].upper()
                models = df[col].dropna().astype(str).tolist()
                if models: dict_final[cat_name][brand_name] = models
        return dict_final
    except Exception as e:
        st.error(f"Erreur Excel : {e}")
        return st.session_state.bibliotheque

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

# --- EXPORTS PDF ---
class FestivalPDF(FPDF):
    def header(self):
        if st.session_state.logo_festival:
            img = st.session_state.logo_festival
            with io.BytesIO() as buf:
                img.save(buf, format='PNG')
                with open("temp_logo.png", "wb") as f: f.write(buf.getvalue())
            self.image("temp_logo.png", 10, 8, 20)
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, st.session_state.nom_festival, 0, 1, 'R')
        self.ln(5)

# --- INTERFACE ---
c_h1, c_h2 = st.columns([1, 4])
with c_h1: 
    if st.session_state.logo_festival: st.image(st.session_state.logo_festival, width=80)
with c_h2: st.title(st.session_state.nom_festival)

tabs = st.tabs(["🏗️ Configuration", "⚙️ Patch & Régie", "📄 Exports PDF"])

# --- TAB 1 : CONFIGURATION ---
with tabs[0]:
    with st.expander("🛠️ Paramètres du Festival & Sauvegarde", expanded=False):
        c1, c2 = st.columns(2)
        st.session_state.nom_festival = c1.text_input("Nom", st.session_state.nom_festival)
        upl_logo = c2.file_uploader("Logo", type=["png", "jpg"])
        if upl_logo: st.session_state.logo_festival = Image.open(upl_logo)
        
        st.divider()
        col_file1, col_file2 = st.columns(2)
        with col_file1:
            st.write("**📚 Base Matériel (Excel)**")
            base_excel = st.file_uploader("Charger Excel", type=["xlsx"], label_visibility="collapsed")
            if base_excel and st.button("Mettre à jour la Bibliothèque"):
                st.session_state.bibliotheque = charger_bibliotheque_excel(base_excel)
                st.success("Bibliothèque chargée !")
        with col_file2:
            st.write("**💾 Projet**")
            data_to_save = {"planning": st.session_state.planning.to_json(), "fiches": st.session_state.fiches_tech.to_json(), "nom": st.session_state.nom_festival}
            st.download_button("📥 Exporter Projet", json.dumps(data_to_save), f"{st.session_state.nom_festival}.json")

    st.subheader("➕ Ajouter un Artiste")
    with st.container(border=True):
        col1, col2, col3, col4, col5 = st.columns([2,2,3,1,1])
        in_sc = col1.text_input("Scène", "MainStage")
        in_jo = col2.date_input("Date")
        in_art = col3.text_input("Artiste")
        in_bal = col4.text_input("Balance", "14:00")
        in_sho = col5.text_input("Show", "20:00")
        in_files = st.file_uploader("Fiches PDF", accept_multiple_files=True, key=f"pdf_up_{st.session_state.pdf_uploader_key}")
        if st.button("✅ Valider l'Artiste"):
            if in_art:
                new_row = pd.DataFrame([{"Scène":in_sc, "Jour":in_jo, "Artiste":in_art, "Balance":in_bal, "Show":in_sho}])
                st.session_state.planning = pd.concat([st.session_state.planning, new_row], ignore_index=True)
                st.session_state.riders_stockage[in_art] = {f.name: f.read() for f in in_files} if in_files else {}
                st.session_state.pdf_uploader_key += 1
                st.rerun()

    st.subheader("📅 Planning & Status PDF")
    if not st.session_state.planning.empty:
        # --- LOGIQUE CROIX ROUGE / VERTE ---
        df_visu = st.session_state.planning.copy()
        df_visu["Rider PDF"] = df_visu["Artiste"].apply(lambda x: "✅" if st.session_state.riders_stockage.get(x) else "❌")
        
        # Réorganiser les colonnes pour mettre les icônes en premier
        cols = ["Rider PDF", "Scène", "Jour", "Artiste", "Balance", "Show"]
        df_visu = df_visu[cols]
        
        ed_plan = st.data_editor(df_visu, num_rows="dynamic", use_container_width=True, disabled=["Rider PDF"])
        if st.button("Enregistrer les modifications du planning"):
            # On ne sauvegarde pas la colonne Rider PDF car elle est calculée
            st.session_state.planning = ed_plan.drop(columns=["Rider PDF"])
            st.rerun()

# --- TAB 2 : PATCH (Inchangé mais propre) ---
with tabs[1]:
    if not st.session_state.planning.empty:
        c_p1, c_p2, c_p3, c_p4 = st.columns([1, 1, 1, 2])
        p_jour = c_p1.selectbox("Jour", sorted(st.session_state.planning["Jour"].astype(str).unique()))
        p_scene = c_p2.selectbox("Scène", st.session_state.planning[st.session_state.planning["Jour"].astype(str)==p_jour]["Scène"].unique())
        p_art = c_p3.selectbox("Artiste", st.session_state.planning[(st.session_state.planning["Jour"].astype(str)==p_jour) & (st.session_state.planning["Scène"]==p_scene)]["Artiste"].unique())
        
        pdfs_art = st.session_state.riders_stockage.get(p_art, {})
        with c_p4:
            if pdfs_art:
                to_view = st.selectbox("Rider :", list(pdfs_art.keys()))
                b64 = base64.b64encode(pdfs_art[to_view]).decode('utf-8')
                st.markdown(f'<a href="data:application/pdf;base64,{b64}" target="_blank" download="{to_view}"><button style="background-color:#28a745;color:white;border:none;padding:8px;border-radius:4px;width:100%;">📖 OUVRIR {to_view}</button></a>', unsafe_allow_html=True)
            else: st.info("Aucun PDF pour cet artiste")

        with st.expander(f"📥 Saisie Patch : {p_art}", expanded=True):
            ci1, ci2, ci3, ci4, ci5 = st.columns([2, 2, 2, 1, 1])
            m_cat = ci1.selectbox("Catégorie", list(st.session_state.bibliotheque.keys()))
            m_mar = ci2.selectbox("Marque", list(st.session_state.bibliotheque.get(m_cat, {}).keys()))
            m_mod = ci3.selectbox("Modèle", st.session_state.bibliotheque.get(m_cat, {}).get(m_mar, []) + ["+ LIBRE"])
            if m_mod == "+ LIBRE": m_mod = ci3.text_input("Référence Libre")
            m_qte = ci4.number_input("Qté", 1, 200, 1)
            if st.button("➕ Ajouter au Patch"):
                new_line = pd.DataFrame([{"Scène":p_scene, "Jour":p_jour, "Groupe":p_art, "Catégorie":m_cat, "Marque":m_mar, "Modèle":m_mod, "Quantité":m_qte, "Artiste_Apporte":ci5.checkbox("Apporté")}])
                st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, new_line], ignore_index=True); st.rerun()

        st.divider()
        cl, cr = st.columns([1.2, 0.8])
        with cl:
            st.subheader(f"📋 Patch de {p_art}")
            mask = (st.session_state.fiches_tech["Groupe"] == p_art)
            st.data_editor(st.session_state.fiches_tech[mask], use_container_width=True)
        with cr:
            st.subheader(f"📊 Besoin {p_scene} (N+N+1)")
            st.dataframe(calculer_besoin_journee(st.session_state.fiches_tech, st.session_state.planning, p_scene, p_jour), hide_index=True)

# --- TAB 3 : EXPORTS ---
with tabs[2]:
    st.info("Utilisez ces boutons pour générer les documents PDF finaux.")
    # Les fonctions d'export (identiques à précédemment) seraient ici...
