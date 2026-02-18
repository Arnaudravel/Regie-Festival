import streamlit as st
import pandas as pd
import datetime
import time
from fpdf import FPDF
import io
import pickle

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Regie-Festival", layout="wide", initial_sidebar_state="collapsed")

# --- INITIALISATION DES VARIABLES DE SESSION ---
if 'planning' not in st.session_state:
    # Modification structure pour la nouvelle logique Balance
    st.session_state.planning = pd.DataFrame(columns=["Scène", "Jour", "Artiste", "A une balance", "Heure Balance", "Durée Balance", "Show"])
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
if 'last_reminder' not in st.session_state:
    st.session_state.last_reminder = time.time()

# --- LOGIQUE POP-UP RAPPEL SAUVEGARDE (10 MIN) ---
current_time = time.time()
if current_time - st.session_state.last_reminder > 600: # 600 secondes = 10 minutes
    st.toast("⚠️ Pensez à sauvegarder votre projet dans l'onglet Admin !", icon="💾")
    st.session_state.last_reminder = current_time

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
tabs = st.tabs(["🏗️ Configuration", "⚙️ Patch & Régie", "📄 Exports PDF", "🛠️ Admin & Sauvegarde"])

# --- ONGLET 1 : CONFIGURATION ---
with tabs[0]:
    st.subheader("➕ Ajouter un Artiste")
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1, 1, 2, 1])
        sc = c1.text_input("Scène", "MainStage")
        jo = c2.date_input("Date de passage", datetime.date.today())
        ar = c3.text_input("Nom Artiste")
        sh = c4.time_input("Heure Show", datetime.time(20, 0))
        
        # NOUVELLE LOGIQUE BALANCE
        st.markdown("**Balances :**")
        b_col1, b_col2, b_col3 = st.columns([1, 1, 1])
        has_bal = b_col1.checkbox("A une balance ?")
        h_bal = ""
        d_bal = ""
        if has_bal:
            # Texte libre pour permettre de laisser vide si besoin
            h_bal = b_col2.text_input("Heure Balance (ex: 14:00)", "")
            d_bal = b_col3.text_input("Durée (ex: 45min)", "")
        
        pdfs = st.file_uploader("Fiches Techniques (PDF)", accept_multiple_files=True, key=f"upl_{st.session_state.uploader_key}")
        
        if st.button("Valider Artiste"):
            if ar:
                # Création de la ligne avec les nouvelles colonnes
                new_row = pd.DataFrame([{"Scène": sc, "Jour": str(jo), "Artiste": ar, "A une balance": has_bal, "Heure Balance": h_bal, "Durée Balance": d_bal, "Show": sh.strftime("%H:%M")}])
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
        df_visu = st.session_state.planning.sort_values(by=["Jour", "Scène", "Show"]).copy()
        df_visu.insert(0, "Rider", df_visu["Artiste"].apply(lambda x: "✅" if st.session_state.riders_stockage.get(x) else "❌"))
        
        # Ajout de hide_index=True
        edited_df = st.data_editor(df_visu, use_container_width=True, num_rows="dynamic", key="main_editor", hide_index=True)
        
        if st.session_state.main_editor["deleted_rows"]:
            st.session_state.delete_confirm_idx = df_visu.index[st.session_state.main_editor["deleted_rows"][0]]
            st.rerun()
            
        df_to_save = edited_df.drop(columns=["Rider"])
        if not df_to_save.equals(st.session_state.planning.sort_values(by=["Jour", "Scène", "Show"]).reset_index(drop=True)):
             st.session_state.planning = df_to_save.reset_index(drop=True)
             st.rerun()

    st.divider()
    st.subheader("📁 Gestion des Fichiers PDF")
    if st.session_state.riders_stockage:
        keys_list = list(st.session_state.riders_stockage.keys())
        if keys_list:
            cg1, cg2 = st.columns(2)
            with cg1:
                choix_art_pdf = st.selectbox("Choisir Artiste pour gérer ses PDF :", keys_list)
                fichiers = st.session_state.riders_stockage.get(choix_art_pdf, {})
                for fname in list(fichiers.keys()):
                    cf1, cf2 = st.columns([4, 1])
                    cf1.write(f"📄 {fname}")
                    if cf2.button("🗑️", key=f"del_pdf_{fname}"):
                        del st.session_state.riders_stockage[choix_art_pdf][fname]
                        st.rerun()
            with cg2:
                nouveaux_pdf = st.file_uploader("Ajouter des fichiers", accept_multiple_files=True, key="add_pdf_extra")
                if st.button("Enregistrer les nouveaux PDF"):
                    if nouveaux_pdf:
                        for f in nouveaux_pdf:
                            st.session_state.riders_stockage[choix_art_pdf][f.name] = f.read()
                        st.rerun()

# --- ONGLET 2 : PATCH & RÉGIE ---
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
                liste_categories = list(CATALOGUE.keys()) if CATALOGUE else ["MICROS FILAIRE", "HF", "EAR MONITOR", "BACKLINE"]
                v_cat = c_cat.selectbox("Catégorie", liste_categories)
                liste_marques = []
                if CATALOGUE and v_cat in CATALOGUE:
                    liste_marques = list(CATALOGUE[v_cat].keys())
                else:
                    liste_marques = ["SHURE", "SENNHEISER", "AKG", "NEUMANN", "YAMAHA", "FENDER"]
                v_mar = c_mar.selectbox("Marque", liste_marques)
                v_mod = ""
                if CATALOGUE and v_cat in CATALOGUE and v_mar in CATALOGUE[v_cat]:
                    raw_modeles = CATALOGUE[v_cat][v_mar]
                    display_modeles = [f"🔹 {str(m).replace('//','').strip()} 🔹" if str(m).startswith("//") else m for m in raw_modeles]
                    v_mod = c_mod.selectbox("Modèle", display_modeles)
                else:
                    v_mod = c_mod.text_input("Modèle", "SM58")
                v_qte = c_qte.number_input("Qté", 1, 500, 1)
                v_app = c_app.checkbox("Artiste Apporte")
                
                if st.button("Ajouter au Patch"):
                    if isinstance(v_mod, str) and (v_mod.startswith("🔹") or v_mod.startswith("//")):
                        st.error("⛔ Impossible d'ajouter un titre de section. Veuillez sélectionner un vrai matériel.")
                    else:
                        mask = (st.session_state.fiches_tech["Groupe"] == sel_a) & (st.session_state.fiches_tech["Modèle"] == v_mod) & (st.session_state.fiches_tech["Marque"] == v_mar) & (st.session_state.fiches_tech["Artiste_Apporte"] == v_app)
                        if not st.session_state.fiches_tech[mask].empty:
                            st.session_state.fiches_tech.loc[mask, "Quantité"] += v_qte
                        else:
                            new_item = pd.DataFrame([{"Scène": sel_s, "Jour": sel_j, "Groupe": sel_a, "Catégorie": v_cat, "Marque": v_mar, "Modèle": v_mod, "Quantité": v_qte, "Artiste_Apporte": v_app}])
                            st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, new_item], ignore_index=True)
                        st.rerun()

            st.divider()
            if st.session_state.delete_confirm_patch_idx is not None:
                pidx = st.session_state.delete_confirm_patch_idx
                with st.status("⚠️ Confirmation", expanded=True):
                    st.write(f"Supprimer : **{st.session_state.fiches_tech.iloc[pidx]['Modèle']}** ?")
                    if st.button("✅ Confirmer"):
                        st.session_state.fiches_tech = st.session_state.fiches_tech.drop(pidx).reset_index(drop=True)
                        st.session_state.delete_confirm_patch_idx = None
                        st.rerun()
                    if st.button("❌ Annuler"):
                        st.session_state.delete_confirm_patch_idx = None
                        st.rerun()

            col_patch, col_besoin = st.columns(2)
            with col_patch:
                st.subheader(f"📋 Items pour {sel_a} (Modifiable)")
                df_patch_art = st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"] == sel_a].sort_values(by=["Catégorie", "Marque"])
                # MASQUAGE NUMÉRO DE LIGNE ICI
                edited_patch = st.data_editor(df_patch_art, use_container_width=True, num_rows="dynamic", key=f"ed_patch_{sel_a}", hide_index=True)
                
                if st.session_state[f"ed_patch_{sel_a}"]["deleted_rows"]:
                    st.session_state.delete_confirm_patch_idx = df_patch_art.index[st.session_state[f"ed_patch_{sel_a}"]["deleted_rows"][0]]
                    st.rerun()
                
                if not edited_patch.equals(df_patch_art):
                    st.session_state.fiches_tech.update(edited_patch)
                    st.rerun()

            with col_besoin:
                st.subheader(f"📊 Besoin {sel_s} - {sel_j}")
                plan_trié = st.session_state.planning[(st.session_state.planning["Jour"] == sel_j) & (st.session_state.planning["Scène"] == sel_s)].sort_values("Show")
                liste_art = plan_trié["Artiste"].tolist()
                df_b = st.session_state.fiches_tech[(st.session_state.fiches_tech["Scène"] == sel_s) & (st.session_state.fiches_tech["Jour"] == sel_j) & (st.session_state.fiches_tech["Artiste_Apporte"] == False)]
                if not df_b.empty:
                    matrice = df_b.groupby(["Catégorie", "Marque", "Modèle", "Groupe"])["Quantité"].sum().unstack(fill_value=0)
                    for a in liste_art: 
                        if a not in matrice.columns: matrice[a] = 0
                    matrice = matrice[liste_art]
                    res = pd.concat([matrice.iloc[:, i] + matrice.iloc[:, i+1] for i in range(len(liste_art)-1)], axis=1).max(axis=1) if len(liste_art) > 1 else matrice.iloc[:, 0]
                    # MASQUAGE NUMÉRO DE LIGNE ICI
                    st.dataframe(res.reset_index().rename(columns={0: "Total"}), use_container_width=True, hide_index=True)

# --- ONGLET 3 : EXPORTS PDF ---
with tabs[2]:
    st.header("📄 Génération des Exports PDF")
    l_jours = sorted(st.session_state.planning["Jour"].unique())
    l_scenes = sorted(st.session_state.planning["Scène"].unique())
    cex1, cex2 = st.columns(2)

    with cex1:
        st.subheader("🗓️ Export Plannings")
        with st.container(border=True):
            m_plan = st.radio("Périmètre", ["Global", "Par Jour", "Par Scène"], key="mp")
            s_j_p = st.selectbox("Jour", l_jours) if m_plan == "Par Jour" else None
            s_s_p = st.selectbox("Scène", l_scenes) if m_plan == "Par Scène" else None
            
            if st.button("Générer PDF Planning", use_container_width=True):
                df_p = st.session_state.planning.copy()
                dico_sections = {}
                jours_a_traiter = [s_j_p] if m_plan == "Par Jour" else l_jours
                scenes_a_traiter = [s_s_p] if m_plan == "Par Scène" else l_scenes
                
                for j in jours_a_traiter:
                    for s in scenes_a_traiter:
                        sub_df = df_p[(df_p["Jour"] == j) & (df_p["Scène"] == s)].sort_values("Show")
                        if not sub_df.empty:
                            # MODIF: Sélection des nouvelles colonnes pour le PDF
                            dico_sections[f"JOUR : {j} | SCENE : {s}"] = sub_df[["Artiste", "A une balance", "Heure Balance", "Durée Balance", "Show"]]
                
                pdf_bytes = generer_pdf_complet(f"PLANNING {m_plan.upper()}", dico_sections)
                st.download_button("📥 Télécharger PDF Planning", pdf_bytes, "planning.pdf", "application/pdf")

    with cex2:
        st.subheader("📦 Export Besoins")
        with st.container(border=True):
            m_bes = st.radio("Type", ["Par Jour & Scène", "Total Période par Scène"], key="mb")
            s_s_m = st.selectbox("Scène", l_scenes, key="ssm")
            
            # --- AJOUT : CHOIX DU GROUPE ---
            sel_art_exp = "Tous les groupes"
            s_j_m = None
            if m_bes == "Par Jour & Scène":
                s_j_m = st.selectbox("Jour", l_jours, key="sjm")
                # On récupère les groupes de ce jour/scène
                artistes_du_jour = ["Tous les groupes"] + list(st.session_state.planning[(st.session_state.planning["Jour"]==s_j_m) & (st.session_state.planning["Scène"]==s_s_m)]["Artiste"].unique())
                sel_art_exp = st.selectbox("Choisir Groupe (Optionnel)", artistes_du_jour)
            
            if st.button("Générer PDF Besoins", use_container_width=True):
                # 1. Calcul des besoins
                df_base = st.session_state.fiches_tech[(st.session_state.fiches_tech["Scène"] == s_s_m) & (st.session_state.fiches_tech["Artiste_Apporte"] == False)]
                
                # --- FILTRE GROUPE SPECIFIQUE ---
                if m_bes == "Par Jour & Scène" and sel_art_exp != "Tous les groupes":
                    df_base = df_base[df_base["Groupe"] == sel
