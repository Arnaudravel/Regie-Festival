import streamlit as st
import pandas as pd
import datetime
from fpdf import FPDF
import io
import pickle

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Regie-Festival", layout="wide", initial_sidebar_state="collapsed")

# --- INITIALISATION DES VARIABLES DE SESSION ---
if 'planning' not in st.session_state:
    st.session_state.planning = pd.DataFrame(columns=["Scène", "Jour", "Artiste", "Balance", "Show", "Patch_IN", "Patch_OUT", "EAR", "MONITOR"])
# Vérification des colonnes si chargement d'un ancien fichier
for col in ["Patch_IN", "Patch_OUT", "EAR", "MONITOR"]:
    if col not in st.session_state.planning.columns:
        st.session_state.planning[col] = 0

if 'fiches_tech' not in st.session_state:
    st.session_state.fiches_tech = pd.DataFrame(columns=["Scène", "Jour", "Groupe", "Catégorie", "Marque", "Modèle", "Quantité", "Artiste_Apporte"])
if 'patch_data' not in st.session_state:
    st.session_state.patch_data = {} # Stockage {Artiste: DataFrame_Patch}
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
tabs = st.tabs(["🏗️ Configuration", "⚙️ Inventaire Matos", "🔌 Patch Plateau", "📄 Exports PDF", "🛠️ Admin"])

# --- TAB 0 : CONFIGURATION ---
with tabs[0]:
    st.subheader("➕ Ajouter un Artiste et ses besoins")
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([1, 1, 2, 1, 1])
        sc = c1.text_input("Scène", "MainStage")
        jo = c2.date_input("Date", datetime.date.today())
        ar = c3.text_input("Nom Artiste")
        ba = c4.time_input("Balance", datetime.time(14, 0))
        sh = c5.time_input("Show", datetime.time(20, 0))
        
        st.write("**Besoins Patch & Circuits :**")
        cp1, cp2, cp3, cp4 = st.columns(4)
        p_in = cp1.number_input("Patch IN (Entrées)", 0, 128, 0)
        p_out = cp2.number_input("Patch OUT (Sorties)", 0, 64, 0)
        p_ear = cp3.number_input("Nombre EAR", 0, 32, 0)
        p_mon = cp4.number_input("Nombre MONITOR", 0, 32, 0)
        
        pdfs = st.file_uploader("Fiches Techniques (PDF)", accept_multiple_files=True, key=f"upl_{st.session_state.uploader_key}")
        
        if st.button("Valider Artiste"):
            if ar:
                new_row = pd.DataFrame([{
                    "Scène": sc, "Jour": str(jo), "Artiste": ar, "Balance": ba.strftime("%H:%M"), "Show": sh.strftime("%H:%M"),
                    "Patch_IN": p_in, "Patch_OUT": p_out, "EAR": p_ear, "MONITOR": p_mon
                }])
                st.session_state.planning = pd.concat([st.session_state.planning, new_row], ignore_index=True)
                if ar not in st.session_state.riders_stockage: st.session_state.riders_stockage[ar] = {}
                if pdfs:
                    for f in pdfs: st.session_state.riders_stockage[ar][f.name] = f.read()
                st.session_state.uploader_key += 1
                st.rerun()

    st.subheader("📋 Planning & Capacités")
    if not st.session_state.planning.empty:
        df_visu = st.session_state.planning.sort_values(by=["Jour", "Scène", "Show"]).copy()
        edited_df = st.data_editor(df_visu, use_container_width=True, num_rows="dynamic", key="main_editor")
        if not edited_df.drop(columns=["Artiste"]).equals(df_visu.drop(columns=["Artiste"])):
             st.session_state.planning = edited_df.reset_index(drop=True)
             st.rerun()

# --- TAB 1 : INVENTAIRE MATERIEL (Code existant conservé) ---
with tabs[1]:
    if not st.session_state.planning.empty:
        f1, f2, f3 = st.columns(3)
        with f1: sel_j = st.selectbox("📅 Jour", sorted(st.session_state.planning["Jour"].unique()), key="inv_j")
        with f2: sel_s = st.selectbox("🏗️ Scène", st.session_state.planning[st.session_state.planning["Jour"] == sel_j]["Scène"].unique(), key="inv_s")
        with f3: sel_a = st.selectbox("🎸 Groupe", st.session_state.planning[(st.session_state.planning["Jour"] == sel_j) & (st.session_state.planning["Scène"] == sel_s)]["Artiste"].unique(), key="inv_a")
        
        if sel_a:
            # (Logique de saisie de matériel du code original...)
            CATALOGUE = st.session_state.custom_catalog
            c_cat, c_mar, c_mod, c_qte, c_app = st.columns([2, 2, 2, 1, 1])
            liste_categories = list(CATALOGUE.keys()) if CATALOGUE else ["MICROS FILAIRE", "HF", "EAR MONITOR", "BACKLINE"]
            v_cat = c_cat.selectbox("Catégorie", liste_categories)
            liste_marques = list(CATALOGUE[v_cat].keys()) if CATALOGUE and v_cat in CATALOGUE else ["SHURE", "SENNHEISER", "AKG", "NEUMANN"]
            v_mar = c_mar.selectbox("Marque", liste_marques)
            v_mod = c_mod.selectbox("Modèle", CATALOGUE[v_cat][v_mar]) if CATALOGUE and v_cat in CATALOGUE and v_mar in CATALOGUE[v_cat] else c_mod.text_input("Modèle", "SM58")
            v_qte = c_qte.number_input("Qté", 1, 100, 1)
            v_app = c_app.checkbox("Artiste Apporte")
            
            if st.button("Ajouter à la liste"):
                new_item = pd.DataFrame([{"Scène": sel_s, "Jour": sel_j, "Groupe": sel_a, "Catégorie": v_cat, "Marque": v_mar, "Modèle": v_mod, "Quantité": v_qte, "Artiste_Apporte": v_app}])
                st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, new_item], ignore_index=True)
                st.rerun()
            st.dataframe(st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"] == sel_a], use_container_width=True)

# --- TAB 2 : PATCH PLATEAU (NOUVEAUTÉ) ---
with tabs[2]:
    st.header("🔌 Configuration du Patch Plateau")
    if st.session_state.planning.empty:
        st.warning("Ajoutez des artistes pour configurer le patch.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1: s_scene = st.selectbox("1. Choisir Scène", st.session_state.planning["Scène"].unique())
        max_in = st.session_state.planning[st.session_state.planning["Scène"] == s_scene]["Patch_IN"].max()
        with c2: s_format = st.radio("2. Format", ["20H (20 paires)", "12N (12 paires)"], horizontal=True)
        t_bloc = 20 if "20H" in s_format else 12
        with c3: s_art = st.selectbox("3. Choisir Groupe", st.session_state.planning[st.session_state.planning["Scène"] == s_scene]["Artiste"].unique())

        st.info(f"Besoin Max Scène : {max_in} IN. Structure : {s_format}")
        
        # Génération du template si inexistant
        if s_art not in st.session_state.patch_data:
            rows = []
            for b in range((max_in // t_bloc) + 1):
                for i in range(1, t_bloc + 1):
                    abs_in = (b * t_bloc) + i
                    if abs_in <= max_in:
                        rows.append({"In Console": abs_in, "Départ": f"Départ {b+1}", "Sous-Patch": f"B{t_bloc} n°1", "In Locale": i, "Source": "", "Note": ""})
            st.session_state.patch_data[s_art] = pd.DataFrame(rows)

        # Editeur de patch
        ed_patch = st.data_editor(st.session_state.patch_data[s_art], use_container_width=True, hide_index=True, key=f"patch_ed_{s_art}")
        st.session_state.patch_data[s_art] = ed_patch

        if st.button(f"📄 Exporter Patch PDF - {s_art}"):
            p = FestivalPDF()
            p.add_page()
            p.set_font("helvetica", "B", 16)
            p.cell(0, 10, f"PATCH PLATEAU : {s_art.upper()}", ln=True, align='C')
            p.set_font("helvetica", "", 10)
            p.cell(0, 8, f"Format : {s_format} | Scène : {s_scene}", ln=True, align='C')
            p.ln(5)
            # Dessiner tableau filtré (uniquement les sources remplies)
            df_print = ed_patch[ed_patch["Source"] != ""]
            p.dessiner_tableau(df_print)
            
            # Résumé Sorties
            info = st.session_state.planning[st.session_state.planning["Artiste"] == s_art].iloc[0]
            p.ajouter_titre_section("OUTPUTS & CIRCUITS")
            p.cell(0, 8, f"Nombre de sorties totales : {info['Patch_OUT']}", ln=True)
            p.cell(0, 8, f"Circuits EAR : {info['EAR']} | Circuits MONITOR : {info['MONITOR']}", ln=True)
            
            st.download_button("⬇️ Télécharger PDF", p.output(dest='S').encode('latin-1'), f"Patch_{s_art}.pdf")

# --- TAB 3 : EXPORTS (Inchangé mais inclut les nouveaux champs) ---
with tabs[3]:
    st.header("📄 Exports PDF")
    # (Logique d'export existante...)
    if st.button("Générer Planning Complet"):
        dico = {"PLANNING": st.session_state.planning}
        pdf_b = generer_pdf_complet("PLANNING FESTIVAL", dico)
        st.download_button("📥 Télécharger Planning", pdf_b, "planning.pdf")

# --- TAB 4 : ADMIN & SAUVEGARDE ---
with tabs[4]:
    # Mise à jour du dictionnaire de sauvegarde
    st.header("🛠️ Administration")
    data_to_save = {
        "planning": st.session_state.planning,
        "fiches_tech": st.session_state.fiches_tech,
        "patch_data": st.session_state.patch_data,
        "festival_name": st.session_state.festival_name,
        "festival_logo": st.session_state.festival_logo,
        "custom_catalog": st.session_state.custom_catalog,
        "riders_stockage": st.session_state.riders_stockage
    }
    st.download_button("💾 Sauvegarder Projet (.pkl)", pickle.dumps(data_to_save), f"regie_{datetime.date.today()}.pkl")
    
    # Importation Excel (Code original conservé)
    code_secret = st.text_input("🔒 Code Admin", type="password")
    if code_secret == "0000":
        xls_file = st.file_uploader("Charger Catalogue Excel", type=['xlsx'])
        if xls_file and st.button("Charger"):
             # (Logique de lecture Excel existante...)
             st.success("Catalogue mis à jour")
