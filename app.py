import streamlit as st
import pandas as pd
from fpdf import FPDF
from PIL import Image
import base64
import io
import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Regie-Festival", layout="wide")

# Initialisation des variables de session
if 'planning' not in st.session_state:
    st.session_state.planning = pd.DataFrame(columns=["Scène", "Jour", "Artiste", "Balance", "Show"])
if 'fiches_tech' not in st.session_state:
    st.session_state.fiches_tech = pd.DataFrame(columns=["Scène", "Jour", "Groupe", "Catégorie", "Marque", "Modèle", "Quantité", "Artiste_Apporte"])
if 'riders_stockage' not in st.session_state:
    st.session_state.riders_stockage = {}
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- FONCTION POP-UP DE CONFIRMATION ---
@st.dialog("Confirmation de suppression")
def confirmer_suppression(index_to_del):
    artiste_nom = st.session_state.planning.iloc[index_to_del]["Artiste"]
    st.warning(f"Êtes-vous sûr de vouloir supprimer le groupe **{artiste_nom}** ?")
    
    col1, col2 = st.columns(2)
    if col1.button("✅ Oui, supprimer", use_container_width=True):
        # Suppression effective
        nom_artiste = st.session_state.planning.iloc[index_to_del]["Artiste"]
        st.session_state.planning = st.session_state.planning.drop(index_to_del).reset_index(drop=True)
        # Nettoyage des riders si nécessaire
        if nom_artiste in st.session_state.riders_stockage:
            del st.session_state.riders_stockage[nom_artiste]
        st.rerun()
    
    if col2.button("❌ Annuler", use_container_width=True):
        st.rerun()

# --- FONCTIONS PDF ---
class FestivalPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, "Rapport Régie Festival", 0, 1, 'C')
        self.ln(10)

def generer_pdf(df, titre):
    pdf = FestivalPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, titre, ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", '', 10)
    for i, r in df.iterrows():
        pdf.cell(0, 7, f"{str(r.to_dict())}", ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFACE ---
st.title("Nouveau Festival")

tabs = st.tabs(["🏗️ Configuration", "⚙️ Patch & Régie", "📄 Exports PDF"])

# --- ONGLET 1 : CONFIGURATION ---
with tabs[0]:
    st.subheader("➕ Ajouter un Artiste")
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([1, 1, 2, 1, 1])
        sc = c1.text_input("Scène", "MainStage")
        jo = c2.date_input("Date de passage", datetime.date.today())
        ar = c3.text_input("Nom Artiste")
        ba = c4.time_input("Balance", datetime.time(14, 0))
        sh = c5.time_input("Show", datetime.time(20, 0))
        
        # Reset automatique du PDF après ajout
        pdfs = st.file_uploader("Fiches Techniques (PDF)", accept_multiple_files=True, key=f"upl_{st.session_state.uploader_key}")
        
        if st.button("Valider Artiste"):
            if ar:
                new_row = pd.DataFrame([{"Scène": sc, "Jour": str(jo), "Artiste": ar, "Balance": ba.strftime("%H:%M"), "Show": sh.strftime("%H:%M")}])
                st.session_state.planning = pd.concat([st.session_state.planning, new_row], ignore_index=True)
                if pdfs:
                    st.session_state.riders_stockage[ar] = {f.name: f.read() for f in pdfs}
                st.session_state.uploader_key += 1 # Change la clé pour vider le uploader
                st.rerun()

    st.subheader("📋 Planning Global")
    if not st.session_state.planning.empty:
        # Préparation des données pour l'éditeur
        df_visu = st.session_state.planning.copy()
        df_visu.insert(0, "Rider", df_visu["Artiste"].apply(lambda x: "✅ PDF" if st.session_state.riders_stockage.get(x) else "❌"))

        # ÉDITEUR DYNAMIQUE
        ed_plan = st.data_editor(
            df_visu, 
            use_container_width=True, 
            num_rows="dynamic", # Permet la suppression directe
            hide_index=False,   # Garder l'index pour la détection
            key="main_editor"
        )

        # LOGIQUE DE DÉTECTION (Modification ou Suppression)
        state = st.session_state.main_editor
        
        # 1. Détection d'une suppression (clic sur la corbeille)
        if state["deleted_rows"]:
            index_suppr = state["deleted_rows"][0]
            confirmer_suppression(index_suppr)

        # 2. Détection d'une modification de cellule
        elif state["edited_rows"]:
            for idx, changes in state["edited_rows"].items():
                for col, val in changes.items():
                    if col != "Rider": # On ne modifie pas la colonne Rider
                        st.session_state.planning.at[idx, col] = val
            st.rerun()

    st.divider()
    st.subheader("📁 Gestion des Fichiers PDF")
    if st.session_state.riders_stockage:
        col_g1, col_g2 = st.columns([2, 2])
        with col_g1:
            keys_list = list(st.session_state.riders_stockage.keys())
            if keys_list:
                choix_art = st.selectbox("Choisir Artiste :", keys_list)
                fichiers = st.session_state.riders_stockage.get(choix_art, {})
                for fname in list(fichiers.keys()):
                    cf1, cf2 = st.columns([3, 1])
                    cf1.write(f"📄 {fname}")
                    if cf2.button("🗑️", key=f"del_{fname}"):
                        del st.session_state.riders_stockage[choix_art][fname]
                        st.rerun()
        with col_g2:
            st.write("Ajouter des PDF")
            nouveaux_pdf = st.file_uploader("Glisser ici", accept_multiple_files=True, key="add_more")
            if st.button("Sauvegarder Ajout"):
                if nouveaux_pdf:
                    if choix_art not in st.session_state.riders_stockage:
                        st.session_state.riders_stockage[choix_art] = {}
                    for f in nouveaux_pdf:
                        st.session_state.riders_stockage[choix_art][f.name] = f.read()
                    st.rerun()

# --- ONGLET 2 : PATCH (Inchangé) ---
with tabs[1]:
    if not st.session_state.planning.empty:
        h1, h2, h3, h4 = st.columns([1,1,1,2])
        sel_j = h1.selectbox("Jour", sorted(st.session_state.planning["Jour"].unique()))
        sel_s = h2.selectbox("Scène", st.session_state.planning["Scène"].unique())
        artistes_dispos = st.session_state.planning[st.session_state.planning["Artiste"] != ""]["Artiste"].unique()
        
        if len(artistes_dispos) > 0:
            sel_a = h3.selectbox("Artiste", artistes_dispos)
            with h4:
                riders = st.session_state.riders_stockage.get(sel_a, {})
                if riders:
                    f_sel = st.selectbox("voir rider :", list(riders.keys()))
                    b64 = base64.b64encode(riders[f_sel]).decode('utf-8')
                    st.markdown(f'<a href="data:application/pdf;base64,{b64}" target="_blank" download="{f_sel}"><div style="background-color:#ff4b4b;color:white;padding:10px;text-align:center;border-radius:5px;font-weight:bold;">📖 OUVRIR {f_sel}</div></a>', unsafe_allow_html=True)

            st.subheader(f"📥 Saisie Matériel : {sel_a}")
            with st.container(border=True):
                c_cat, c_mar, c_mod, c_qte, c_app = st.columns([2, 2, 2, 1, 1])
                v_cat = c_cat.selectbox("Catégorie", ["MICROS FILAIRE", "HF", "EAR MONITOR", "BACKLINE"])
                v_mar = c_mar.selectbox("Marque", ["SHURE", "SENNHEISER", "AKG", "NEUMANN"])
                v_mod = c_mod.text_input("Modèle", "SM58")
                v_qte = c_qte.number_input("Qté", 1, 500, 10)
                v_app = c_app.checkbox("Artiste Apporte")
                
                if st.button("Ajouter au Patch"):
                    mask = (st.session_state.fiches_tech["Groupe"] == sel_a) & \
                           (st.session_state.fiches_tech["Modèle"] == v_mod) & \
                           (st.session_state.fiches_tech["Artiste_Apporte"] == v_app)
                    if not st.session_state.fiches_tech[mask].empty:
                        st.session_state.fiches_tech.loc[mask, "Quantité"] += v_qte
                    else:
                        new_item = pd.DataFrame([{"Scène": sel_s, "Jour": sel_j, "Groupe": sel_a, "Catégorie": v_cat, "Marque": v_mar, "Modèle": v_mod, "Quantité": v_qte, "Artiste_Apporte": v_app}])
                        st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, new_item], ignore_index=True)
                    st.rerun()

            col_patch, col_besoin = st.columns([1.5, 1])
            with col_patch:
                st.subheader(f"📋 Patch de {sel_a}")
                st.data_editor(st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"] == sel_a], use_container_width=True, num_rows="dynamic")
            with col_besoin:
                st.subheader(f"📊 Besoin {sel_s} {sel_j}")
                besoin = st.session_state.fiches_tech[(st.session_state.fiches_tech["Scène"] == sel_s) & (st.session_state.fiches_tech["Artiste_Apporte"] == False)]
                st.dataframe(besoin[["Catégorie", "Marque", "Modèle", "Quantité"]].groupby(["Catégorie", "Marque", "Modèle"]).sum().reset_index(), use_container_width=True)

# --- ONGLET 3 : EXPORTS (Inchangé) ---
with tabs[2]:
    col_ex1, col_ex2 = st.columns(2)
    with col_ex1:
        st.subheader("🗓️ Export Planning")
        peri = st.radio("Périmètre :", ["Par Scène / Jour", "Toute la Journée (Toutes scènes)", "Tout le Festival"])
        q_sc = st.selectbox("Quelle Scène ?", ["Choose an option"] + list(st.session_state.planning["Scène"].unique()))
        q_jo = st.selectbox("Quel Jour ?", ["Choose an option"] + list(st.session_state.planning["Jour"].unique()))
        if st.button("Générer PDF Planning"):
            st.info("Génération du document en cours...")
    with col_ex2:
        st.subheader("🛠️ Export Matériel")
        type_r = st.radio("Type de Rapport :", ["Besoin Journée (N+N+1)", "Besoin Global Scène (Max des Max)"])
        m_sc = st.selectbox("Quelle Scène ? ", ["Choose an option"] + list(st.session_state.planning["Scène"].unique()))
        m_jo = st.selectbox("Quel Jour ? ", ["Choose an option"] + list(st.session_state.planning["Jour"].unique()))
        if st.button("Générer Rapport Matériel"):
            st.info("Calcul des besoins et export...")
