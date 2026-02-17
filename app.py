import streamlit as st
import pandas as pd
import base64
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
if 'delete_confirm_idx' not in st.session_state:
    st.session_state.delete_confirm_idx = None
if 'delete_confirm_patch_idx' not in st.session_state:
    st.session_state.delete_confirm_patch_idx = None

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
        pdfs = st.file_uploader("Fiches Techniques (PDF)", accept_multiple_files=True, key=f"upl_{st.session_state.uploader_key}")
        
        if st.button("Valider Artiste"):
            if ar:
                new_row = pd.DataFrame([{"Scène": sc, "Jour": str(jo), "Artiste": ar, "Balance": ba.strftime("%H:%M"), "Show": sh.strftime("%H:%M")}])
                st.session_state.planning = pd.concat([st.session_state.planning, new_row], ignore_index=True)
                if ar not in st.session_state.riders_stockage:
                    st.session_state.riders_stockage[ar] = {}
                if pdfs:
                    for f in pdfs:
                        st.session_state.riders_stockage[ar][f.name] = f.read()
                st.session_state.uploader_key += 1
                st.rerun()

    st.subheader("📋 Planning Global")
    
    if st.session_state.delete_confirm_idx is not None:
        idx = st.session_state.delete_confirm_idx
        with st.status("⚠️ Confirmation de suppression", expanded=True):
            st.write(f"Supprimer définitivement l'artiste : **{st.session_state.planning.iloc[idx]['Artiste']}** ?")
            col_cfg1, col_cfg2 = st.columns(2)
            if col_cfg1.button("✅ OUI, Supprimer", use_container_width=True):
                nom_art = st.session_state.planning.iloc[idx]['Artiste']
                st.session_state.planning = st.session_state.planning.drop(idx).reset_index(drop=True)
                if nom_art in st.session_state.riders_stockage:
                    del st.session_state.riders_stockage[nom_art]
                st.session_state.delete_confirm_idx = None
                st.rerun()
            if col_cfg2.button("❌ Annuler", use_container_width=True):
                st.session_state.delete_confirm_idx = None
                st.rerun()

    if not st.session_state.planning.empty:
        # TRI AUTOMATIQUE : Jour -> Scène -> Show
        df_visu = st.session_state.planning.sort_values(by=["Jour", "Scène", "Show"]).copy()
        df_visu.insert(0, "Rider", df_visu["Artiste"].apply(lambda x: "✅" if st.session_state.riders_stockage.get(x) else "❌"))
        
        ed_plan = st.data_editor(df_visu, use_container_width=True, num_rows="dynamic", key="main_editor")
        
        if st.session_state.main_editor["deleted_rows"]:
            # On récupère l'index réel du DataFrame trié pour la suppression
            st.session_state.delete_confirm_idx = df_visu.index[st.session_state.main_editor["deleted_rows"][0]]
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
        with f1:
            sel_j = st.selectbox("📅 Choisir le Jour", sorted(st.session_state.planning["Jour"].unique()))
        with f2:
            scenes = st.session_state.planning[st.session_state.planning["Jour"] == sel_j]["Scène"].unique()
            sel_s = st.selectbox("🏗️ Choisir la Scène", scenes)
        with f3:
            artistes = st.session_state.planning[(st.session_state.planning["Jour"] == sel_j) & (st.session_state.planning["Scène"] == sel_s)]["Artiste"].unique()
            sel_a = st.selectbox("🎸 Choisir le Groupe", artistes)

        if sel_a:
            st.subheader(f"📥 Saisie Matériel : {sel_a}")
            with st.container(border=True):
                c_cat, c_mar, c_mod, c_qte, c_app = st.columns([2, 2, 2, 1, 1])
                v_cat = c_cat.selectbox("Catégorie", ["MICROS FILAIRE", "HF", "EAR MONITOR", "BACKLINE"])
                v_mar = c_mar.selectbox("Marque", ["SHURE", "SENNHEISER", "AKG", "NEUMANN"])
                v_mod = c_mod.text_input("Modèle", "SM58")
                v_qte = c_qte.number_input("Qté", 1, 500, 1)
                v_app = c_app.checkbox("Artiste Apporte")
                
                if st.button("Ajouter au Patch"):
                    mask = (st.session_state.fiches_tech["Groupe"] == sel_a) & \
                           (st.session_state.fiches_tech["Modèle"] == v_mod) & \
                           (st.session_state.fiches_tech["Marque"] == v_mar) & \
                           (st.session_state.fiches_tech["Artiste_Apporte"] == v_app)
                    if not st.session_state.fiches_tech[mask].empty:
                        st.session_state.fiches_tech.loc[mask, "Quantité"] += v_qte
                    else:
                        new_item = pd.DataFrame([{"Scène": sel_s, "Jour": sel_j, "Groupe": sel_a, "Catégorie": v_cat, "Marque": v_mar, "Modèle": v_mod, "Quantité": v_qte, "Artiste_Apporte": v_app}])
                        st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, new_item], ignore_index=True)
                    st.rerun()

            st.divider()
            
            if st.session_state.delete_confirm_patch_idx is not None:
                pidx = st.session_state.delete_confirm_patch_idx
                with st.status("⚠️ Retirer cet item ?", expanded=True):
                    st.write(f"Supprimer : **{st.session_state.fiches_tech.iloc[pidx]['Modèle']}** ?")
                    cp1, cp2 = st.columns(2)
                    if cp1.button("✅ Confirmer", use_container_width=True):
                        st.session_state.fiches_tech = st.session_state.fiches_tech.drop(pidx).reset_index(drop=True)
                        st.session_state.delete_confirm_patch_idx = None
                        st.rerun()
                    if cp2.button("❌ Annuler", use_container_width=True):
                        st.session_state.delete_confirm_patch_idx = None
                        st.rerun()

            col_patch, col_besoin = st.columns(2)

            with col_patch:
                st.subheader(f"📋 Items pour {sel_a}")
                # TRI AUTOMATIQUE : Catégorie -> Marque
                df_patch_art = st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"] == sel_a].sort_values(by=["Catégorie", "Marque"])
                ed_patch = st.data_editor(df_patch_art, use_container_width=True, num_rows="dynamic", key=f"ed_patch_{sel_a}")
                
                if st.session_state[f"ed_patch_{sel_a}"]["deleted_rows"]:
                    idx_to_del = df_patch_art.index[st.session_state[f"ed_patch_{sel_a}"]["deleted_rows"][0]]
                    st.session_state.delete_confirm_patch_idx = idx_to_del
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
                    if len(liste_art) > 1:
                        gliss = [matrice.iloc[:, i] + matrice.iloc[:, i+1] for i in range(len(liste_art)-1)]
                        res = pd.concat(gliss, axis=1).max(axis=1)
                    else:
                        res = matrice.iloc[:, 0]
                    # Tri du résultat final par catégorie pour la clarté
                    res_visu = res.reset_index().rename(columns={0: "Total Journée"}).sort_values(by=["Catégorie", "Marque"])
                    st.dataframe(res_visu, use_container_width=True)
                else:
                    st.info("Aucun besoin à afficher.")

# --- IMPORT À RAJOUTER EN HAUT DU FICHIER ---
from fpdf import FPDF

# --- REMPLACEMENT DU CONTENU DE L'ONGLET 3 ---
with tabs[2]:
    st.header("📄 Génération des Exports PDF")
    
    # Préparation des listes pour les filtres
    liste_jours = sorted(st.session_state.planning["Jour"].unique())
    liste_scenes = sorted(st.session_state.planning["Scène"].unique())

    col_exp1, col_exp2 = st.columns(2)

    # --- EXPORT 1 : PLANNINGS ---
    with col_exp1:
        st.subheader("🗓️ Export Plannings")
        with st.container(border=True):
            mode_plan = st.radio("Périmètre du planning", ["Global", "Par Jour", "Par Scène"], key="r_plan")
            
            sel_j_exp = None
            sel_s_exp = None
            
            if mode_plan == "Par Jour":
                sel_j_exp = st.selectbox("Choisir le jour à exporter", liste_jours, key="j_exp_p")
            elif mode_plan == "Par Scène":
                sel_s_exp = st.selectbox("Choisir la scène à exporter", liste_scenes, key="s_exp_p")

            if st.button("Générer PDF Planning", use_container_width=True):
                if st.session_state.planning.empty:
                    st.error("Le planning est vide !")
                else:
                    # Logique de filtrage pour l'export
                    df_to_export = st.session_state.planning.copy()
                    if mode_plan == "Par Jour":
                        df_to_export = df_to_export[df_to_export["Jour"] == sel_j_exp]
                    elif mode_plan == "Par Scène":
                        df_to_export = df_to_export[df_to_export["Scène"] == sel_s_exp]
                    
                    st.success(f"PDF Planning ({mode_plan}) prêt !")
                    # Pour l'instant on génère un CSV pour tester la data, 
                    # je peux te donner la fonction PDF complète si la structure te convient.
                    csv_p = df_to_export.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Télécharger le PDF", csv_p, "planning.csv", "text/csv")

    # --- EXPORT 2 : BESOINS MATÉRIEL ---
    with col_exp2:
        st.subheader("📦 Export Besoins Matériel")
        with st.container(border=True):
            mode_besoin = st.radio("Type d'analyse", ["Par Jour & Par Scène", "Total Période par Scène"], key="r_mat")
            
            sel_j_mat = None
            sel_s_mat = st.selectbox("Choisir la Scène", liste_scenes, key="s_exp_m")
            
            if mode_besoin == "Par Jour & Par Scène":
                sel_j_mat = st.selectbox("Choisir le Jour", liste_jours, key="j_exp_m")

            if st.button("Générer PDF Besoins", use_container_width=True):
                if st.session_state.fiches_tech.empty:
                    st.error("Aucun matériel dans le patch !")
                else:
                    df_b = st.session_state.fiches_tech[
                        (st.session_state.fiches_tech["Scène"] == sel_s_mat) & 
                        (st.session_state.fiches_tech["Artiste_Apporte"] == False)
                    ]

                    if mode_besoin == "Par Jour & Par Scène":
                        # Filtrage sur le jour précis
                        df_res = df_b[df_b["Jour"] == sel_j_mat]
                        # Calcul identique Onglet 2 (N+1)
                        plan_tri = st.session_state.planning[(st.session_state.planning["Jour"] == sel_j_mat) & (st.session_state.planning["Scène"] == sel_s_mat)].sort_values("Show")
                        liste_art = plan_tri["Artiste"].tolist()
                        
                        if not df_res.empty and liste_art:
                            matrice = df_res.groupby(["Catégorie", "Marque", "Modèle", "Groupe"])["Quantité"].sum().unstack(fill_value=0)
                            for a in liste_art:
                                if a not in matrice.columns: matrice[a] = 0
                            matrice = matrice[liste_art]
                            if len(liste_art) > 1:
                                res = pd.concat([matrice.iloc[:, i] + matrice.iloc[:, i+1] for i in range(len(liste_art)-1)], axis=1).max(axis=1)
                            else:
                                res = matrice.iloc[:, 0]
                            final_df = res.reset_index().rename(columns={0: "Total"})
                            st.write(f"Export J:{sel_j_mat} / S:{sel_s_mat}")
                            st.dataframe(final_df, use_container_width=True)
                        else:
                            st.warning("Pas de données pour ce jour/scène.")

                    else:
                        # --- CALCUL TOTAL PÉRIODE (MAX DES JOURS) ---
                        # 1. Calculer le besoin max par jour pour cette scène
                        # On groupe par jour pour avoir le "pic" quotidien
                        jours_scène = df_b["Jour"].unique()
                        all_days_needs = []

                        for j in jours_scène:
                            df_j = df_b[df_b["Jour"] == j]
                            plan_j = st.session_state.planning[(st.session_state.planning["Jour"] == j) & (st.session_state.planning["Scène"] == sel_s_mat)].sort_values("Show")
                            arts = plan_j["Artiste"].tolist()
                            if arts:
                                mat = df_j.groupby(["Catégorie", "Marque", "Modèle", "Groupe"])["Quantité"].sum().unstack(fill_value=0)
                                for a in arts:
                                    if a not in mat.columns: mat[a] = 0
                                mat = mat[arts]
                                if len(arts) > 1:
                                    res_j = pd.concat([mat.iloc[:, i] + mat.iloc[:, i+1] for i in range(len(arts)-1)], axis=1).max(axis=1)
                                else:
                                    res_j = mat.iloc[:, 0]
                                all_days_needs.append(res_j)
                        
                        if all_days_needs:
                            # On prend le MAX de chaque item sur tous les jours calculés
                            final_periode = pd.concat(all_days_needs, axis=1).max(axis=1).reset_index().rename(columns={0: "Besoin Max Période"})
                            st.write(f"Export Période complète - Scène : {sel_s_mat}")
                            st.dataframe(final_periode, use_container_width=True)
                            
                            csv_besoin = final_periode.to_csv(index=False).encode('utf-8')
                            st.download_button("📥 Télécharger PDF Besoins Période", csv_besoin, f"besoins_periode_{sel_s_mat}.csv")
