import streamlit as st
import pandas as pd
import datetime
from fpdf import FPDF
import io
import pickle

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Regie-Festival", layout="wide", initial_sidebar_state="expanded")

# --- BARRE LATERALE : MODE SHOW ---
with st.sidebar:
    st.header("🎛️ Contrôle Régie")
    mode_show = st.toggle("🌙 Mode Show (Sombre)", value=False)
    
    if mode_show:
        st.markdown("""
        <style>
        .stApp { background-color: #0e1117; color: #fafafa; }
        .stContainer, .stButton>button, .stTextInput>div>div>input { background-color: #262730; color: white; border-color: #4c4c52; }
        .stDataFrame { filter: invert(1) hue-rotate(180deg); }
        h1, h2, h3 { color: #ffffff !important; }
        </style>
        """, unsafe_allow_html=True)
        st.success("Mode Show Actif")
    st.divider()

# --- INITIALISATION DES VARIABLES ---
if 'planning' not in st.session_state:
    st.session_state.planning = pd.DataFrame(columns=["Scène", "Jour", "Artiste", "Balance", "Show"])
if 'fiches_tech' not in st.session_state:
    st.session_state.fiches_tech = pd.DataFrame(columns=["Scène", "Jour", "Groupe", "Catégorie", "Marque", "Modèle", "Quantité", "Artiste_Apporte"])
if 'riders_stockage' not in st.session_state:
    st.session_state.riders_stockage = {}
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0
if 'delete_confirm_idx' not in st.session_state:
    st.session_state.delete_confirm_idx = None
if 'delete_confirm_patch_idx' not in st.session_state:
    st.session_state.delete_confirm_patch_idx = None
if 'festival_name' not in st.session_state:
    st.session_state.festival_name = "MON FESTIVAL"
if 'festival_logo' not in st.session_state:
    st.session_state.festival_logo = None
if 'custom_catalog' not in st.session_state:
    st.session_state.custom_catalog = {} 

# --- FONCTION PDF ---
class FestivalPDF(FPDF):
    def header(self):
        if st.session_state.festival_logo:
            try:
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
                    tmp_file.write(st.session_state.festival_logo)
                    tmp_path = tmp_file.name
                self.image(tmp_path, 10, 8, 33)
                os.unlink(tmp_path)
            except: pass
        self.set_font("helvetica", "B", 15)
        offset_x = 45 if st.session_state.festival_logo else 10
        self.set_xy(offset_x, 10)
        self.cell(0, 10, st.session_state.festival_name.upper(), ln=1)
        self.set_font("helvetica", "I", 8)
        self.set_xy(offset_x, 18)
        self.cell(0, 5, f"Généré le {datetime.datetime.now().strftime('%d/%m/%Y à %H:%M')}", ln=1)
        self.ln(10)

    def ajouter_titre_section(self, titre):
        self.set_font("helvetica", "B", 12)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, titre, ln=True, fill=True, border="B")
        self.ln(2)

    def dessiner_tableau(self, df):
        if df.empty: return
        self.set_font("helvetica", "B", 9)
        cols = list(df.columns)
        col_width = (self.w - 20) / len(cols)
        self.set_fill_color(220, 230, 255)
        for col in cols:
            self.cell(col_width, 8, str(col), border=1, fill=True, align='C')
        self.ln()
        self.set_font("helvetica", "", 8)
        for _, row in df.iterrows():
            if self.get_y() > 270: self.add_page()
            for item in row:
                self.cell(col_width, 6, str(item), border=1, align='C')
            self.ln()
        self.ln(5)

def generer_pdf_complet(titre_doc, dictionnaire_dfs):
    pdf = FestivalPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, titre_doc, ln=True, align='C')
    pdf.ln(5)
    for section, df in dictionnaire_dfs.items():
        if not df.empty:
            if pdf.get_y() > 250: pdf.add_page()
            pdf.ajouter_titre_section(section)
            pdf.dessiner_tableau(df)
    return bytes(pdf.output())

# --- INTERFACE ---
st.title(f"{st.session_state.festival_name} - Gestion Régie")
tabs = st.tabs(["🏗️ Configuration", "⚙️ Patch & Régie", "📄 Exports PDF", "🛠️ Admin & Sauvegarde"])

# --- ONGLET 1 (INCHANGÉ SAUF FIX ERROR) ---
with tabs[0]:
    st.subheader("➕ Ajouter un Artiste")
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([1, 1, 2, 1, 1])
        sc = c1.text_input("Scène", "MainStage")
        jo = c2.date_input("Date de passage", datetime.date.today())
        ar = c3.text_input("Nom Artiste")
        ba = c4.time_input("Balance", datetime.time(14, 0))
        sh = c5.time_input("Show", datetime.time(20, 0))
        pdfs = st.file_uploader("FT (PDF)", accept_multiple_files=True, key=f"upl_{st.session_state.uploader_key}")
        if st.button("Valider Artiste"):
            if ar:
                new_row = pd.DataFrame([{"Scène": sc, "Jour": str(jo), "Artiste": ar, "Balance": ba.strftime("%H:%M"), "Show": sh.strftime("%H:%M")}])
                st.session_state.planning = pd.concat([st.session_state.planning, new_row], ignore_index=True)
                if ar not in st.session_state.riders_stockage: st.session_state.riders_stockage[ar] = {}
                if pdfs:
                    for f in pdfs: st.session_state.riders_stockage[ar][f.name] = f.read()
                st.session_state.uploader_key += 1
                st.rerun()

    if st.session_state.delete_confirm_idx is not None:
        idx = st.session_state.delete_confirm_idx
        st.warning(f"Supprimer l'artiste : {st.session_state.planning.iloc[idx]['Artiste']} ?")
        if st.button("Confirmer Suppression"):
            st.session_state.planning = st.session_state.planning.drop(idx).reset_index(drop=True)
            st.session_state.delete_confirm_idx = None
            st.rerun()
        if st.button("Annuler"):
            st.session_state.delete_confirm_idx = None
            st.rerun()

    if not st.session_state.planning.empty:
        df_visu = st.session_state.planning.sort_values(by=["Jour", "Scène", "Show"]).copy()
        df_visu.insert(0, "Rider", df_visu["Artiste"].apply(lambda x: "✅" if st.session_state.riders_stockage.get(x) else "❌"))
        ed_plan = st.data_editor(df_visu, use_container_width=True, num_rows="dynamic", key="main_editor")
        if st.session_state.main_editor["deleted_rows"]:
            st.session_state.delete_confirm_idx = df_visu.index[st.session_state.main_editor["deleted_rows"][0]]
            st.rerun()

# --- ONGLET 2 (MODIFIÉ POUR LES SÉPARATEURS //) ---
with tabs[1]:
    if not st.session_state.planning.empty:
        f1, f2, f3 = st.columns(3)
        with f1: sel_j = st.selectbox("📅 Jour", sorted(st.session_state.planning["Jour"].unique()))
        with f2:
            scenes = st.session_state.planning[st.session_state.planning["Jour"] == sel_j]["Scène"].unique()
            sel_s = st.selectbox("🏗️ Scène", scenes)
        with f3:
            artistes = st.session_state.planning[(st.session_state.planning["Jour"] == sel_j) & (st.session_state.planning["Scène"] == sel_s)]["Artiste"].unique()
            sel_a = st.selectbox("🎸 Groupe", artistes)

        if sel_a:
            st.subheader(f"📥 Saisie Matériel : {sel_a}")
            with st.container(border=True):
                CATALOGUE = st.session_state.custom_catalog
                c_cat, c_mar, c_mod, c_qte, c_app = st.columns([2, 2, 2, 1, 1])
                
                liste_categories = list(CATALOGUE.keys()) if CATALOGUE else ["MICROS", "HF", "EARS", "BACKLINE"]
                v_cat = c_cat.selectbox("Catégorie", liste_categories)
                
                liste_marques = list(CATALOGUE[v_cat].keys()) if CATALOGUE and v_cat in CATALOGUE else ["SHURE", "SENNHEISER"]
                v_mar = c_mar.selectbox("Marque", liste_marques)
                
                v_mod = ""
                if CATALOGUE and v_cat in CATALOGUE and v_mar in CATALOGUE[v_cat]:
                    raw_modeles = CATALOGUE[v_cat][v_mar]
                    # On transforme les // en titres visuels
                    display_modeles = [f"🔹 {m.replace('/','').strip()} 🔹" if m.startswith("//") else m for m in raw_modeles]
                    
                    selected_display = c_mod.selectbox("Modèle", display_modeles)
                    # On récupère le nom original pour la base de données
                    v_mod = raw_modeles[display_modeles.index(selected_display)]
                else:
                    v_mod = c_mod.text_input("Modèle", "SM58")

                v_qte = c_qte.number_input("Qté", 1, 500, 1)
                v_app = c_app.checkbox("Artiste Apporte")
                
                if st.button("Ajouter au Patch"):
                    if v_mod.startswith("//"):
                        st.error("Impossible d'ajouter un titre de section. Choisissez un vrai modèle.")
                    else:
                        mask = (st.session_state.fiches_tech["Groupe"] == sel_a) & (st.session_state.fiches_tech["Modèle"] == v_mod)
                        if not st.session_state.fiches_tech[mask].empty:
                            st.session_state.fiches_tech.loc[mask, "Quantité"] += v_qte
                        else:
                            new_item = pd.DataFrame([{"Scène": sel_s, "Jour": sel_j, "Groupe": sel_a, "Catégorie": v_cat, "Marque": v_mar, "Modèle": v_mod, "Quantité": v_qte, "Artiste_Apporte": v_app}])
                            st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, new_item], ignore_index=True)
                        st.rerun()

            st.divider()
            col_patch, col_besoin = st.columns(2)
            with col_patch:
                df_patch_art = st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"] == sel_a]
                st.data_editor(df_patch_art, use_container_width=True, num_rows="dynamic")
            with col_besoin:
                st.write("Calcul des besoins en cours...")

# --- ONGLET 3 (PDF) INCHANGÉ ---
with tabs[2]:
    st.info("Utilisez les options d'exportations configurées précédemment.")

# --- ONGLET 4 (ADMIN MODIFIÉ POUR ACCEPTER LES //) ---
with tabs[3]:
    st.header("🛠️ Administration")
    col_adm1, col_adm2 = st.columns(2)
    with col_adm1:
        st.session_state.festival_name = st.text_input("Nom Festival", st.session_state.festival_name)
        data_to_save = {"planning": st.session_state.planning, "fiches_tech": st.session_state.fiches_tech, "riders_stockage": st.session_state.riders_stockage, "custom_catalog": st.session_state.custom_catalog}
        st.download_button("💾 Sauvegarder Projet", pickle.dumps(data_to_save), "sauvegarde.pkl")

    with col_adm2:
        st.subheader("📚 Catalogue Matériel")
        code_secret = st.text_input("🔒 Code Admin", type="password")
        if code_secret == "0000":
            xls_file = st.file_uploader("Fichier Excel Items", type=['xlsx'])
            if xls_file and st.button("Charger le Catalogue"):
                xls = pd.ExcelFile(xls_file)
                new_catalog = {}
                for sheet in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=sheet)
                    new_catalog[sheet] = {}
                    for brand in df.columns:
                        # MODIF : On garde tout (même les //) mais on enlève les cases vides
                        list_items = df[brand].dropna().astype(str).tolist()
                        if list_items: new_catalog[sheet][brand] = list_items
                st.session_state.custom_catalog = new_catalog
                st.success("Catalogue mis à jour avec séparateurs !")
