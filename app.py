import streamlit as st
import pandas as pd
import datetime
from fpdf import FPDF
import io
import pickle
import base64
import streamlit.components.v1 as components
import math

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
if 'riders_stockage' not in st.session_state:
    st.session_state.riders_stockage = {}
if 'artist_circuits' not in st.session_state:
    st.session_state.artist_circuits = {}
if 'patch_data' not in st.session_state:
    st.session_state.patch_data = {}
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

# --- FONCTION TECHNIQUE POUR LE RENDU PDF ---
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

# --- INTERFACE PRINCIPALE ---
st.title(f"{st.session_state.festival_name} - Gestion Régie")

# --- CREATION DES ONGLETS PRINCIPAUX ---
main_tabs = st.tabs(["Configuration", "Technique"])

# ==========================================
# ONGLET 1 : CONFIGURATION
# ==========================================
with main_tabs[0]:
    sub_tabs_config = st.tabs(["Gestion / Planning des Artistes", "Admin & Sauvegarde", "Exports PDF"])
    
    # --- SOUS-ONGLET 1 : GESTION / PLANNING ---
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
                if opt_balance:
                    ba = st.time_input("Heure Balance", datetime.time(14, 0))
                else:
                    ba = None
                    st.info("Pas de balance")
            
            with col_d_bal:
                if opt_balance:
                    du = st.text_input("Durée Balance", "45 min")
                else:
                    du = ""

            pdfs = st.file_uploader("Fiches Techniques (PDF)", accept_multiple_files=True, key=f"upl_{st.session_state.uploader_key}")
            
            if st.button("Valider Artiste"):
                if ar:
                    val_ba = ba.strftime("%H:%M") if ba and opt_balance else ""
                    val_du = du if opt_balance else ""
                    new_row = pd.DataFrame([{
                        "Scène": sc, 
                        "Jour": str(jo), 
                        "Artiste": ar, 
                        "Balance": val_ba,
                        "Durée Balance": val_du, 
                        "Show": sh.strftime("%H:%M")
                    }])
                    if "Durée Balance" not in st.session_state.planning.columns:
                         st.session_state.planning["Durée Balance"] = ""
                    st.session_state.planning = pd.concat([st.session_state.planning, new_row], ignore_index=True)
                    if ar not in st.session_state.riders_stockage:
                        st.session_state.riders_stockage[ar] = {}
                    if pdfs:
                        for f in pdfs:
                            st.session_state.riders_stockage[ar][f.name] = f.read()
                    st.session_state.uploader_key += 1
                    st.rerun()

        st.subheader("📋 Planning Global (Modifiable)")
        if st.session_state.delete_confirm_idx is not None:
            idx = st.session_state.delete_confirm_idx
            with st.status("⚠️ Confirmation de suppression", expanded=True):
                st.write(f"Supprimer définitivement l'artiste : **{st.session_state.planning.iloc[idx]['Artiste']}** ?")
                col_cfg1, col_cfg2 = st.columns(2)
                if col_cfg1.button("✅ OUI, Supprimer", use_container_width=True):
                    nom_art = st.session_state.planning.iloc[idx]['Artiste']
                    st.session_state.planning = st.session_state.planning.drop(idx).reset_index(drop=True)
                    if nom_art in st.session_state.riders_stockage: del st.session_state.riders_stockage[nom_art]
                    st.session_state.delete_confirm_idx = None
                    st.rerun()
                if col_cfg2.button("❌ Annuler", use_container_width=True):
                    st.session_state.delete_confirm_idx = None
                    st.rerun()

        if not st.session_state.planning.empty:
            if "Durée Balance" not in st.session_state.planning.columns:
                st.session_state.planning["Durée Balance"] = ""
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

    # --- SOUS-ONGLET 2 : ADMIN & SAUVEGARDE ---
    with sub_tabs_config[1]:
        st.header("🛠️ Administration & Sauvegarde")
        col_adm1, col_adm2 = st.columns(2)
        with col_adm1:
            st.subheader("🆔 Identité Festival")
            with st.container(border=True):
                new_name = st.text_input("Nom du Festival", st.session_state.festival_name)
                if new_name != st.session_state.festival_name:
                    st.session_state.festival_name = new_name
                    st.rerun()
                new_logo = st.file_uploader("Logo du Festival (Image)", type=['png', 'jpg', 'jpeg'])
                if new_logo:
                    st.session_state.festival_logo = new_logo.read()
                    st.success("Logo chargé !")
            st.subheader("💾 Sauvegarde Projet")
            with st.container(border=True):
                data_to_save = {
                    "planning": st.session_state.planning,
                    "fiches_tech": st.session_state.fiches_tech,
                    "riders_stockage": st.session_state.riders_stockage,
                    "artist_circuits": st.session_state.artist_circuits,
                    "festival_name": st.session_state.festival_name,
                    "festival_logo": st.session_state.festival_logo,
                    "custom_catalog": st.session_state.custom_catalog,
                    "patch_data": st.session_state.patch_data
                }
                pickle_out = pickle.dumps(data_to_save)
                st.download_button("💾 Sauvegarder ma Session (.pkl)", pickle_out, f"backup_festival_{datetime.date.today()}.pkl")
                st.divider()
                uploaded_session = st.file_uploader("📂 Charger une sauvegarde (.pkl)", type=['pkl'])
                if uploaded_session:
                    if st.button("Restaurer la sauvegarde"):
                        data_loaded = pickle.loads(uploaded_session.read())
                        st.session_state.planning = data_loaded.get("planning", pd.DataFrame())
                        st.session_state.fiches_tech = data_loaded.get("fiches_tech", pd.DataFrame())
                        st.session_state.riders_stockage = data_loaded.get("riders_stockage", {})
                        st.session_state.artist_circuits = data_loaded.get("artist_circuits", {})
                        st.session_state.festival_name = data_loaded.get("festival_name", "Mon Festival")
                        st.session_state.festival_logo = data_loaded.get("festival_logo", None)
                        st.session_state.custom_catalog = data_loaded.get("custom_catalog", {})
                        st.session_state.patch_data = data_loaded.get("patch_data", {})
                        st.rerun()

        with col_adm2:
            st.subheader("📚 Catalogue Matériel (Excel)")
            code_secret = st.text_input("🔒 Code Admin", type="password")
            if code_secret == "0000":
                with st.container(border=True):
                    xls_file = st.file_uploader("Fichier Excel Items", type=['xlsx', 'xls'])
                    if xls_file:
                        if st.button("Analyser et Charger le Catalogue"):
                            try:
                                xls = pd.ExcelFile(xls_file)
                                new_catalog = {}
                                for sheet in xls.sheet_names:
                                    df = pd.read_excel(xls, sheet_name=sheet)
                                    brands = df.columns.tolist()
                                    new_catalog[sheet] = {}
                                    for brand in brands:
                                        modeles = df[brand].dropna().astype(str).tolist()
                                        if modeles:
                                            new_catalog[sheet][brand] = modeles
                                st.session_state.custom_catalog = new_catalog
                                st.success(f"Catalogue chargé !")
                            except Exception as e:
                                st.error(f"Erreur lecture Excel : {e}")

    # --- SOUS-ONGLET 3 : EXPORTS PDF ---
    with sub_tabs_config[2]:
        st.header("📄 Génération des Exports PDF")
        if not st.session_state.planning.empty:
            l_jours = sorted(st.session_state.planning["Jour"].unique())
            l_scenes = sorted(st.session_state.planning["Scène"].unique())
            # (Reste du code d'export PDF identique...)

# ==========================================
# ONGLET 2 : TECHNIQUE
# ==========================================
with main_tabs[1]:
    sub_tabs_tech = st.tabs(["Saisie du matériel", "Patch IN / OUT"])
    
    # --- SOUS-ONGLET 1 : SAISIE MATERIEL ---
    with sub_tabs_tech[0]:
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
                st.divider()
                st.subheader(f"⚙️ Configuration des circuits : {sel_a}")
                if sel_a not in st.session_state.artist_circuits:
                    st.session_state.artist_circuits[sel_a] = {"inputs": 48, "ear_stereo": 4, "mon_stereo": 2, "mon_mono": 4}
                
                c_circ1, c_circ2, c_circ3, c_circ4 = st.columns(4)
                st.session_state.artist_circuits[sel_a]["inputs"] = c_circ1.number_input("Circuits d'entrées", 0, 128, int(st.session_state.artist_circuits[sel_a]["inputs"]), key=f"in_{sel_a}")
                st.session_state.artist_circuits[sel_a]["ear_stereo"] = c_circ2.number_input("EAR (Stéréo)", 0, 32, int(st.session_state.artist_circuits[sel_a]["ear_stereo"]), key=f"ear_{sel_a}")
                st.session_state.artist_circuits[sel_a]["mon_stereo"] = c_circ3.number_input("MON (Stéréo)", 0, 32, int(st.session_state.artist_circuits[sel_a]["mon_stereo"]), key=f"ms_{sel_a}")
                st.session_state.artist_circuits[sel_a]["mon_mono"] = c_circ4.number_input("MON (Mono)", 0, 32, int(st.session_state.artist_circuits[sel_a]["mon_mono"]), key=f"mm_{sel_a}")

                # Logique Saisie Matériel (déjà présente dans ton code)
                # ... [Code de saisie des items déjà existant] ...

    # --- SOUS-ONGLET 2 : PATCH IN / OUT (RECTIFIE) ---
    with sub_tabs_tech[1]:
        if not st.session_state.planning.empty:
            # Sélections globales identiques à la saisie
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                sel_a_patch = st.selectbox("Choisir l'Artiste à Patcher", st.session_state.planning["Artiste"].unique())
            
            if sel_a_patch:
                circuits = st.session_state.artist_circuits.get(sel_a_patch, {"inputs": 48, "ear_stereo": 4, "mon_stereo": 2, "mon_mono": 4})
                
                # --- PATCH INPUTS ---
                st.markdown(f"### 📥 PATCH INPUTS - {sel_a_patch}")
                
                # Initialisation si vide
                if sel_a_patch not in st.session_state.patch_data:
                    st.session_state.patch_data[sel_a_patch] = {
                        "inputs": pd.DataFrame([{"CH": i+1, "SOURCE": "", "MICRO": "", "INSERT": "", "PIED": "", "48V": False} for i in range(circuits["inputs"])]),
                        "outputs": pd.DataFrame([{"OUT": i+1, "DESTINATION": "", "TYPE": "12N", "FORMAT": "Mono"} for i in range(12)]) # Exemple par défaut
                    }
                
                # Affichage tableau INPUTS
                df_in = st.session_state.patch_data[sel_a_patch]["inputs"]
                # On ajuste la taille si l'utilisateur a changé le nombre d'entrées dans l'onglet précédent
                if len(df_in) != circuits["inputs"]:
                    new_len = circuits["inputs"]
                    if new_len > len(df_in):
                        added = pd.DataFrame([{"CH": i+1, "SOURCE": "", "MICRO": "", "INSERT": "", "PIED": "", "48V": False} for i in range(len(df_in), new_len)])
                        df_in = pd.concat([df_in, added], ignore_index=True)
                    else:
                        df_in = df_in.iloc[:new_len]
                
                edited_in = st.data_editor(df_in, use_container_width=True, hide_index=True, key=f"patch_in_ed_{sel_a_patch}")
                st.session_state.patch_data[sel_a_patch]["inputs"] = edited_in

                st.divider()

                # --- PATCH OUTPUTS (AVEC OPTIONS 12N, 20H) ---
                st.markdown(f"### 📤 PATCH OUTPUTS - {sel_a_patch}")
                
                # Configuration des sorties basée sur les circuits saisis
                total_outs = circuits["ear_stereo"] + circuits["mon_stereo"] + circuits["mon_mono"]
                df_out = st.session_state.patch_data[sel_a_patch]["outputs"]
                
                # Correction / Mise à jour automatique des lignes de sortie
                # (On génère une liste de types basée sur les besoins : EAR, MON, etc.)
                types_list = (["EAR (Stéréo)"] * circuits["ear_stereo"] + 
                              ["MON (Stéréo)"] * circuits["mon_stereo"] + 
                              ["MON (Mono)"] * circuits["mon_mono"])
                
                if len(df_out) != len(types_list):
                    df_out = pd.DataFrame({
                        "OUT": [i+1 for i in range(len(types_list))],
                        "DESTINATION": [""] * len(types_list),
                        "TYPE": ["12N"] * len(types_list), # Option par défaut réintégrée
                        "FORMAT": types_list
                    })

                # Configuration des colonnes pour inclure 12N et 20H
                edited_out = st.data_editor(
                    df_out, 
                    use_container_width=True, 
                    hide_index=True, 
                    key=f"patch_out_ed_{sel_a_patch}",
                    column_config={
                        "TYPE": st.column_config.SelectboxColumn(
                            "Type Boitier / Connecteur",
                            options=["12N", "20H", "XLR Direct", "Combo", "Multibroche"],
                            help="Sélectionnez l'option de sortie (12N et 20H disponibles)"
                        )
                    }
                )
                st.session_state.patch_data[sel_a_patch]["outputs"] = edited_out
        else:
            st.warning("Veuillez d'abord ajouter des artistes dans le Planning.")

# --- FIN DU CODE ---
