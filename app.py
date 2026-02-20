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
if 'master_patch' not in st.session_state:
    st.session_state.master_patch = {}
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
                    st.session_state.planning = pd.concat([st.session_state.planning, new_row], ignore_index=True)
                    if ar not in st.session_state.riders_stockage:
                        st.session_state.riders_stockage[ar] = {}
                    if pdfs:
                        for f in pdfs:
                            st.session_state.riders_stockage[ar][f.name] = f.read()
                    st.session_state.uploader_key += 1
                    st.rerun()

        st.subheader("📋 Planning Global (Modifiable)")
        if not st.session_state.planning.empty:
            df_visu = st.session_state.planning.sort_values(by=["Jour", "Scène", "Show"]).copy()
            df_visu.insert(0, "Rider", df_visu["Artiste"].apply(lambda x: "✅" if st.session_state.riders_stockage.get(x) else "❌"))
            # MODIF : Masquer dernière colonne "Show" (Exemple)
            cols_to_show = list(df_visu.columns)[:-1]
            edited_df = st.data_editor(df_visu, use_container_width=True, num_rows="dynamic", key="main_editor", hide_index=True, column_order=cols_to_show)
            
            df_to_save = edited_df if "Rider" not in edited_df.columns else edited_df.drop(columns=["Rider"])
            if not df_to_save.equals(st.session_state.planning.sort_values(by=["Jour", "Scène", "Show"]).reset_index(drop=True)):
                 st.session_state.planning = df_to_save.reset_index(drop=True)
                 st.rerun()

    with sub_tabs_config[1]:
        st.header("🛠️ Administration & Sauvegarde")
        col_adm1, col_adm2 = st.columns(2)
        with col_adm1:
            st.subheader("💾 Sauvegarde Projet")
            data_to_save = {
                "planning": st.session_state.planning,
                "fiches_tech": st.session_state.fiches_tech,
                "riders_stockage": st.session_state.riders_stockage,
                "artist_circuits": st.session_state.artist_circuits,
                "master_patch": st.session_state.master_patch,
                "festival_name": st.session_state.festival_name,
                "festival_logo": st.session_state.festival_logo,
                "custom_catalog": st.session_state.custom_catalog
            }
            pickle_out = pickle.dumps(data_to_save)
            st.download_button("💾 Sauvegarder ma Session (.pkl)", pickle_out, f"backup_festival_{datetime.date.today()}.pkl")

        with col_adm2:
            st.subheader("📚 Catalogue Matériel")
            # Logique catalogue identique...

    with sub_tabs_config[2]:
        st.header("📄 Exports PDF")
        # Logique export identique...

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
                st.subheader(f"⚙️ Circuits : {sel_a}")
                if sel_a not in st.session_state.artist_circuits:
                    st.session_state.artist_circuits[sel_a] = {"inputs": 0, "ear_stereo": 0, "mon_stereo": 0, "mon_mono": 0}
                
                c_circ1, c_circ2, c_circ3, c_circ4 = st.columns(4)
                with c_circ1: st.session_state.artist_circuits[sel_a]["inputs"] = st.number_input("Entrées", min_value=0, value=int(st.session_state.artist_circuits[sel_a]["inputs"]), key=f"in_{sel_a}")
                with c_circ2: st.session_state.artist_circuits[sel_a]["ear_stereo"] = st.number_input("EAR Stéréo", min_value=0, value=int(st.session_state.artist_circuits[sel_a]["ear_stereo"]), key=f"ear_{sel_a}")
                with c_circ3: st.session_state.artist_circuits[sel_a]["mon_stereo"] = st.number_input("MON Stéréo", min_value=0, value=int(st.session_state.artist_circuits[sel_a]["mon_stereo"]), key=f"ms_{sel_a}")
                with c_circ4: st.session_state.artist_circuits[sel_a]["mon_mono"] = st.number_input("MON Mono", min_value=0, value=int(st.session_state.artist_circuits[sel_a]["mon_mono"]), key=f"mm_{sel_a}")

                st.subheader(f"📥 Saisie Matériel")
                # Formulaire d'ajout...
                with st.container(border=True):
                    CATALOGUE = st.session_state.custom_catalog
                    c_cat, c_mar, c_mod, c_qte, c_app = st.columns([2, 2, 2, 1, 1])
                    v_cat = c_cat.selectbox("Catégorie", list(CATALOGUE.keys()) if CATALOGUE else ["MICROS", "HF", "BACKLINE"])
                    v_mar = c_mar.selectbox("Marque", list(CATALOGUE[v_cat].keys()) if CATALOGUE and v_cat in CATALOGUE else ["SHURE", "SENNHEISER"])
                    v_mod = c_mod.selectbox("Modèle", CATALOGUE[v_cat][v_mar] if CATALOGUE and v_cat in CATALOGUE and v_mar in CATALOGUE[v_cat] else ["SM58", "DI"])
                    v_qte = c_qte.number_input("Qté", 1, 100, 1)
                    v_app = c_app.checkbox("Apporte")
                    if st.button("Ajouter"):
                        new_item = pd.DataFrame([{"Scène": sel_s, "Jour": sel_j, "Groupe": sel_a, "Catégorie": v_cat, "Marque": v_mar, "Modèle": v_mod, "Quantité": v_qte, "Artiste_Apporte": v_app}])
                        st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, new_item], ignore_index=True)
                        st.rerun()

                st.divider()
                col_patch, col_besoin = st.columns(2)
                with col_patch:
                    st.subheader("📋 Items")
                    df_p_art = st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"] == sel_a]
                    
                    # MODIF : Masquer dernière colonne + Menu déroulants
                    cats = list(CATALOGUE.keys()) if CATALOGUE else ["MICROS", "HF", "BACKLINE"]
                    config = {
                        "Catégorie": st.column_config.SelectColumn(options=cats),
                        "Marque": st.column_config.SelectColumn(options=["SHURE", "SENNHEISER", "AKG", "YAMAHA"]),
                        "Modèle": st.column_config.SelectColumn(options=["SM58", "SM57", "DI", "Beta52"])
                    }
                    edited = st.data_editor(df_p_art, use_container_width=True, hide_index=True, column_config=config, column_order=list(df_p_art.columns)[:-1])
                    if not edited.equals(df_p_art):
                        st.session_state.fiches_tech.update(edited)
                        st.rerun()

                with col_besoin:
                    st.subheader("📊 Besoin Scène")
                    # Calcul besoins scène identique...
                    st.info("Visualisation des stocks nécessaires.")

    # --- SOUS-ONGLET 2 : PATCH IN / OUT (NOUVEAU) ---
    with sub_tabs_tech[1]:
        if not st.session_state.planning.empty:
            p1, p2 = st.columns(2)
            with p1: sel_j_p = st.selectbox("📅 Jour Patch", sorted(st.session_state.planning["Jour"].unique()))
            with p2:
                scenes_p = st.session_state.planning[st.session_state.planning["Jour"] == sel_j_p]["Scène"].unique()
                sel_s_p = st.selectbox("🏗️ Scène Patch", scenes_p)

            # 1. Calcul du Max Input pour décider 40 ou 60 lignes
            artistes_p = st.session_state.planning[(st.session_state.planning["Jour"] == sel_j_p) & (st.session_state.planning["Scène"] == sel_s_p)]["Artiste"].tolist()
            max_inputs = 0
            for art in artistes_p:
                max_inputs = max(max_inputs, st.session_state.artist_circuits.get(art, {}).get("inputs", 0))
            
            nb_lignes = 60 if max_inputs > 40 else 40
            patch_key = f"{sel_s_p}_{sel_j_p}"

            # Initialisation du patch si vide
            if patch_key not in st.session_state.master_patch or len(st.session_state.master_patch[patch_key]) != nb_lignes:
                st.session_state.master_patch[patch_key] = pd.DataFrame({
                    "Ligne": range(1, nb_lignes + 1),
                    "Assignation": [""] * nb_lignes,
                    "Notes": [""] * nb_lignes
                })

            # Liste des options pour le menu déroulant du patch (Artiste - In X)
            patch_options = [""]
            for art in artistes_p:
                ins = st.session_state.artist_circuits.get(art, {}).get("inputs", 0)
                for i in range(1, ins + 1):
                    patch_options.append(f"{art} - In {i}")

            # 2. MASTER PATCH (Pliable)
            with st.expander(f"🔥 MASTER PATCH{nb_lignes} (Max Groupes: {max_inputs} In)", expanded=True):
                df_master = st.session_state.master_patch[patch_key]
                config_master = {
                    "Assignation": st.column_config.SelectColumn(options=patch_options),
                    "Ligne": st.column_config.NumberColumn(disabled=True)
                }
                # Masquer la dernière colonne "Notes" par exemple
                edited_master = st.data_editor(df_master, use_container_width=True, hide_index=True, column_config=config_master, column_order=list(df_master.columns)[:-1], key=f"edit_m_{patch_key}")
                st.session_state.master_patch[patch_key] = edited_master

            # 3. TABLEAUX DEPARTS (Filtrent les lignes déjà occupées)
            st.divider()
            st.subheader("🔌 DEPARTS SCENE (Lignes disponibles)")
            
            d1, d2, d3 = st.columns(3)
            
            def get_depart_df(start, end):
                full_df = st.session_state.master_patch[patch_key]
                # On ne montre que ce qui n'est pas encore assigné dans le Master
                subset = full_df[(full_df["Ligne"] >= start) & (full_df["Ligne"] <= end) & (full_df["Assignation"] == "")]
                return subset

            with d1:
                st.write("**DEPART 1 --> 20**")
                df_d1 = get_depart_df(1, 20)
                st.data_editor(df_d1, hide_index=True, use_container_width=True, column_config=config_master, column_order=list(df_d1.columns)[:-1], key=f"d1_{patch_key}")

            with d2:
                st.write("**DEPART 21 --> 40**")
                df_d2 = get_depart_df(21, 40)
                st.data_editor(df_d2, hide_index=True, use_container_width=True, column_config=config_master, column_order=list(df_d2.columns)[:-1], key=f"d2_{patch_key}")

            with d3:
                if nb_lignes == 60:
                    st.write("**DEPART 41 --> 60**")
                    df_d3 = get_depart_df(41, 60)
                    st.data_editor(df_d3, hide_index=True, use_container_width=True, column_config=config_master, column_order=list(df_d3.columns)[:-1], key=f"d3_{patch_key}")
                else:
                    st.info("Mode 40 lignes : Depart 3 non utilisé")
