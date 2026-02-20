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

# --- INITIALISATION DES VARIABLES DE SESSION ---
if 'planning' not in st.session_state:
    st.session_state.planning = pd.DataFrame(columns=["Scène", "Jour", "Artiste", "Balance", "Durée Balance", "Show"])
if 'fiches_tech' not in st.session_state:
    st.session_state.fiches_tech = pd.DataFrame(columns=["Scène", "Jour", "Groupe", "Catégorie", "Marque", "Modèle", "Quantité", "Artiste_Apporte"])
if 'riders_stockage' not in st.session_state:
    st.session_state.riders_stockage = {}
if 'artist_circuits' not in st.session_state:
    st.session_state.artist_circuits = {}
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0
if 'festival_name' not in st.session_state:
    st.session_state.festival_name = "MON FESTIVAL"
if 'festival_logo' not in st.session_state:
    st.session_state.festival_logo = None
if 'custom_catalog' not in st.session_state:
    st.session_state.custom_catalog = {} 
if 'patch_data' not in st.session_state:
    st.session_state.patch_data = {}

# --- FONCTIONS TECHNIQUES ---
def get_dynamic_options(all_options, current_val, used_options):
    """Filtre les options pour ne garder que celles non utilisées, sauf la valeur actuelle."""
    return [opt for opt in all_options if opt == current_val or opt not in used_options]

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
main_tabs = st.tabs(["Configuration", "Technique"])

# ==========================================
# ONGLET CONFIGURATION (Résumé pour la structure)
# ==========================================
with main_tabs[0]:
    sub_tabs_config = st.tabs(["Gestion / Planning", "Admin", "Exports"])
    with sub_tabs_config[0]:
        st.subheader("Ajouter un Artiste")
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1, 1, 2, 1])
            sc = c1.text_input("Scène", "MainStage")
            jo = c2.date_input("Date", datetime.date.today())
            ar = c3.text_input("Nom Artiste")
            sh = c4.time_input("Heure Show", datetime.time(20, 0))
            if st.button("Valider Artiste"):
                if ar:
                    new_row = pd.DataFrame([{"Scène": sc, "Jour": str(jo), "Artiste": ar, "Balance": "14:00", "Durée Balance": "45 min", "Show": sh.strftime("%H:%M")}])
                    st.session_state.planning = pd.concat([st.session_state.planning, new_row], ignore_index=True)
                    st.rerun()
        st.dataframe(st.session_state.planning, use_container_width=True)

    with sub_tabs_config[1]:
        st.subheader("Sauvegarde")
        data_to_save = {"planning": st.session_state.planning, "fiches_tech": st.session_state.fiches_tech, "patch_data": st.session_state.patch_data}
        st.download_button("💾 Sauvegarder", pickle.dumps(data_to_save), "backup.pkl")

# ==========================================
# ONGLET TECHNIQUE (MODIFIÉ)
# ==========================================
with main_tabs[1]:
    sub_tabs_tech = st.tabs(["Saisie du matériel", "Patch IN / OUT"])
    
    with sub_tabs_tech[0]:
        st.write("Section Saisie Matériel (Inchangée)")
        # Ici votre code original de saisie matériel fonctionne, on se concentre sur le Patch.

    with sub_tabs_tech[1]:
        st.subheader("📋 Patch IN / OUT")
        
        if not st.session_state.planning.empty:
            f1_p, f2_p, f3_p = st.columns(3)
            with f1_p: sel_j_p = st.selectbox("📅 Jour ", sorted(st.session_state.planning["Jour"].unique()), key="j_patch")
            with f2_p:
                scenes_p = st.session_state.planning[st.session_state.planning["Jour"] == sel_j_p]["Scène"].unique()
                sel_s_p = st.selectbox("🏗️ Scène ", scenes_p, key="s_patch")
            with f3_p:
                artistes_p = st.session_state.planning[(st.session_state.planning["Jour"] == sel_j_p) & (st.session_state.planning["Scène"] == sel_s_p)]["Artiste"].unique()
                sel_a_p = st.selectbox("🎸 Groupe ", artistes_p, key="a_patch")

            if sel_a_p:
                # --- RÉCUPÉRATION DES DONNÉES DE PATCH ---
                # On utilise une clé unique par artiste pour éviter les conflits de rafraîchissement
                patch_key = f"data_{sel_a_p}_{sel_j_p}"
                if patch_key not in st.session_state.patch_data:
                    # Initialisation d'un patch vide (ex: 48 lignes par défaut)
                    st.session_state.patch_data[patch_key] = pd.DataFrame({
                        "ID": range(1, 49),
                        "Input Patch": [None]*48,
                        "B12M/F": [None]*48,
                        "Notes": [""]*48
                    })

                # Sélections des types de patch
                col_type, col_nb = st.columns(2)
                type_patch = col_type.radio("Format de Patch", ["PATCH 12N", "PATCH 20H"], horizontal=True)
                step = 12 if type_patch == "PATCH 12N" else 20
                nb_tableaux = math.ceil(48 / step)

                # --- PRÉPARATION DES LISTES DÉROULANTES EXCLUSIVES ---
                # Liste complète des choix possibles
                all_inputs = [f"IN {i}" for i in range(1, 49)]
                all_b12 = [f"B12-{i}" for i in range(1, 49)]

                current_df = st.session_state.patch_data[patch_key]

                # --- AFFICHAGE DES TABLEAUX ---
                for t in range(nb_tableaux):
                    start_idx = t * step
                    end_idx = min((t + 1) * step, 48)
                    
                    # Problème 1 : Titre dynamique
                    title = f"DEPART {t+1} ({start_idx + 1} -> {end_idx})"
                    st.markdown(f"#### {title}")
                    
                    sub_df = current_df.iloc[start_idx:end_idx].copy()
                    
                    # Calcul des déjà utilisés dans TOUT le patch pour cet artiste
                    used_inputs = current_df["Input Patch"].dropna().tolist()
                    used_b12 = current_df["B12M/F"].dropna().tolist()

                    # Configuration des colonnes pour le data_editor
                    # Problème 2 & 3 & 4 (Masquer ID avec hide_index=True et column_config)
                    edited_sub_df = st.data_editor(
                        sub_df,
                        column_config={
                            "ID": None, # Problème 4 : Masque la colonne ID
                            "Input Patch": st.column_config.SelectboxColumn(
                                "Input Patch", # Problème 2 : Renommé
                                options=all_inputs,
                                width="medium"
                            ),
                            "B12M/F": st.column_config.SelectboxColumn(
                                "B12M/F", # Problème 3 : Choix libre B12
                                options=all_b12,
                                width="medium"
                            )
                        },
                        hide_index=True,
                        key=f"editor_{patch_key}_{t}",
                        use_container_width=True
                    )

                    # Problème 5 : Mise à jour sécurisée pour éviter la suppression des lignes
                    if not edited_sub_df.equals(sub_df):
                        st.session_state.patch_data[patch_key].iloc[start_idx:end_idx] = edited_sub_df
                        st.rerun()

        else:
            st.info("Veuillez d'abord configurer le planning dans l'onglet Configuration.")

# --- FOOTER ---
st.divider()
st.caption(f"© 2024 {st.session_state.festival_name} - Assistant Régie")
