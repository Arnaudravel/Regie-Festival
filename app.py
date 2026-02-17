import streamlit as st
import pandas as pd
import base64
import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Regie-Festival", layout="wide")

# Initialisation sécurisée des variables
if 'planning' not in st.session_state:
    st.session_state.planning = pd.DataFrame(columns=["Scène", "Jour", "Artiste", "Balance", "Show"])
if 'fiches_tech' not in st.session_state:
    st.session_state.fiches_tech = pd.DataFrame(columns=["Scène", "Jour", "Groupe", "Catégorie", "Marque", "Modèle", "Quantité", "Artiste_Apporte"])
if 'riders_stockage' not in st.session_state:
    st.session_state.riders_stockage = {}
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- LOGIQUE DE SUPPRESSION (SANS DECORATEUR SI ERREUR) ---

@st.dialog("Supprimer cet artiste ?")
def pop_supprimer_artiste(index):
    st.warning(f"Confirmer la suppression de : {st.session_state.planning.iloc[index]['Artiste']} ?")
    c1, c2 = st.columns(2)
    if c1.button("Oui, supprimer", use_container_width=True):
        nom = st.session_state.planning.iloc[index]['Artiste']
        st.session_state.planning = st.session_state.planning.drop(index).reset_index(drop=True)
        if nom in st.session_state.riders_stockage:
            del st.session_state.riders_stockage[nom]
        st.rerun()
    if c2.button("Non, annuler", use_container_width=True):
        st.rerun()

@st.dialog("Supprimer cet item ?")
def pop_supprimer_item(index, df_source):
    st.warning(f"Supprimer l'item : {df_source.iloc[index]['Modèle']} ?")
    c1, c2 = st.columns(2)
    if c1.button("Oui, retirer", use_container_width=True):
        idx_global = df_source.index[index]
        st.session_state.fiches_tech = st.session_state.fiches_tech.drop(idx_global).reset_index(drop=True)
        st.rerun()
    if c2.button("Non, annuler", use_container_width=True):
        st.rerun()

# --- INTERFACE PRINCIPALE ---
st.title("Gestion Régie Festival")
tabs = st.tabs(["🏗️ Configuration", "⚙️ Patch & Régie", "📄 Exports"])

# --- ONGLET 1 : CONFIGURATION ---
with tabs[0]:
    st.subheader("➕ Ajouter un Artiste")
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([1, 1, 2, 1, 1])
        sc = c1.text_input("Scène", "MainStage")
        jo = c2.date_input("Jour", datetime.date.today())
        ar = c3.text_input("Artiste")
        ba = c4.time_input("Balance", datetime.time(14, 0))
        sh = c5.time_input("Show", datetime.time(20, 0))
        pdfs = st.file_uploader("PDF", accept_multiple_files=True, key=f"u_{st.session_state.uploader_key}")
        
        if st.button("Valider l'ajout"):
            if ar:
                new_row = pd.DataFrame([{"Scène": sc, "Jour": str(jo), "Artiste": ar, "Balance": ba.strftime("%H:%M"), "Show": sh.strftime("%H:%M")}])
                st.session_state.planning = pd.concat([st.session_state.planning, new_row], ignore_index=True)
                st.session_state.riders_stockage[ar] = {f.name: f.read() for f in pdfs} if pdfs else {}
                st.session_state.uploader_key += 1
                st.rerun()

    st.subheader("📋 Planning")
    if not st.session_state.planning.empty:
        # On affiche une colonne Rider simple
        df_visu = st.session_state.planning.copy()
        df_visu.insert(0, "Rider", df_visu["Artiste"].apply(lambda x: "✅" if st.session_state.riders_stockage.get(x) else "❌"))
        
        edit_plan = st.data_editor(df_visu, use_container_width=True, num_rows="dynamic", key="editor_plan")
        
        # Détection suppression
        if st.session_state.editor_plan["deleted_rows"]:
            pop_supprimer_artiste(st.session_state.editor_plan["deleted_rows"][0])
        # Détection modification
        elif st.session_state.editor_plan["edited_rows"]:
            for idx, changes in st.session_state.editor_plan["edited_rows"].items():
                for col, val in changes.items():
                    if col != "Rider": st.session_state.planning.at[idx, col] = val
            st.rerun()

    st.divider()
    st.subheader("📁 Gestion des PDF")
    if st.session_state.riders_stockage:
        artistes_liste = list(st.session_state.riders_stockage.keys())
        c_sel, c_files = st.columns([1, 2])
        with c_sel:
            target = st.selectbox("Gérer les PDF de :", artistes_liste)
        with c_files:
            docs = st.session_state.riders_stockage.get(target, {})
            for name in list(docs.keys()):
                col_n, col_d = st.columns([4, 1])
                col_n.write(f"📄 {name}")
                if col_d.button("🗑️", key=f"del_{target}_{name}"):
                    del st.session_state.riders_stockage[target][name]
                    st.rerun()

# --- ONGLET 2 : PATCH & RÉGIE ---
with tabs[1]:
    if not st.session_state.planning.empty:
        # LIGNE 1 : FILTRES ALIGNÉS
        f1, f2, f3 = st.columns(3)
        sel_j = f1.selectbox("📅 Jour", sorted(st.session_state.planning["Jour"].unique()))
        scenes_disp = st.session_state.planning[st.session_state.planning["Jour"] == sel_j]["Scène"].unique()
        sel_s = f2.selectbox("🏗️ Scène", scenes_disp)
        artistes_disp = st.session_state.planning[(st.session_state.planning["Jour"] == sel_j) & (st.session_state.planning["Scène"] == sel_s)]["Artiste"].unique()
        sel_a = f3.selectbox("🎸 Groupe", artistes_disp)

        if sel_a:
            with st.container(border=True):
                c_cat, c_mar, c_mod, c_qte, c_app = st.columns([2, 2, 2, 1, 1])
                v_cat = c_cat.selectbox("Catégorie", ["MICROS", "HF", "EAR MONITOR", "BACKLINE"])
                v_mar = c_mar.selectbox("Marque", ["SHURE", "SENNHEISER", "AKG", "NEUMANN"])
                v_mod = c_mod.text_input("Modèle", "SM58")
                v_qte = c_qte.number_input("Qté", 1, 100, 1)
                v_app = c_app.checkbox("Artiste Apporte")
                
                if st.button("➕ Ajouter au Patch"):
                    mask = (st.session_state.fiches_tech["Groupe"] == sel_a) & \
                           (st.session_state.fiches_tech["Modèle"] == v_mod) & \
                           (st.session_state.fiches_tech["Artiste_Apporte"] == v_app)
                    if not st.session_state.fiches_tech[mask].empty:
                        st.session_state.fiches_tech.loc[mask, "Quantité"] += v_qte
                    else:
                        new_item = pd.DataFrame([{"Scène": sel_s, "Jour": sel_j, "Groupe": sel_a, "Catégorie": v_cat, "Marque": v_mar, "Modèle": v_mod, "Quantité": v_qte, "Artiste_Apporte": v_app}])
                        st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, new_item], ignore_index=True)
                    st.rerun()

            st.divider()

            # LIGNE 2 : CÔTE À CÔTE
            col_left, col_right = st.columns(2)
            
            with col_left:
                st.subheader(f"📋 Patch : {sel_a}")
                df_art = st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"] == sel_a]
                ed_patch = st.data_editor(df_art, use_container_width=True, num_rows="dynamic", key=f"ed_{sel_a}")
                
                if st.session_state[f"ed_{sel_a}"]["deleted_rows"]:
                    pop_supprimer_item(st.session_state[f"ed_{sel_a}"]["deleted_rows"][0], df_art)
                elif st.session_state[f"ed_{sel_a}"]["edited_rows"]:
                    for idx_rel, changes in st.session_state[f"ed_{sel_a}"]["edited_rows"].items():
                        st.session_state.fiches_tech.at[df_art.index[idx_rel], "Quantité"] = changes.get("Quantité", st.session_state.fiches_tech.at[df_art.index[idx_rel], "Quantité"])
                    st.rerun()

            with col_right:
                st.subheader(f"📊 Besoin {sel_s}")
                plan_j = st.session_state.planning[(st.session_state.planning["Jour"] == sel_j) & (st.session_state.planning["Scène"] == sel_s)].sort_values("Show")
                artistes_j = plan_j["Artiste"].tolist()
                df_b = st.session_state.fiches_tech[(st.session_state.fiches_tech["Scène"] == sel_s) & (st.session_state.fiches_tech["Jour"] == sel_j) & (st.session_state.fiches_tech["Artiste_Apporte"] == False)]

                if not df_b.empty:
                    # Calcul N+1
                    mat = df_b.groupby(["Catégorie", "Marque", "Modèle", "Groupe"])["Quantité"].sum().unstack(fill_value=0)
                    for a in artistes_j: 
                        if a not in mat.columns: mat[a] = 0
                    mat = mat[artistes_j]
                    if len(artistes_j) > 1:
                        res = pd.concat([mat.iloc[:, i] + mat.iloc[:, i+1] for i in range(len(artistes_j)-1)], axis=1).max(axis=1)
                    else:
                        res = mat.iloc[:, 0]
                    st.table(res.reset_index().rename(columns={0: "Quantité"}))
                else:
                    st.info("Aucun besoin.")
