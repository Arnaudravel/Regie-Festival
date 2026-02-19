import streamlit as st
import pandas as pd
import datetime
from fpdf import FPDF
import io
import pickle
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
tabs = st.tabs(["🏗️ Configuration", "⚙️ Patch & Régie", "📄 Exports PDF", "🛠️ Admin & Sauvegarde"])

# --- ONGLET 1 : CONFIGURATION (PLANNING DYNAMIQUE) ---
with tabs[0]:
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
        # MODIF 1 : Masquage index Onglet 1
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
                        for f in nouveaux_pdf: st.session_state.riders_stockage[choix_art_pdf][f.name] = f.read()
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
                        st.error("⛔ Impossible d'ajouter un titre de section.")
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
                    # MODIF 1 & 3 : Masquage index et forçage du nom de colonne à "Total"
                    st.dataframe(res.to_frame(name="Total").reset_index(), use_container_width=True, hide_index=True)

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
                            cols_to_export = ["Artiste", "Balance", "Durée Balance", "Show"]
                            if "Durée Balance" not in sub_df.columns:
                                cols_to_export.remove("Durée Balance")
                            dico_sections[f"JOUR : {j} | SCENE : {s}"] = sub_df[cols_to_export]
                pdf_bytes = generer_pdf_complet(f"PLANNING {m_plan.upper()}", dico_sections)
                st.download_button("📥 Télécharger PDF Planning", pdf_bytes, "planning.pdf", "application/pdf")

    with cex2:
        st.subheader("📦 Export Besoins")
        with st.container(border=True):
            m_bes = st.radio("Type", ["Par Jour & Scène", "Total Période par Scène"], key="mb")
            s_s_m = st.selectbox("Scène", l_scenes, key="ssm")
            s_j_m = None
            sel_grp_exp = "Tous"
            if m_bes == "Par Jour & Scène":
                s_j_m = st.selectbox("Jour", l_jours, key="sjm")
                arts_du_jour = st.session_state.planning[(st.session_state.planning["Jour"] == s_j_m) & (st.session_state.planning["Scène"] == s_s_m)]["Artiste"].unique()
                sel_grp_exp = st.selectbox("Filtrer par Groupe (Optionnel)", ["Tous"] + list(arts_du_jour))
            
            if st.button("Générer PDF Besoins", use_container_width=True):
                df_base = st.session_state.fiches_tech[(st.session_state.fiches_tech["Scène"] == s_s_m) & (st.session_state.fiches_tech["Artiste_Apporte"] == False)]
                if sel_grp_exp != "Tous":
                    df_base = df_base[df_base["Groupe"] == sel_grp_exp]
                
                dico_besoins = {}
                def calcul_pic(df_input, jour, scene):
                    if sel_grp_exp != "Tous":
                        plan = st.session_state.planning[(st.session_state.planning["Jour"] == jour) & (st.session_state.planning["Scène"] == scene) & (st.session_state.planning["Artiste"] == sel_grp_exp)].sort_values("Show")
                    else:
                        plan = st.session_state.planning[(st.session_state.planning["Jour"] == jour) & (st.session_state.planning["Scène"] == scene)].sort_values("Show")
                    arts = plan["Artiste"].tolist()
                    if not arts or df_input.empty: return pd.DataFrame()
                    mat = df_input.groupby(["Catégorie", "Marque", "Modèle", "Groupe"])["Quantité"].sum().unstack(fill_value=0)
                    for a in arts: 
                        if a not in mat.columns: mat[a] = 0
                    if len(arts) > 1:
                        res = pd.concat([mat[arts].iloc[:, i] + mat[arts].iloc[:, i+1] for i in range(len(arts)-1)], axis=1).max(axis=1)
                    else:
                         res = mat[arts].iloc[:, 0]
                    # MODIF 2 : Forçage du nom de colonne pour l'export PDF
                    return res.to_frame(name="Total").reset_index()

                if m_bes == "Par Jour & Scène":
                    data_pic = calcul_pic(df_base[df_base["Jour"] == s_j_m], s_j_m, s_s_m)
                    if not data_pic.empty:
                        for cat in data_pic["Catégorie"].unique():
                            cols_dispo = [c for c in ["Marque", "Modèle", "Total"] if c in data_pic.columns]
                            dico_besoins[f"CATEGORIE : {cat}"] = data_pic[data_pic["Catégorie"] == cat][cols_dispo]
                else:
                    all_days_res = []
                    for j in df_base["Jour"].unique():
                        res_j = calcul_pic(df_base[df_base["Jour"] == j], j, s_s_m)
                        if not res_j.empty: 
                            # On renomme temporairement pour la fusion
                            all_days_res.append(res_j.set_index(["Catégorie", "Marque", "Modèle"]).rename(columns={"Total": "Q"}))
                    if all_days_res:
                        final = pd.concat(all_days_res, axis=1).max(axis=1).reset_index().rename(columns={0: "Max_Periode"})
                        for cat in final["Catégorie"].unique():
                            cols_dispo_glob = [c for c in ["Marque", "Modèle", "Max_Periode"] if c in final.columns]
                            dico_besoins[f"CATEGORIE : {cat}"] = final[final["Catégorie"] == cat][cols_dispo_glob]

                df_apporte = st.session_state.fiches_tech[(st.session_state.fiches_tech["Scène"] == s_s_m) & (st.session_state.fiches_tech["Artiste_Apporte"] == True)]
                if m_bes == "Par Jour & Scène":
                     df_apporte = df_apporte[df_apporte["Jour"] == s_j_m]
                if sel_grp_exp != "Tous":
                    df_apporte = df_apporte[df_apporte["Groupe"] == sel_grp_exp]
                artistes_apporte = df_apporte["Groupe"].unique()
                if len(artistes_apporte) > 0:
                    dico_besoins[" "] = pd.DataFrame() 
                    dico_besoins["--- MATERIEL APPORTE PAR LES ARTISTES ---"] = pd.DataFrame()
                    for art in artistes_apporte:
                        items_art = df_apporte[df_apporte["Groupe"] == art][["Catégorie", "Marque", "Modèle", "Quantité"]]
                        dico_besoins[f"FOURNI PAR : {art}"] = items_art
                titre_besoin = f"BESOINS {s_s_m} ({m_bes})"
                if sel_grp_exp != "Tous": titre_besoin += f" - {sel_grp_exp}"
                pdf_bytes_b = generer_pdf_complet(titre_besoin, dico_besoins)
                st.download_button("📥 Télécharger PDF Besoins", pdf_bytes_b, "besoins.pdf", "application/pdf")

# --- ONGLET 4 : ADMIN & SAUVEGARDE ---
with tabs[3]:
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
            st.info("Ces informations apparaitront sur tous les exports PDF.")
        st.subheader("💾 Sauvegarde Projet")
        with st.container(border=True):
            data_to_save = {
                "planning": st.session_state.planning,
                "fiches_tech": st.session_state.fiches_tech,
                "riders_stockage": st.session_state.riders_stockage,
                "festival_name": st.session_state.festival_name,
                "festival_logo": st.session_state.festival_logo,
                "custom_catalog": st.session_state.custom_catalog
            }
            pickle_out = pickle.dumps(data_to_save)
            st.download_button("💾 Sauvegarder ma Session (.pkl)", pickle_out, f"backup_festival_{datetime.date.today()}.pkl")
            st.divider()
            uploaded_session = st.file_uploader("📂 Charger une sauvegarde (.pkl)", type=['pkl'])
            if uploaded_session:
                if st.button("Restaurer la sauvegarde"):
                    try:
                        data_loaded = pickle.loads(uploaded_session.read())
                        st.session_state.planning = data_loaded["planning"]
                        st.session_state.fiches_tech = data_loaded["fiches_tech"]
                        st.session_state.riders_stockage = data_loaded["riders_stockage"]
                        st.session_state.festival_name = data_loaded.get("festival_name", "Mon Festival")
                        st.session_state.festival_logo = data_loaded.get("festival_logo", None)
                        st.session_state.custom_catalog = data_loaded.get("custom_catalog", {})
                        st.success("Session restaurée avec succès !")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur lors du chargement : {e}")
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
                if st.session_state.custom_catalog:
                     if st.button("🗑️ Réinitialiser Catalogue"):
                        st.session_state.custom_catalog = {}
                        st.rerun()
        else:
            if code_secret: st.warning("Code incorrect")
