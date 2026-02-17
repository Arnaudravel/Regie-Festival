import streamlit as st
import pandas as pd
import datetime
from fpdf import FPDF
import io

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Regie-Festival", layout="wide")

# --- INITIALISATION DES VARIABLES DE SESSION ---
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

# --- FONCTION TECHNIQUE POUR LE RENDU PDF (CORRIGÉE POUR LES BYTES) ---
def creer_pdf_depuis_df(titre, dataframe):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, titre, ln=True, align='C')
    pdf.ln(10)
    
    # Configuration des colonnes
    pdf.set_font("helvetica", "B", 10)
    cols = list(dataframe.columns)
    col_width = (pdf.w - 20) / len(cols)
    
    # En-tête du tableau
    pdf.set_fill_color(200, 220, 255)
    for col in cols:
        pdf.cell(col_width, 10, str(col), border=1, fill=True, align='C')
    pdf.ln()
    
    # Données
    pdf.set_font("helvetica", "", 9)
    for _, row in dataframe.iterrows():
        if pdf.get_y() > 260:
            pdf.add_page()
        for item in row:
            pdf.cell(col_width, 8, str(item), border=1, align='C')
        pdf.ln()
    
    # Sortie en bytes pour éviter l'erreur StreamlitAPIException
    return bytes(pdf.output())

# --- INTERFACE PRINCIPALE ---
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
        df_visu = st.session_state.planning.sort_values(by=["Jour", "Scène", "Show"]).copy()
        df_visu.insert(0, "Rider", df_visu["Artiste"].apply(lambda x: "✅" if st.session_state.riders_stockage.get(x) else "❌"))
        ed_plan = st.data_editor(df_visu, use_container_width=True, num_rows="dynamic", key="main_editor")
        if st.session_state.main_editor["deleted_rows"]:
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
                c_cat, c_mar, c_mod, c_qte, c_app = st.columns([2, 2, 2, 1, 1])
                v_cat = c_cat.selectbox("Catégorie", ["MICROS FILAIRE", "HF", "EAR MONITOR", "BACKLINE"])
                v_mar = c_mar.selectbox("Marque", ["SHURE", "SENNHEISER", "AKG", "NEUMANN"])
                v_mod = c_mod.text_input("Modèle", "SM58")
                v_qte = c_qte.number_input("Qté", 1, 500, 1)
                v_app = c_app.checkbox("Artiste Apporte")
                if st.button("Ajouter au Patch"):
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
                with st.status("⚠️ Retirer cet item ?", expanded=True):
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
                st.subheader(f"📋 Items pour {sel_a}")
                df_patch_art = st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"] == sel_a].sort_values(by=["Catégorie", "Marque"])
                ed_patch = st.data_editor(df_patch_art, use_container_width=True, num_rows="dynamic", key=f"ed_patch_{sel_a}")
                if st.session_state[f"ed_patch_{sel_a}"]["deleted_rows"]:
                    st.session_state.delete_confirm_patch_idx = df_patch_art.index[st.session_state[f"ed_patch_{sel_a}"]["deleted_rows"][0]]
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
                    st.dataframe(res.reset_index().rename(columns={0: "Total Journée"}).sort_values(by=["Catégorie", "Marque"]), use_container_width=True)

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
                titre = "Planning Global"
                if m_plan == "Par Jour": df_p = df_p[df_p["Jour"] == s_j_p]; titre = f"Planning {s_j_p}"
                elif m_plan == "Par Scène": df_p = df_p[df_p["Scène"] == s_s_p]; titre = f"Planning Scène {s_s_p}"
                pdf_p = creer_pdf_depuis_df(titre, df_p)
                st.download_button("📥 Télécharger PDF", pdf_p, f"{titre}.pdf", "application/pdf")

    with cex2:
        st.subheader("📦 Export Besoins")
        with st.container(border=True):
            m_bes = st.radio("Type", ["Par Jour & Scène", "Total Période par Scène"], key="mb")
            s_s_m = st.selectbox("Scène", l_scenes, key="ssm")
            s_j_m = st.selectbox("Jour", l_jours, key="sjm") if m_bes == "Par Jour & Scène" else None
            if st.button("Générer PDF Besoins", use_container_width=True):
                df_base = st.session_state.fiches_tech[(st.session_state.fiches_tech["Scène"] == s_s_m) & (st.session_state.fiches_tech["Artiste_Apporte"] == False)]
                if m_bes == "Par Jour & Scène":
                    df_j = df_base[df_base["Jour"] == s_j_m]
                    arts = st.session_state.planning[(st.session_state.planning["Jour"] == s_j_m) & (st.session_state.planning["Scène"] == s_s_m)].sort_values("Show")["Artiste"].tolist()
                    if arts and not df_j.empty:
                        mat = df_j.groupby(["Catégorie", "Marque", "Modèle", "Groupe"])["Quantité"].sum().unstack(fill_value=0)
                        for a in arts: 
                            if a not in mat.columns: mat[a] = 0
                        res = pd.concat([mat[arts].iloc[:, i] + mat[arts].iloc[:, i+1] for i in range(len(arts)-1)], axis=1).max(axis=1) if len(arts) > 1 else mat[arts].iloc[:, 0]
                        pdf_b = creer_pdf_depuis_df(f"Besoins {s_s_m} - {s_j_m}", res.reset_index().rename(columns={0: "Total"}))
                        st.download_button("📥 Télécharger PDF", pdf_b, f"besoins_{s_s_m}_{s_j_m}.pdf", "application/pdf")
                else:
                    all_needs = []
                    for j in df_base["Jour"].unique():
                        df_j = df_base[df_base["Jour"] == j]
                        arts = st.session_state.planning[(st.session_state.planning["Jour"] == j) & (st.session_state.planning["Scène"] == s_s_m)].sort_values("Show")["Artiste"].tolist()
                        if arts:
                            mat = df_j.groupby(["Catégorie", "Marque", "Modèle", "Groupe"])["Quantité"].sum().unstack(fill_value=0)
                            for a in arts: 
                                if a not in mat.columns: mat[a] = 0
                            res_j = pd.concat([mat[arts].iloc[:, i] + mat[arts].iloc[:, i+1] for i in range(len(arts)-1)], axis=1).max(axis=1) if len(arts) > 1 else mat[arts].iloc[:, 0]
                            all_needs.append(res_j)
                    if all_needs:
                        res_p = pd.concat(all_needs, axis=1).max(axis=1).reset_index().rename(columns={0: "Max Période"})
                        pdf_p = creer_pdf_depuis_df(f"Besoins MAX {s_s_m}", res_p)
                        st.download_button("📥 Télécharger PDF", pdf_p, f"Besoins_MAX_{s_s_m}.pdf", "application/pdf")
