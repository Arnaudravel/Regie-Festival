import streamlit as st
import pandas as pd
from fpdf import FPDF
from PIL import Image
import base64
import io
import datetime

# --- 1. CONFIGURATION & STATE ---
st.set_page_config(page_title="Régie Festival Pro", layout="wide")

if 'nom_festival' not in st.session_state: st.session_state.nom_festival = "Nouveau Festival"
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
        "MICROS FILAIRE": {"SHURE": ["SM58", "SM57", "BETA52", "BETA58", "BETA91"], "SENNHEISER": ["MD421", "E906", "E604"]},
        "REGIE": {"YAMAHA": ["QL1", "CL5", "PM7"], "MIDAS": ["M32", "PRO2"]},
        "MICROS HF": {"SHURE": ["AD4D", "AXIENT"], "SENNHEISER": ["6000 Series"]},
        "EAR MONITOR": {"SHURE": ["PSM1000"], "SENNHEISER": ["2000 Series"]}
    }

# --- 2. MOTEUR DE CALCUL (LOGIQUE N+N+1) ---
def calculer_besoin_journee(df_tech, planning, scene, jour):
    plan = planning[(planning["Scène"] == scene) & (planning["Jour"] == jour)].copy().sort_values(by="Show")
    artistes = plan["Artiste"].tolist()
    
    if not artistes: return pd.DataFrame()
    
    matos_regie = df_tech[(df_tech["Scène"] == scene) & (df_tech["Jour"] == jour) & (df_tech["Artiste_Apporte"] == False)]
    
    if matos_regie.empty: return pd.DataFrame()
    
    if len(artistes) == 1:
        return matos_regie.groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].sum().reset_index()

    besoins_binomes = []
    for i in range(len(artistes) - 1):
        groupe_actuel = artistes[i]
        groupe_suivant = artistes[i+1]
        df_binome = matos_regie[matos_regie["Groupe"].isin([groupe_actuel, groupe_suivant])]
        somme_binome = df_binome.groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].sum()
        besoins_binomes.append(somme_binome)
    
    if besoins_binomes:
        res = pd.concat(besoins_binomes, axis=1).max(axis=1).reset_index()
        res.columns = ["Catégorie", "Marque", "Modèle", "Quantité"]
        return res
    else:
        return pd.DataFrame()

# --- 3. CLASSES D'EXPORT PDF ---

class FestivalPDF(FPDF):
    def header(self):
        if st.session_state.logo_festival:
            img = st.session_state.logo_festival
            with io.BytesIO() as buf:
                img.save(buf, format='PNG')
                with open("temp_logo.png", "wb") as f: f.write(buf.getvalue())
            self.image("temp_logo.png", 10, 8, 25)
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, st.session_state.nom_festival, 0, 1, 'R')
        self.ln(10)

def export_categorized_pdf(df, title):
    pdf = FestivalPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, title, ln=True, align='C')
    pdf.ln(10)
    
    if df.empty:
        pdf.set_font("Arial", 'I', 12)
        pdf.cell(0, 10, "Aucun matériel requis.", ln=True)
        return pdf.output(dest='S').encode('latin-1')

    categories = df["Catégorie"].unique()
    for cat in categories:
        df_cat = df[df["Catégorie"] == cat]
        pdf.set_fill_color(200, 220, 255) 
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, f"Catégorie : {cat}", ln=True, fill=True)
        
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Arial", 'B', 9)
        cols = ["Marque", "Modèle", "Quantité"]
        widths = [50, 100, 30]
        for i, col in enumerate(cols):
            pdf.cell(widths[i], 8, str(col), 1, 0, 'C', True)
        pdf.ln()
        
        pdf.set_font("Arial", '', 9)
        for _, row in df_cat.iterrows():
            pdf.cell(widths[0], 7, str(row["Marque"]), 1)
            pdf.cell(widths[1], 7, str(row["Modèle"]), 1)
            pdf.cell(widths[2], 7, str(row["Quantité"]), 1, 0, 'C')
            pdf.ln()
        pdf.ln(5)
    return pdf.output(dest='S').encode('latin-1')

def export_planning_structured(df, title):
    pdf = FestivalPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 18)
    pdf.cell(0, 15, title, ln=True, align='C')
    pdf.ln(5)
    
    jours_uniques = sorted(df["Jour"].unique())

    for jour in jours_uniques:
        pdf.set_fill_color(50, 50, 50) 
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 14)
        date_str = jour.strftime('%d/%m/%Y') if isinstance(jour, datetime.date) else str(jour)
        pdf.cell(0, 10, f"DATE : {date_str}", 1, 1, 'L', True)
        pdf.set_text_color(0, 0, 0)
        
        df_jour = df[df["Jour"] == jour]
        scenes_uniques = sorted(df_jour["Scène"].unique())

        for scene in scenes_uniques:
            pdf.ln(2)
            pdf.set_fill_color(220, 230, 255)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 8, f"SCÈNE : {scene}", "L", 1, 'L', True)
            
            df_scene = df_jour[df_jour["Scène"] == scene].sort_values(by="Show")
            
            pdf.set_fill_color(240, 240, 240)
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(30, 8, "SHOW", 1, 0, 'C', True)
            pdf.cell(100, 8, "ARTISTE", 1, 0, 'C', True)
            pdf.cell(30, 8, "BALANCE", 1, 0, 'C', True)
            pdf.ln()
            
            pdf.set_font("Arial", '', 10)
            for _, row in df_scene.iterrows():
                pdf.cell(30, 8, str(row["Show"]), 1, 0, 'C')
                pdf.cell(100, 8, str(row["Artiste"]), 1, 0, 'L')
                pdf.cell(30, 8, str(row["Balance"]), 1, 0, 'C')
                pdf.ln()
            pdf.ln(3)
        pdf.ln(5)

    return pdf.output(dest='S').encode('latin-1')

# --- 4. INTERFACE ---
c_h1, c_h2 = st.columns([1, 4])
with c_h1: 
    if st.session_state.logo_festival: st.image(st.session_state.logo_festival, width=100)
with c_h2: 
    st.title(st.session_state.nom_festival)

# MODIFICATION : Suppression de l'onglet Admin
tabs = st.tabs(["🏗️ Configuration", "⚙️ Patch & Régie", "📄 Exports PDF"])

# --- ONGLET 1 : CONFIGURATION ---
with tabs[0]:
    c1, c2 = st.columns(2)
    st.session_state.nom_festival = c1.text_input("Nom du Festival", st.session_state.nom_festival)
    upl_logo = c2.file_uploader("Logo", type=["png", "jpg"])
    if upl_logo: st.session_state.logo_festival = Image.open(upl_logo)

    with st.expander("➕ Ajouter un Artiste", expanded=True):
        col1, col2, col3, col4, col5 = st.columns(5)
        in_sc = col1.text_input("Scène", "MainStage")
        in_jo = col2.date_input("Date de passage", datetime.date.today())
        in_art = col3.text_input("Nom Artiste")
        in_bal = col4.text_input("Balance", "14:00")
        in_sho = col5.text_input("Show", "20:00")
        
        in_files = st.file_uploader("Fiches Techniques (PDF)", accept_multiple_files=True, key=f"pdf_up_{st.session_state.pdf_uploader_key}")

        if st.button("Valider Artiste"):
            if in_art:
                new_row = pd.DataFrame([{"Scène":in_sc, "Jour":in_jo, "Artiste":in_art, "Balance":in_bal, "Show":in_sho}])
                st.session_state.planning = pd.concat([st.session_state.planning, new_row], ignore_index=True)
                st.session_state.riders_stockage[in_art] = {} 
                if in_files:
                    for f in in_files:
                        st.session_state.riders_stockage[in_art][f.name] = f.read()
                st.session_state.pdf_uploader_key += 1
                st.rerun()

    st.subheader("Planning Global")
    if not st.session_state.planning.empty:
        df_plan_view = st.session_state.planning.copy()
        status_col = []
        for art in df_plan_view["Artiste"]:
            nb_files = len(st.session_state.riders_stockage.get(art, {}))
            status_col.append("✅ PDF Chargé" if nb_files > 0 else "❌ Aucun PDF")
        
        df_plan_view.insert(0, "Rider", status_col)
        ed_plan = st.data_editor(df_plan_view, num_rows="dynamic", use_container_width=True, key="plan_edit_main")
        if st.button("Enregistrer Planning"):
            st.session_state.planning = ed_plan.drop(columns=["Rider"])
            st.rerun()

    if not st.session_state.planning.empty:
        st.divider()
        st.subheader("📁 Gestion des Fichiers PDF")
        c_adm1, c_adm2, c_adm3 = st.columns([1, 1.5, 1])
        sel_art_adm = c_adm1.selectbox("Choisir Artiste :", st.session_state.planning["Artiste"].unique(), key="sel_art_pdf")
        
        with c_adm2:
            files_dict = st.session_state.riders_stockage.get(sel_art_adm, {})
            if not files_dict: st.warning("Aucun fichier pour cet artiste.")
            for fname in list(files_dict.keys()):
                cc1, cc2 = st.columns([4, 1])
                cc1.text(f"📄 {fname}")
                # MODIFICATION : Changement de la corbeille par une croix rouge ❌
                if cc2.button("❌", key=f"del_{sel_art_adm}_{fname}"):
                    del st.session_state.riders_stockage[sel_art_adm][fname]
                    st.rerun()
        
        with c_adm3:
            add_files = st.file_uploader("Ajouter des PDF", accept_multiple_files=True, key=f"add_pdf_{sel_art_adm}")
            if st.button("Sauvegarder Ajout"):
                if add_files:
                    if sel_art_adm not in st.session_state.riders_stockage: st.session_state.riders_stockage[sel_art_adm] = {}
                    for f in add_files:
                        st.session_state.riders_stockage[sel_art_adm][f.name] = f.read()
                    st.rerun()

# --- ONGLET 2 : PATCH ---
with tabs[1]:
    if not st.session_state.planning.empty:
        col_sel1, col_sel2, col_sel3, col_sel4 = st.columns([1, 1, 1, 2])
        p_jour = col_sel1.selectbox("Jour", sorted(st.session_state.planning["Jour"].unique()), key="pj")
        p_scene = col_sel2.selectbox("Scène", st.session_state.planning[st.session_state.planning["Jour"]==p_jour]["Scène"].unique(), key="ps")
        p_art = col_sel3.selectbox("Artiste", st.session_state.planning[(st.session_state.planning["Jour"]==p_jour) & (st.session_state.planning["Scène"]==p_scene)]["Artiste"].unique(), key="pa")
        
        pdfs_art = st.session_state.riders_stockage.get(p_art, {})
        with col_sel4:
            if pdfs_art:
                to_view = st.selectbox("Voir Rider :", list(pdfs_art.keys()), key="view_pdf")
                b64_pdf = base64.b64encode(pdfs_art[to_view]).decode('utf-8')
                # MODIFICATION : Changement couleur de fond du bouton en VERT (#28a745)
                st.markdown(f'<a href="data:application/pdf;base64,{b64_pdf}" target="_blank" download="{to_view}"><button style="background-color:#28a745;color:white;border:none;padding:8px;border-radius:4px;width:100%;cursor:pointer;">📖 OUVRIR {to_view}</button></a>', unsafe_allow_html=True)
            else:
                st.info("Aucun PDF disponible")

        with st.expander(f"📥 Saisie Matériel : {p_art}", expanded=True):
            ci1, ci2, ci3, ci4, ci5 = st.columns([2, 2, 2, 1, 1])
            m_cat = ci1.selectbox("Catégorie", list(st.session_state.bibliotheque.keys()), key="mc")
            m_mar = ci2.selectbox("Marque", list(st.session_state.bibliotheque[m_cat].keys()), key="mm")
            m_mod = ci3.selectbox("Modèle", st.session_state.bibliotheque[m_cat][m_mar] + ["+ LIBRE"], key="mo")
            if m_mod == "+ LIBRE": m_mod = ci3.text_input("Référence Libre")
            m_qte = ci4.number_input("Qté", 1, 200, 1)
            m_app = ci5.checkbox("Artiste Apporte")

            if st.button("Ajouter au Patch"):
                new_line = pd.DataFrame([{"Scène":p_scene, "Jour":p_jour, "Groupe":p_art, "Catégorie":m_cat, "Marque":m_mar, "Modèle":m_mod, "Quantité":m_qte, "Artiste_Apporte":m_app}])
                st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, new_line], ignore_index=True)
                st.rerun()

        st.divider()
        cl, cr = st.columns([1.3, 0.7])
        with cl:
            st.subheader(f"📋 Patch de {p_art}")
            mask_patch = (st.session_state.fiches_tech["Groupe"] == p_art) & (st.session_state.fiches_tech["Jour"] == p_jour)
            df_curr_patch = st.session_state.fiches_tech[mask_patch].copy()
            ed_patch = st.data_editor(df_curr_patch, num_rows="dynamic", use_container_width=True, key=f"editor_{p_art}")
            if st.button("Sauvegarder Patch"):
                st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech[~mask_patch], ed_patch], ignore_index=True)
                st.rerun()
        
        with cr:
            st.subheader(f"📊 Besoin {p_scene} {p_jour}")
            df_calc = calculer_besoin_journee(st.session_state.fiches_tech, st.session_state.planning, p_scene, p_jour)
            st.dataframe(df_calc, hide_index=True, use_container_width=True)

# --- ONGLET 3 : EXPORTS ---
with tabs[2]:
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        st.subheader("📅 Export Planning")
        scope_plan = st.radio("Périmètre :", ["Par Scène / Jour", "Toute la Journée (Toutes scènes)", "Tout le Festival"], key="scope_p")
        
        if scope_plan == "Par Scène / Jour":
            p_s = st.selectbox("Quelle Scène ?", st.session_state.planning["Scène"].unique() if not st.session_state.planning.empty else [], key="exp_s_p")
            p_j = st.selectbox("Quel Jour ?", sorted(st.session_state.planning["Jour"].unique()) if not st.session_state.planning.empty else [], key="exp_j_p")
        elif scope_plan == "Toute la Journée (Toutes scènes)":
            p_j = st.selectbox("Quel Jour ?", sorted(st.session_state.planning["Jour"].unique()) if not st.session_state.planning.empty else [], key="exp_j_p_all")
            
        if st.button("Générer PDF Planning"):
            if scope_plan == "Par Scène / Jour":
                df_export = st.session_state.planning[(st.session_state.planning["Scène"] == p_s) & (st.session_state.planning["Jour"] == p_j)]
                title = f"Planning {p_s} - {p_j}"
            elif scope_plan == "Toute la Journée (Toutes scènes)":
                df_export = st.session_state.planning[st.session_state.planning["Jour"] == p_j]
                title = f"Planning Global - {p_j}"
            else:
                df_export = st.session_state.planning
                title = "Planning Général Festival"
            
            pdf_data = export_planning_structured(df_export, title)
            st.download_button("📥 Télécharger Planning", pdf_data, "planning.pdf")

    with col_exp2:
        st.subheader("🛠️ Export Matériel")
        scope_matos = st.radio("Type de Rapport :", ["Besoin Journée (N+N+1)", "Besoin Global Scène (Max des Max)"], key="scope_m")
        m_s_list = st.session_state.planning["Scène"].unique() if not st.session_state.planning.empty else []
        m_s = st.selectbox("Quelle Scène ?", m_s_list, key="exp_s_m")
        
        if scope_matos == "Besoin Journée (N+N+1)":
            m_j = st.selectbox("Quel Jour ?", sorted(st.session_state.planning["Jour"].unique()) if not st.session_state.planning.empty else [], key="exp_j_m")
            
        if st.button("Générer Rapport Matériel"):
            if scope_matos == "Besoin Journée (N+N+1)":
                res = calculer_besoin_journee(st.session_state.fiches_tech, st.session_state.planning, m_s, m_j)
                title = f"Besoin Régie {m_s} - {m_j}"
            else:
                jours_scene = st.session_state.planning[st.session_state.planning["Scène"] == m_s]["Jour"].unique()
                dfs_jours = [calculer_besoin_journee(st.session_state.fiches_tech, st.session_state.planning, m_s, j) for j in jours_scene]
                res = pd.concat(dfs_jours).groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].max().reset_index() if dfs_jours else pd.DataFrame()
                title = f"Besoin Global {m_s}"
                
            pdf_matos = export_categorized_pdf(res, title)
            st.download_button("📥 Télécharger Rapport", pdf_matos, "liste_materiel.pdf")