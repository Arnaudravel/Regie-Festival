import streamlit as st
import pandas as pd
from fpdf import FPDF
from PIL import Image
import base64
import io
import datetime
import json

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Régie Festival Pro", layout="wide")

if 'nom_festival' not in st.session_state: st.session_state.nom_festival = "Mon Festival"
if 'logo_festival' not in st.session_state: st.session_state.logo_festival = None
if 'planning' not in st.session_state:
    st.session_state.planning = pd.DataFrame(columns=["Scène", "Jour", "Artiste", "Balance", "Show"])
if 'fiches_tech' not in st.session_state:
    st.session_state.fiches_tech = pd.DataFrame(columns=["Scène", "Jour", "Groupe", "Catégorie", "Marque", "Modèle", "Quantité", "Artiste_Apporte"])
if 'riders_stockage' not in st.session_state:
    st.session_state.riders_stockage = {} 
if 'pdf_reset_key' not in st.session_state:
    st.session_state.pdf_reset_key = 0
if 'bibliotheque' not in st.session_state:
    st.session_state.bibliotheque = {
        "MICROS FILAIRE": {"SHURE": ["SM58", "SM57", "BETA52"], "SENNHEISER": ["MD421", "E906"]},
        "REGIE": {"YAMAHA": ["QL1", "CL5"], "MIDAS": ["M32"]},
        "DI / LINE": {"BSS": ["AR133"], "RADIAL": ["J48"]}
    }

# --- 2. FONCTIONS ---
def charger_bibliotheque_excel(file):
    try:
        dict_final = {}
        all_sheets = pd.read_excel(file, sheet_name=None)
        for sheet_name, df in all_sheets.items():
            cat_name = sheet_name.replace("DONNEES ", "").upper()
            dict_final[cat_name] = {}
            for col in df.columns:
                brand_name = col.split('_')[0].upper()
                models = df[col].dropna().astype(str).tolist()
                if models: dict_final[cat_name][brand_name] = models
        return dict_final
    except Exception as e:
        st.error(f"Erreur Excel : {e}")
        return st.session_state.bibliotheque

def calculer_besoin_max_scene(df_tech, planning, scene, jour):
    plan = planning[(planning["Scène"] == scene) & (planning["Jour"] == jour)].copy().sort_values(by="Show")
    if plan.empty: return pd.DataFrame()
    artistes_ord = plan["Artiste"].tolist()
    matos = df_tech[(df_tech["Scène"] == scene) & (df_tech["Jour"] == jour) & (df_tech["Artiste_Apporte"] == False)]
    if matos.empty: return pd.DataFrame()
    
    scenarios = []
    if len(artistes_ord) == 1:
        scenarios.append(matos.groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].sum().reset_index())
    else:
        for i in range(len(artistes_ord) - 1):
            binome = matos[matos["Groupe"].isin([artistes_ord[i], artistes_ord[i+1]])]
            scenarios.append(binome.groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].sum().reset_index())
        # Ajout du dernier groupe seul
        scenarios.append(matos[matos["Groupe"] == artistes_ord[-1]].groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].sum().reset_index())
    
    return pd.concat(scenarios).groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].max().reset_index()

# --- 3. INTERFACE ---
c1, c2 = st.columns([1, 4])
with c1: 
    if st.session_state.logo_festival: st.image(st.session_state.logo_festival, width=100)
with c2: st.title(st.session_state.nom_festival)

tabs = st.tabs(["🏗️ Configuration", "⚙️ Patch & Régie", "📄 Exports PDF"])

# --- TAB 1 : CONFIGURATION & PLANNING ---
with tabs[0]:
    with st.expander("🛠️ Paramètres & Import Excel", expanded=False):
        cx1, cx2 = st.columns(2)
        st.session_state.nom_festival = cx1.text_input("Nom Festival", st.session_state.nom_festival)
        upl_l = cx2.file_uploader("Logo", type=["png", "jpg"])
        if upl_l: st.session_state.logo_festival = Image.open(upl_l)
        st.divider()
        f_ex = st.file_uploader("Charger Bibliothèque Excel", type=["xlsx"])
        if f_ex and st.button("Mettre à jour Matériel"):
            st.session_state.bibliotheque = charger_bibliotheque_excel(f_ex)
            st.success("Bibliothèque mise à jour !")

    st.subheader("➕ Ajouter un Artiste")
    with st.container(border=True):
        colA, colB, colC, colD, colE = st.columns([1.5, 1.5, 3, 1, 1])
        n_sc = colA.text_input("Scène", "MainStage")
        n_jo = colB.date_input("Date", datetime.date.today())
        n_art = colC.text_input("Nom Artiste")
        n_bal = colD.text_input("Balance (HH:mm)", "14:00")
        n_sho = colE.text_input("Show (HH:mm)", "20:00")
        
        # Correction : Clé unique pour vider l'uploader après validation
        n_pdf = st.file_uploader("Fiches PDF", accept_multiple_files=True, key=f"pdf_up_{st.session_state.pdf_reset_key}")
        
        if st.button("Valider l'Artiste", type="primary"):
            if n_art:
                row = pd.DataFrame([{"Scène": n_sc, "Jour": n_jo, "Artiste": n_art, "Balance": n_bal, "Show": n_sho}])
                st.session_state.planning = pd.concat([st.session_state.planning, row], ignore_index=True)
                if n_pdf:
                    st.session_state.riders_stockage[n_art] = {f.name: f.read() for f in n_pdf}
                st.session_state.pdf_reset_key += 1
                st.rerun()

    st.subheader("📅 Planning & Status PDF")
    if not st.session_state.planning.empty:
        # Affichage avec croix rouge/verte
        df_visu = st.session_state.planning.copy()
        df_visu.insert(0, "Fiches PDF", df_visu["Artiste"].apply(lambda x: "✅" if st.session_state.riders_stockage.get(x) else "❌"))
        
        # Tableau entièrement éditable et supprimable
        ed_plan = st.data_editor(df_visu, use_container_width=True, num_rows="dynamic", hide_index=True)
        if st.button("Sauvegarder les modifications (Planning)"):
            st.session_state.planning = ed_plan.drop(columns=["Fiches PDF"])
            st.rerun()
            
    st.divider()
    st.subheader("📁 Gestion des fichiers chargés")
    if st.session_state.riders_stockage:
        art_sel = st.selectbox("Choisir un artiste pour gérer ses PDF", list(st.session_state.riders_stockage.keys()))
        files = st.session_state.riders_stockage[art_sel]
        if files:
            for fname in list(files.keys()):
                c_f1, c_f2 = st.columns([4, 1])
                c_f1.write(f"📄 {fname}")
                if c_f2.button(f"Supprimer", key=f"del_{art_sel}_{fname}"):
                    del st.session_state.riders_stockage[art_sel][fname]
                    st.rerun()

# --- TAB 2 : PATCH (L'interface fidèle) ---
with tabs[1]:
    if not st.session_state.planning.empty:
        cp1, cp2, cp3, cp4 = st.columns([1, 1, 1, 2])
        sel_j = cp1.selectbox("Jour", sorted(st.session_state.planning["Jour"].astype(str).unique()))
        sel_s = cp2.selectbox("Scène", st.session_state.planning[st.session_state.planning["Jour"].astype(str)==sel_j]["Scène"].unique())
        sel_a = cp3.selectbox("Artiste", st.session_state.planning[(st.session_state.planning["Jour"].astype(str)==sel_j) & (st.session_state.planning["Scène"]==sel_s)]["Artiste"].unique())
        
        # Bouton PDF Vert
        with cp4:
            pdf_list = st.session_state.riders_stockage.get(sel_a, {})
            if pdf_list:
                f_view = st.selectbox("Fiche :", list(pdf_list.keys()), label_visibility="collapsed")
                b64 = base64.b64encode(pdf_list[f_view]).decode('utf-8')
                st.markdown(f'<a href="data:application/pdf;base64,{b64}" target="_blank" download="{f_view}"><div style="background-color:#28a745;color:white;padding:10px;text-align:center;border-radius:5px;font-weight:bold;">📄 OUVRIR LA FICHE TECHNIQUE</div></a>', unsafe_allow_html=True)

        st.divider()
        col_L, col_R = st.columns(2)
        with col_L:
            st.subheader(f"📥 Saisie : {sel_a}")
            with st.container(border=True):
                i_cat = st.selectbox("Catégorie", list(st.session_state.bibliotheque.keys()))
                i_mar = st.selectbox("Marque", list(st.session_state.bibliotheque[i_cat].keys()))
                i_mod = st.selectbox("Modèle", st.session_state.bibliotheque[i_cat][i_mar] + ["Saisie Libre"])
                if i_mod == "Saisie Libre": i_mod = st.text_input("Référence")
                c_q1, c_q2 = st.columns(2)
                i_qte = c_q1.number_input("Quantité", 1, 100, 1)
                i_app = c_q2.checkbox("Amené par l'Artiste")
                
                if st.button("Ajouter au Patch", use_container_width=True):
                    df_p = st.session_state.fiches_tech
                    mask = (df_p["Groupe"]==sel_a) & (df_p["Modèle"]==i_mod) & (df_p["Artiste_Apporte"]==i_app)
                    if not df_p[mask].empty:
                        st.session_state.fiches_tech.loc[mask, "Quantité"] += i_qte
                    else:
                        new_l = pd.DataFrame([{"Scène":sel_s, "Jour":sel_j, "Groupe":sel_a, "Catégorie":i_cat, "Marque":i_mar, "Modèle":i_mod, "Quantité":i_qte, "Artiste_Apporte":i_app}])
                        st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, new_l], ignore_index=True)
                    st.rerun()

            st.data_editor(st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"]==sel_a], num_rows="dynamic", use_container_width=True)

        with col_R:
            st.subheader(f"📊 Besoin {sel_j} - {sel_s}")
            st.dataframe(calculer_besoin_max_scene(st.session_state.fiches_tech, st.session_state.planning, sel_s, sel_j), use_container_width=True, hide_index=True)

# --- TAB 3 : EXPORTS ---
with tabs[2]:
    st.subheader("📄 Génération des documents")
    # Ici tu peux remettre tes boutons d'exports individuels selon tes besoins
    if st.button("Générer PDF Planning"):
        st.write("Fonctionnalité en cours de génération...")
