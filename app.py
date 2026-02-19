import streamlit as st
import pandas as pd
import datetime
from fpdf import FPDF
import io
import pickle
import base64
import streamlit.components.v1 as components

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Regie-Festival", layout="wide", initial_sidebar_state="collapsed")

# --- AMÉLIORATION : POP-UP TIMER (JAVASCRIPT) ---
st.components.v1.html(
    """
    <script>
    setInterval(function(){
        alert("💾 RAPPEL : Pensez à sauvegarder votre projet dans l'onglet 'Admin' !");
    }, 600000);
    </script>
    """,
    height=0,
    width=0
)

# --- INITIALISATION DES VARIABLES DE SESSION ---
if 'planning' not in st.session_state:
    st.session_state.planning = pd.DataFrame(columns=["Scène", "Jour", "Artiste", "Balance", "Durée Balance", "Show"])
if 'fiches_tech' not in st.session_state:
    st.session_state.fiches_tech = pd.DataFrame(columns=["Scène", "Jour", "Groupe", "Catégorie", "Marque", "Modèle", "Quantité", "Artiste_Apporte"])
if 'infos_techniques' not in st.session_state:
    st.session_state.infos_techniques = {} # {Artiste: {entrees: "", ear: "", stereo: "", mono: ""}}
if 'riders_stockage' not in st.session_state:
    st.session_state.riders_stockage = {}
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0
if 'delete_confirm_idx' not in st.session_state:
    st.session_state.delete_confirm_idx = None
if 'festival_name' not in st.session_state:
    st.session_state.festival_name = "MON FESTIVAL"
if 'festival_logo' not in st.session_state:
    st.session_state.festival_logo = None
if 'custom_catalog' not in st.session_state:
    st.session_state.custom_catalog = {} 

# --- FONCTION DE NETTOYAGE POUR PDF ---
def clean_pdf_text(text):
    if not isinstance(text, str): text = str(text)
    return text.encode('latin-1', 'replace').decode('latin-1').replace('?', '')

# --- CLASSE PDF ---
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
        self.cell(0, 10, clean_pdf_text(st.session_state.festival_name.upper()), ln=1)
        self.set_font("helvetica", "I", 8)
        self.set_xy(offset_x, 18)
        self.cell(0, 5, f"Généré le {datetime.datetime.now().strftime('%d/%m/%Y à %H:%M')}", ln=1)
        self.ln(10)

    def ajouter_titre_section(self, titre):
        self.set_font("helvetica", "B", 12)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, clean_pdf_text(titre), ln=True, fill=True, border="B")
        self.ln(2)

    def dessiner_tableau(self, df):
        if df.empty: return
        self.set_font("helvetica", "B", 9)
        cols = list(df.columns)
        col_width = (self.w - 20) / len(cols)
        self.set_fill_color(220, 230, 255)
        for col in cols:
            self.cell(col_width, 8, clean_pdf_text(col), border=1, fill=True, align='C')
        self.ln()
        self.set_font("helvetica", "", 8)
        for _, row in df.iterrows():
            if self.get_y() > 270: self.add_page()
            for item in row:
                self.cell(col_width, 6, clean_pdf_text(item), border=1, align='C')
            self.ln()
        self.ln(5)

def generer_pdf_complet(titre_doc, dictionnaire_dfs):
    pdf = FestivalPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, clean_pdf_text(titre_doc), ln=True, align='C')
    pdf.ln(5)
    for section, df in dictionnaire_dfs.items():
        if not df.empty:
            if pdf.get_y() > 250: pdf.add_page()
            pdf.ajouter_titre_section(section)
            pdf.dessiner_tableau(df)
    return bytes(pdf.output())

# --- INTERFACE PRINCIPALE ---
st.title(f"{st.session_state.festival_name} - Gestion Régie")
main_tabs = st.tabs(["Configuration", "Technique"])

# ==========================================
# ONGLET 1 : CONFIGURATION
# ==========================================
with main_tabs[0]:
    sub_tabs_config = st.tabs(["Gestion / Planning des Artistes", "Admin & Sauvegarde", "Exports PDF"])
    
    with sub_tabs_config[0]:
        st.subheader("➕ Ajouter un Artiste")
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1, 1, 2, 1])
            sc = c1.text_input("Scène", "MainStage")
            jo = c2.date_input("Date de passage", datetime.date.today())
            ar = c3.text_input("Nom Artiste")
            sh = c4.time_input("Heure du Show", datetime.time(20, 0))
            
            col_opt, col_h_bal, col_d_bal = st.columns([1, 1, 1])
            with col_opt:
                st.write("") 
                opt_balance = st.checkbox("Faire une balance ?", value=True)
            with col_h_bal:
                ba = st.time_input("Heure Balance", datetime.time(14, 0)) if opt_balance else None
                if not opt_balance: st.info("Pas de balance")
            with col_d_bal:
                du = st.text_input("Durée Balance", "45 min") if opt_balance else ""

            pdfs = st.file_uploader("Fiches Techniques (PDF)", accept_multiple_files=True, key=f"upl_{st.session_state.uploader_key}")
            
            if st.button("Valider Artiste"):
                if ar:
                    val_ba = ba.strftime("%H:%M") if ba and opt_balance else ""
                    new_row = pd.DataFrame([{
                        "Scène": sc, "Jour": str(jo), "Artiste": ar, 
                        "Balance": val_ba, "Durée Balance": du, "Show": sh.strftime("%H:%M")
                    }])
                    st.session_state.planning = pd.concat([st.session_state.planning, new_row], ignore_index=True)
                    if ar not in st.session_state.riders_stockage: st.session_state.riders_stockage[ar] = {}
                    if ar not in st.session_state.infos_techniques: st.session_state.infos_techniques[ar] = {"entrees": "", "ear": "", "stereo": "", "mono": ""}
                    if pdfs:
                        for f in pdfs: st.session_state.riders_stockage[ar][f.name] = f.read()
                    st.session_state.uploader_key += 1
                    st.rerun()

        st.subheader("📋 Planning Global")
        if st.session_state.delete_confirm_idx is not None:
            idx = st.session_state.delete_confirm_idx
            st.warning(f"Supprimer l'artiste : {st.session_state.planning.iloc[idx]['Artiste']} ?")
            if st.button("Confirmer Suppression"):
                nom_art = st.session_state.planning.iloc[idx]['Artiste']
                st.session_state.planning = st.session_state.planning.drop(idx).reset_index(drop=True)
                if nom_art in st.session_state.riders_stockage: del st.session_state.riders_stockage[nom_art]
                st.session_state.delete_confirm_idx = None
                st.rerun()

        if not st.session_state.planning.empty:
            df_visu = st.session_state.planning.sort_values(by=["Jour", "Scène", "Show"]).copy()
            df_visu.insert(0, "Rider", df_visu["Artiste"].apply(lambda x: "✅" if st.session_state.riders_stockage.get(x) else "❌"))
            edited_df = st.data_editor(df_visu, use_container_width=True, num_rows="dynamic", key="main_editor", hide_index=True)
            
            if st.session_state.main_editor["deleted_rows"]:
                st.session_state.delete_confirm_idx = df_visu.index[st.session_state.main_editor["deleted_rows"][0]]
                st.rerun()
            
            df_to_save = edited_df.drop(columns=["Rider"])
            if not df_to_save.equals(st.session_state.planning.sort_values(by=["Jour", "Scène", "Show"]).reset_index(drop=True)):
                 st.session_state.planning = df_to_save.reset_index(drop=True)
                 st.rerun()

    with sub_tabs_config[1]:
        st.header("💾 Sauvegarde & Admin")
        c_adm1, c_adm2 = st.columns(2)
        with c_adm1:
            st.session_state.festival_name = st.text_input("Nom du Festival", st.session_state.festival_name)
            new_logo = st.file_uploader("Logo", type=['png', 'jpg'])
            if new_logo: st.session_state.festival_logo = new_logo.read()
            
            data_to_save = {"planning": st.session_state.planning, "fiches_tech": st.session_state.fiches_tech, "infos_techniques": st.session_state.infos_techniques, "riders_stockage": st.session_state.riders_stockage, "festival_name": st.session_state.festival_name, "festival_logo": st.session_state.festival_logo, "custom_catalog": st.session_state.custom_catalog}
            st.download_button("💾 Sauvegarder Projet", pickle.dumps(data_to_save), f"backup_{st.session_state.festival_name}.pkl")
        
        with c_adm2:
            st.subheader("📚 Catalogue (Excel)")
            xls_file = st.file_uploader("Fichier Catalogue", type=['xlsx'])
            if xls_file and st.button("Charger Catalogue"):
                try:
                    xls = pd.ExcelFile(xls_file)
                    new_catalog = {sheet: {brand: pd.read_excel(xls, sheet_name=sheet)[brand].dropna().tolist() for brand in pd.read_excel(xls, sheet_name=sheet).columns} for sheet in xls.sheet_names}
                    st.session_state.custom_catalog = new_catalog
                    st.success("Catalogue chargé !")
                except Exception as e: st.error(f"Erreur : {e}")

    with sub_tabs_config[2]:
        st.header("📄 Exports PDF")
        l_jours = sorted(st.session_state.planning["Jour"].unique())
        l_scenes = sorted(st.session_state.planning["Scène"].unique())
        if st.button("Générer PDF Planning Global"):
            dico_p = {f"{j} - {s}": st.session_state.planning[(st.session_state.planning["Jour"]==j) & (st.session_state.planning["Scène"]==s)] for j in l_jours for s in l_scenes}
            st.download_button("📥 Télécharger Planning", generer_pdf_complet("PLANNING", dico_p), "planning.pdf")

# ==========================================
# ONGLET 2 : TECHNIQUE
# ==========================================
with main_tabs[1]:
    sub_tabs_tech = st.tabs(["Saisie du matériel", "Patch IN / OUT"])
    
    with sub_tabs_tech[0]:
        if not st.session_state.planning.empty:
            f1, f2, f3 = st.columns(3)
            sel_j = f1.selectbox("📅 Jour", sorted(st.session_state.planning["Jour"].unique()), key="tech_j")
            sel_s = f2.selectbox("🏗️ Scène", st.session_state.planning[st.session_state.planning["Jour"] == sel_j]["Scène"].unique(), key="tech_s")
            sel_a = f3.selectbox("🎸 Groupe", st.session_state.planning[(st.session_state.planning["Jour"] == sel_j) & (st.session_state.planning["Scène"] == sel_s)]["Artiste"].unique(), key="tech_a")
            
            if sel_a:
                # Infos Techniques
                it = st.session_state.infos_techniques.setdefault(sel_a, {"entrees": "", "ear": "", "stereo": "", "mono": ""})
                c_it1, c_it2, c_it3, c_it4 = st.columns(4)
                it["entrees"] = c_it1.text_input("Entrées", it["entrees"], key=f"it1_{sel_a}")
                it["ear"] = c_it2.text_input("EAR", it["ear"], key=f"it2_{sel_a}")
                it["stereo"] = c_it3.text_input("Stéréo", it["stereo"], key=f"it3_{sel_a}")
                it["mono"] = c_it4.text_input("Mono", it["mono"], key=f"it4_{sel_a}")

                # Saisie Matériel
                with st.container(border=True):
                    CAT = st.session_state.custom_catalog
                    c_c, c_m, c_mod, c_q, c_app = st.columns([2, 2, 2, 1, 1])
                    v_cat = c_c.selectbox("Catégorie", list(CAT.keys()) if CAT else ["AUDIO"])
                    v_mar = c_m.selectbox("Marque", list(CAT[v_cat].keys()) if CAT and v_cat in CAT else ["DIVERS"])
                    v_mod = c_mod.selectbox("Modèle", CAT[v_cat][v_mar]) if CAT and v_cat in CAT and v_mar in CAT[v_cat] else c_mod.text_input("Modèle")
                    v_qte = c_q.number_input("Qté", 1, 100, 1)
                    v_app = c_app.checkbox("Artiste Apporte")
                    
                    if st.button("Ajouter"):
                        new_item = pd.DataFrame([{"Scène": sel_s, "Jour": sel_j, "Groupe": sel_a, "Catégorie": v_cat, "Marque": v_mar, "Modèle": v_mod, "Quantité": v_qte, "Artiste_Apporte": v_app}])
                        st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, new_item], ignore_index=True)
                        st.rerun()

                st.subheader(f"Liste matériel : {sel_a}")
                df_curr = st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"] == sel_a]
                ed_tech = st.data_editor(df_curr, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"ed_tech_{sel_a}")
                
                if not ed_tech.equals(df_curr):
                    # Mise à jour propre : on remplace les données de l'artiste
                    st.session_state.fiches_tech = st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"] != sel_a]
                    st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, ed_tech], ignore_index=True)
                    st.rerun()

    with sub_tabs_tech[1]:
        st.subheader("📋 Patch IN / OUT")
        st.info("Section bientôt disponible.")
