import streamlit as st
import pandas as pd
from fpdf import FPDF
from PIL import Image
import base64
import io
import datetime
import json

# --- CONFIGURATION ---
st.set_page_config(page_title="Régie Festival Pro", layout="wide")

if 'nom_festival' not in st.session_state: st.session_state.nom_festival = "Mon Festival"
if 'logo_festival' not in st.session_state: st.session_state.logo_festival = None
if 'planning' not in st.session_state:
    st.session_state.planning = pd.DataFrame(columns=["Scène", "Jour", "Artiste", "Balance", "Show"])
if 'fiches_tech' not in st.session_state:
    st.session_state.fiches_tech = pd.DataFrame(columns=["Scène", "Jour", "Groupe", "Catégorie", "Marque", "Modèle", "Quantité", "Artiste_Apporte"])
if 'riders_stockage' not in st.session_state:
    st.session_state.riders_stockage = {} 
if 'pdf_uploader_key' not in st.session_state:
    st.session_state.pdf_uploader_key = 0
if 'bibliotheque' not in st.session_state:
    st.session_state.bibliotheque = {
        "MICROS FILAIRE": {"SHURE": ["SM58", "SM57", "BETA52"], "SENNHEISER": ["MD421", "E906"]},
        "REGIE": {"YAMAHA": ["QL1", "CL5"], "MIDAS": ["M32"]},
        "DI / LINE": {"BSS": ["AR133"], "RADIAL": ["J48"]}
    }

# --- FONCTIONS TECHNIQUES ---
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
        scenarios.append(matos[matos["Groupe"] == artistes_ord[-1]].groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].sum().reset_index())
    
    return pd.concat(scenarios).groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].max().reset_index()

# --- INTERFACE ---
c_logo, c_titre = st.columns([1, 4])
with c_logo:
    if st.session_state.logo_festival: st.image(st.session_state.logo_festival, width=100)
with c_titre: st.title(st.session_state.nom_festival)

tabs = st.tabs(["🏗️ Configuration", "⚙️ Patch & Régie", "📄 Exports PDF"])

# --- ONGLET 1 : CONFIGURATION ---
with tabs[0]:
    with st.expander("🛠️ Paramètres du Festival & Excel", expanded=False):
        c1, c2 = st.columns(2)
        st.session_state.nom_festival = c1.text_input("Nom du Festival", st.session_state.nom_festival)
        upl_logo = c2.file_uploader("Logo", type=["png", "jpg"])
        if upl_logo: st.session_state.logo_festival = Image.open(upl_logo)
        st.divider()
        f_excel = st.file_uploader("Charger Base Excel", type=["xlsx"])
        if f_excel and st.button("Mettre à jour la Bibliothèque"):
            st.session_state.bibliotheque = charger_bibliotheque_excel(f_excel)
            st.success("Bibliothèque mise à jour !")

    st.subheader("➕ Ajouter un Artiste")
    with st.container(border=True):
        cA, cB, cC, cD, cE = st.columns([1.5, 1.5, 3, 1, 1])
        n_sc = cA.text_input("Scène", "MainStage")
        n_jo = cB.date_input("Date", datetime.date.today())
        n_art = cC.text_input("Nom de l'Artiste")
        n_bal = cD.text_input("Balance", "14:00")
        n_sho = cE.text_input("Show", "20:00")
        n_pdf = st.file_uploader("Fiches Techniques (PDF)", accept_multiple_files=True, key=f"up_{st.session_state.pdf_uploader_key}")
        
        if st.button("Valider l'Artiste", type="primary"):
            if n_art:
                row = pd.DataFrame([{"Scène": n_sc, "Jour": n_jo, "Artiste": n_art, "Balance": n_bal, "Show": n_sho}])
                st.session_state.planning = pd.concat([st.session_state.planning, row], ignore_index=True)
                if n_pdf:
                    st.session_state.riders_stockage[n_art] = {f.name: f.read() for f in n_pdf}
                st.session_state.pdf_uploader_key += 1
                st.rerun()

    st.subheader("📅 Planning & Status")
    if not st.session_state.planning.empty:
        df_v = st.session_state.planning.copy()
        df_v.insert(0, "PDF", df_v["Artiste"].apply(lambda x: "✅" if st.session_state.riders_stockage.get(x) else "❌"))
        
        ed_p = st.data_editor(df_v, use_container_width=True, num_rows="dynamic", hide_index=True)
        if st.button("Enregistrer les modifications du planning"):
            st.session_state.planning = ed_p.drop(columns=["PDF"])
            st.rerun()

    st.divider()
    st.subheader("📁 Gestion des Fiches PDF")
    if st.session_state.riders_stockage:
        art_sel = st.selectbox("Sélectionner l'artiste pour gérer ses fichiers", list(st.session_state.riders_stockage.keys()))
        files = st.session_state.riders_stockage[art_sel]
        for fn in list(files.keys()):
            col_f1, col_f2 = st.columns([4, 1])
            col_f1.write(f"📄 {fn}")
            if col_f2.button("Supprimer", key=f"del_{fn}"):
                del st.session_state.riders_stockage[art_sel][fn]
                st.rerun()

# --- ONGLET 2 : PATCH ---
with tabs[1]:
    if not st.session_state.planning.empty:
        s1, s2, s3, s4 = st.columns([1, 1, 1, 2])
        sj = s1.selectbox("Jour", sorted(st.session_state.planning["Jour"].astype(str).unique()))
        ss = s2.selectbox("Scène", st.session_state.planning[st.session_state.planning["Jour"].astype(str)==sj]["Scène"].unique())
        sa = s3.selectbox("Artiste", st.session_state.planning[(st.session_state.planning["Jour"].astype(str)==sj) & (st.session_state.planning["Scène"]==ss)]["Artiste"].unique())
        
        with s4:
            pdfs = st.session_state.riders_stockage.get(sa, {})
            if pdfs:
                f_name = st.selectbox("Voir fiche :", list(pdfs.keys()), label_visibility="collapsed")
                b64 = base64.b64encode(pdfs[f_name]).decode('utf-8')
                st.markdown(f'<a href="data:application/pdf;base64,{b64}" target="_blank" download="{f_name}"><div style="background-color:#28a745;color:white;padding:10px;text-align:center;border-radius:5px;font-weight:bold;">📄 OUVRIR LA FICHE TECHNIQUE</div></a>', unsafe_allow_html=True)

        st.divider()
        cL, cR = st.columns(2)
        with cL:
            st.subheader(f"📥 Saisie Patch : {sa}")
            with st.container(border=True):
                cat = st.selectbox("Catégorie", list(st.session_state.bibliotheque.keys()))
                mar = st.selectbox("Marque", list(st.session_state.bibliotheque[cat].keys()))
                mod = st.selectbox("Modèle", st.session_state.bibliotheque[cat][mar] + ["Saisie Libre"])
                if mod == "Saisie Libre": mod = st.text_input("Entrez le modèle")
                q1, q2 = st.columns(2)
                qte = q1.number_input("Quantité", 1, 100, 1)
                app = q2.checkbox("Amené par l'Artiste")
                
                if st.button("Ajouter au Patch", use_container_width=True):
                    mask = (st.session_state.fiches_tech["Groupe"]==sa) & (st.session_state.fiches_tech["Modèle"]==mod) & (st.session_state.fiches_tech["Artiste_Apporte"]==app)
                    if not st.session_state.fiches_tech[mask].empty:
                        st.session_state.fiches_tech.loc[mask, "Quantité"] += qte
                    else:
                        new_l = pd.DataFrame([{"Scène":ss, "Jour":sj, "Groupe":sa, "Catégorie":cat, "Marque":mar, "Modèle":mod, "Quantité":qte, "Artiste_Apporte":app}])
                        st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, new_l], ignore_index=True)
                    st.rerun()
            
            st.data_editor(st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"]==sa], use_container_width=True, num_rows="dynamic")

        with cR:
            st.subheader(f"📊 Besoin {sj} - {ss}")
            st.dataframe(calculer_besoin_max_scene(st.session_state.fiches_tech, st.session_state.planning, ss, sj), use_container_width=True, hide_index=True)

# --- ONGLET 3 : EXPORTS ---
with tabs[2]:
    st.subheader("📄 Génération des documents")
    st.info("Les fonctions d'exportation PDF complètes sont prêtes à être générées ici.")
    # Boutons d'exports individuels à rajouter si besoin
