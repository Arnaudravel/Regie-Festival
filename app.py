import streamlit as st
import pandas as pd
import base64
import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Regie-Festival", layout="wide")

# Vérification de la compatibilité st.dialog (pour éviter le NameError)
if not hasattr(st, "dialog"):
    st.error("⚠️ Votre version de Streamlit est trop ancienne pour 'st.dialog'. Veuillez faire : pip install --upgrade streamlit")
    # Simulation pour éviter que le code crash totalement
    def dialog_fallback(title):
        def decorator(func):
            return func
        return decorator
    st.dialog = dialog_fallback

# Initialisation des variables de session
if 'planning' not in st.session_state:
    st.session_state.planning = pd.DataFrame(columns=["Scène", "Jour", "Artiste", "Balance", "Show"])
if 'fiches_tech' not in st.session_state:
    st.session_state.fiches_tech = pd.DataFrame(columns=["Scène", "Jour", "Groupe", "Catégorie", "Marque", "Modèle", "Quantité", "Artiste_Apporte"])
if 'riders_stockage' not in st.session_state:
    st.session_state.riders_stockage = {}
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- FONCTIONS POP-UP DE CONFIRMATION ---

@st.dialog("Confirmation de suppression")
def confirmer_suppression(index_to_del):
    artiste_nom = st.session_state.planning.iloc[index_to_del]["Artiste"]
    st.warning(f"Êtes-vous sûr de vouloir supprimer le groupe **{artiste_nom}** ?")
    col1, col2 = st.columns(2)
    if col1.button("✅ Oui, supprimer", use_container_width=True):
        st.session_state.planning = st.session_state.planning.drop(index_to_del).reset_index(drop=True)
        if artiste_nom in st.session_state.riders_stockage:
            del st.session_state.riders_stockage[artiste_nom]
        st.rerun()
    if col2.button("❌ Annuler", use_container_width=True):
        st.rerun() # Ferme et recharge l'état initial

@st.dialog("Supprimer cet item ?")
def confirmer_suppression_patch(index_to_del, df_source):
    item = df_source.iloc[index_to_del]
    st.warning(f"Supprimer l'item : **{item['Modèle']}** ?")
    col1, col2 = st.columns(2)
    if col1.button("✅ Confirmer", use_container_width=True):
        real_idx = df_source.index[index_to_del]
        st.session_state.fiches_tech = st.session_state.fiches_tech.drop(real_idx).reset_index(drop=True)
        st.rerun()
    if col2.button("❌ Annuler", use_container_width=True):
        st.rerun()

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
    if not st.session_state.planning.empty:
        df_visu = st.session_state.planning.copy()
        df_visu.insert(0, "Rider", df_visu["Artiste"].apply(lambda x: "✅" if st.session_state.riders_stockage.get(x) else "❌"))
        ed_plan = st.data_editor(df_visu, use_container_width=True, num_rows="dynamic", key="main_editor")
        
        if st.session_state.main_editor["deleted_rows"]:
            confirmer_suppression(st.session_state.main_editor["deleted_rows"][0])
        elif st.session_state.main_editor["edited_rows"]:
            for idx, changes in st.session_state.main_editor["edited_rows"].items():
                for col, val in changes.items():
                    if col != "Rider":
                        st.session_state.planning.at[idx, col] = val
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
        # LIGNE 1 : FILTRES ALIGNÉS
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

            # LIGNE 2 : TABLEAUX CÔTE À CÔTE
            col_patch, col_besoin = st.columns(2)

            with col_patch:
                st.subheader(f"📋 Items pour {sel_a}")
                df_patch_art = st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"] == sel_a]
                ed_patch = st.data_editor(df_patch_art, use_container_width=True, num_rows="dynamic", key=f"ed_patch_{sel_a}")
                
                if st.session_state[f"ed_patch_{sel_a}"]["deleted_rows"]:
                    confirmer_suppression_patch(st.session_state[f"ed_patch_{sel_a}"]["deleted_rows"][0], df_patch_art)
                elif st.session_state[f"ed_patch_{sel_a}"]["edited_rows"]:
                    for idx_rel, changes in st.session_state[f"ed_patch_{sel_a}"]["edited_rows"].items():
                        real_idx = df_patch_art.index[idx_rel]
                        for col, val in changes.items():
                            st.session_state.fiches_tech.at[real_idx, col] = val
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
                    st.dataframe(res.reset_index().rename(columns={0: "Total Journée"}), use_container_width=True)
                else:
                    st.info("Aucun besoin à afficher.")

# --- ONGLET 3 : EXPORTS ---
with tabs[2]:
    st.write("Section Export (En attente)")
