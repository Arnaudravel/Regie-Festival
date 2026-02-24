import streamlit as st
import pandas as pd
import datetime
from fpdf import FPDF
import io
import pickle
import base64
import plotly.express as px
import streamlit.components.v1 as components

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Regie-Festival", layout="wide", initial_sidebar_state="collapsed")

# --- CACHER LES BOUTONS DE TELECHARGEMENT DES TABLEAUX ---
st.markdown(
    """
    <style>
    [data-testid="stElementToolbar"] {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True
)

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

# --- HELPER : LISTE DES HEURES ---
def get_time_options():
    times = ["-- none --"]
    for h in range(24):
        for m in (0, 15, 30, 45):
            times.append(f"{h:02d}:{m:02d}")
    return times

time_options = get_time_options()

# --- INITIALISATION DES VARIABLES DE SESSION ---
cols_planning = [
    "Scène", "Jour", "Artiste", 
    "Load IN Début", "Load IN Fin", 
    "Inst Off Début", "Inst Off Fin", 
    "Inst On Début", "Inst On Fin", 
    "Balance Début", "Balance Fin", 
    "Change Over Début", "Change Over Fin", 
    "Show Début", "Show Fin"
]

if 'planning' not in st.session_state:
    st.session_state.planning = pd.DataFrame(columns=cols_planning)
else:
    # Mise à jour de compatibilité si un ancien fichier de sauvegarde est chargé
    for col in cols_planning:
        if col not in st.session_state.planning.columns:
            st.session_state.planning[col] = "-- none --"

if 'fiches_tech' not in st.session_state:
    st.session_state.fiches_tech = pd.DataFrame(columns=["Scène", "Jour", "Groupe", "Catégorie", "Marque", "Modèle", "Quantité", "Artiste_Apporte"])
if 'riders_stockage' not in st.session_state:
    st.session_state.riders_stockage = {}
if 'artist_circuits' not in st.session_state:
    st.session_state.artist_circuits = {}
if 'patches_io' not in st.session_state:
    st.session_state.patches_io = {}
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
if 'easyjob_mapping' not in st.session_state:
    st.session_state.easyjob_mapping = {}
if 'save_path' not in st.session_state:
    st.session_state.save_path = f"backup_festival.pkl"
if 'notes_artistes' not in st.session_state:
    st.session_state.notes_artistes = {}
if 'alim_elec' not in st.session_state:
    st.session_state.alim_elec = pd.DataFrame(columns=["Scène", "Jour", "Groupe", "Format", "Métier", "Emplacement"])

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

    def dessiner_texte(self, texte):
        self.set_font("helvetica", "", 10)
        val = str(texte).encode('latin-1', 'replace').decode('latin-1')
        self.multi_cell(0, 6, val)
        self.ln(5)

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
            if self.get_y() > (self.h - 20): self.add_page()
            for item in row:
                val = str(item).replace('\n', ' ').encode('latin-1', 'replace').decode('latin-1')
                self.cell(col_width, 6, val, border=1, align='C')
            self.ln()
        self.ln(5)

    def dessiner_tableau_patch(self, df):
        if df.empty: return
        self.set_font("helvetica", "B", 9)
        cols = list(df.columns)
        col_width = (self.w - 20) / len(cols)
        
        self.set_fill_color(220, 230, 255)
        for col in cols:
            self.cell(col_width, 8, str(col), border=1, fill=True, align='C')
        self.ln()
    
        self.set_font("helvetica", "", 8)
        
        EMOJI_COLORS = {
            "🟤": (205, 133, 63), "🔴": (255, 153, 153), "🟠": (255, 204, 153),
            "🟡": (255, 255, 153), "🟢": (153, 255, 153), "🔵": (153, 204, 255),
            "🟣": (204, 153, 255), "⚪": (240, 240, 240), "🍏": (204, 255, 153)
        }

        for _, row in df.iterrows():
            if self.get_y() > (self.h - 20): self.add_page()
            
            row_color = (255, 255, 255)
            row_texts = []
            
            for item in row:
                if isinstance(item, bool): val = "[ X ]" if item else "[   ]"
                elif str(item).strip() == "True": val = "[ X ]"
                elif str(item).strip() == "False": val = "[   ]"
                else: val = str(item) if pd.notna(item) else ""

                for emoji, color in EMOJI_COLORS.items():
                    if emoji in val:
                        row_color = color
                        val = val.replace(emoji, "").strip()
            
                val = val.replace('\n', ' ').encode('latin-1', 'replace').decode('latin-1')
                row_texts.append(val)
            
            self.set_fill_color(*row_color)
            for val in row_texts:
                self.cell(col_width, 6, val, border=1, align='C', fill=True)
            self.ln()
        self.ln(5)

def generer_pdf_complet(titre_doc, dictionnaire_dfs, orientation='P', format='A4'):
    pdf = FestivalPDF(orientation=orientation, unit='mm', format=format)
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, titre_doc, ln=True, align='C')
    pdf.ln(5)
    
    for section, data in dictionnaire_dfs.items():
        if isinstance(data, pd.DataFrame):
            if not data.empty:
                if pdf.get_y() > (pdf.h - 30): pdf.add_page()
                pdf.ajouter_titre_section(section)
                pdf.dessiner_tableau(data)
        elif isinstance(data, str) and data.strip():
            if pdf.get_y() > (pdf.h - 30): pdf.add_page()
            pdf.ajouter_titre_section(section)
            pdf.dessiner_texte(data)
            
    return pdf.output(dest='S').encode('latin-1')

def generer_pdf_patch(titre_doc, dictionnaire_dfs):
    pdf = FestivalPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, titre_doc, ln=True, align='C')
    pdf.ln(5)
    
    for section, data in dictionnaire_dfs.items():
        if isinstance(data, pd.DataFrame):
            if not data.empty:
                if pdf.get_y() > 250: pdf.add_page()
                pdf.ajouter_titre_section(section)
                pdf.dessiner_tableau_patch(data)
        elif isinstance(data, str) and data.strip():
            if pdf.get_y() > 250: pdf.add_page()
            pdf.ajouter_titre_section(section)
            pdf.dessiner_texte(data)
            
    return pdf.output(dest='S').encode('latin-1')

# --- Helper extraction chronologique plannings ---
def get_chronological_planning(df_scene):
    events = []
    phases = [
        ("Load IN", "Load IN Début", "Load IN Fin"),
        ("Inst Off Stage", "Inst Off Début", "Inst Off Fin"),
        ("Inst On Stage", "Inst On Début", "Inst On Fin"),
        ("Balance", "Balance Début", "Balance Fin"),
        ("Change Over", "Change Over Début", "Change Over Fin"),
        ("Show", "Show Début", "Show Fin")
    ]
    for _, row in df_scene.iterrows():
        art = row["Artiste"]
        for phase_name, c_deb, c_fin in phases:
            deb = row.get(c_deb, "-- none --")
            fin = row.get(c_fin, "-- none --")
            if deb != "-- none --" or fin != "-- none --":
                sort_time = deb if deb != "-- none --" else "24:00"
                events.append({
                    "Heure Début": deb if deb != "-- none --" else "",
                    "Heure Fin": fin if fin != "-- none --" else "",
                    "Artiste": art,
                    "Phase": phase_name,
                    "sort_key": sort_time
                })
    df_events = pd.DataFrame(events)
    if not df_events.empty:
        df_events = df_events.sort_values("sort_key").drop(columns=["sort_key"])
    return df_events

# --- INTERFACE PRINCIPALE ---
st.title(f"{st.session_state.festival_name} - Gestion Régie")

# --- CREATION DES ONGLETS PRINCIPAUX ---
main_tabs = st.tabs(["PROJET", "Gestion des artistes / Planning festival", "Technique"])

# ==========================================
# ONGLET 1 : PROJET
# ==========================================
with main_tabs[0]:
    sub_tabs_projet = st.tabs(["Admin & Sauvegarde", "Export"])
    
    # --- SOUS-ONGLET 1 : ADMIN & SAUVEGARDE ---
    with sub_tabs_projet[0]:
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
                    "artist_circuits": st.session_state.artist_circuits,
                    "patches_io": st.session_state.patches_io,
                    "festival_name": st.session_state.festival_name,
                    "festival_logo": st.session_state.festival_logo,
                    "custom_catalog": st.session_state.custom_catalog,
                    "easyjob_mapping": st.session_state.easyjob_mapping,
                    "notes_artistes": st.session_state.notes_artistes,
                    "alim_elec": st.session_state.alim_elec
                }
                
                path_input = st.text_input("📍 Chemin / Nom du fichier de sauvegarde (.pkl)", value=st.session_state.save_path)
                
                c_sv1, c_sv2 = st.columns(2)
                with c_sv1:
                    if st.button("💾 Save (Écraser)", use_container_width=True):
                        try:
                            with open(st.session_state.save_path, "wb") as f:
                                pickle.dump(data_to_save, f)
                            st.success(f"✅ Sauvegardé avec succès dans : {st.session_state.save_path}")
                        except Exception as e:
                            st.error(f"Erreur d'écriture : {e}")
                
                with c_sv2:
                    if st.button("💾 Save As... (Enregistrer sous)", use_container_width=True):
                        if path_input:
                            try:
                                with open(path_input, "wb") as f:
                                    pickle.dump(data_to_save, f)
                                st.session_state.save_path = path_input
                                st.success(f"✅ Nouveau fichier sauvegardé sous : {path_input}")
                            except Exception as e:
                                st.error(f"Erreur d'écriture : {e}")
                        else:
                            st.warning("Précisez un nom ou un chemin de fichier.")

                with st.expander("Alternative Web (Téléchargement classique)"):
                    pickle_out = pickle.dumps(data_to_save)
                    st.download_button("📥 Télécharger ma Session (.pkl)", pickle_out, f"backup_festival_{datetime.date.today()}.pkl", use_container_width=True)

                st.divider()
                uploaded_session = st.file_uploader("📂 Charger une sauvegarde (.pkl)", type=['pkl'])
                if uploaded_session:
                    if st.button("Restaurer la sauvegarde"):
                        try:
                            data_loaded = pickle.loads(uploaded_session.read())
                            st.session_state.planning = data_loaded["planning"]
                            st.session_state.fiches_tech = data_loaded["fiches_tech"]
                            st.session_state.riders_stockage = data_loaded["riders_stockage"]
                            st.session_state.artist_circuits = data_loaded.get("artist_circuits", {})
                            st.session_state.patches_io = data_loaded.get("patches_io", {})
                            st.session_state.festival_name = data_loaded.get("festival_name", "Mon Festival")
                            st.session_state.festival_logo = data_loaded.get("festival_logo", None)
                            st.session_state.custom_catalog = data_loaded.get("custom_catalog", {})
                            st.session_state.easyjob_mapping = data_loaded.get("easyjob_mapping", {})
                            st.session_state.notes_artistes = data_loaded.get("notes_artistes", {})
                            st.session_state.alim_elec = data_loaded.get("alim_elec", pd.DataFrame(columns=["Scène", "Jour", "Groupe", "Format", "Métier", "Emplacement"]))
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
                                new_mapping = {}
                                
                                for sheet in xls.sheet_names:
                                    df = pd.read_excel(xls, sheet_name=sheet)
                                    new_catalog[sheet] = {}
                                    new_mapping[sheet] = {}
                                    
                                    marques_normales = [col for col in df.columns if not str(col).endswith("_EASYJOB")]
                                    
                                    for brand in marques_normales:
                                        modeles = df[brand].dropna().astype(str).tolist()
                                        col_miroir = f"{brand}_EASYJOB"
                                        
                                        if modeles:
                                            new_catalog[sheet][brand] = modeles
                                            new_mapping[sheet][brand] = {}
                                            
                                            if col_miroir in df.columns:
                                                modeles_miroirs = df[col_miroir].astype(str).tolist()
                                                for i, mod in enumerate(modeles):
                                                    if i < len(modeles_miroirs) and modeles_miroirs[i] != 'nan' and str(modeles_miroirs[i]).strip() != '':
                                                        new_mapping[sheet][brand][mod] = str(modeles_miroirs[i]).strip()
                                                    else:
                                                        new_mapping[sheet][brand][mod] = f"{brand} {mod}" 
                                            else:
                                                for mod in modeles:
                                                    new_mapping[sheet][brand][mod] = f"{brand} {mod}"
                                                    
                                st.session_state.custom_catalog = new_catalog
                                st.session_state.easyjob_mapping = new_mapping
                                st.success(f"Catalogue chargé et mapping EasyJob configuré !")
                            except Exception as e:
                                st.error(f"Erreur lecture Excel : {e}")
                    if st.session_state.custom_catalog:
                        if st.button("🗑️ Réinitialiser Catalogue"):
                            st.session_state.custom_catalog = {}
                            st.session_state.easyjob_mapping = {}
                            st.rerun()
            else:
                if code_secret: st.warning("Code incorrect")

    # --- SOUS-ONGLET 2 : EXPORT ---
    with sub_tabs_projet[1]:
        st.header("📄 Génération des Exports PDF")
        l_jours = sorted(st.session_state.planning["Jour"].unique())
        l_scenes = sorted(st.session_state.planning["Scène"].unique())
        cex1, cex2 = st.columns(2)

        with cex1:
            st.subheader("🗓️ Export Plannings")
            with st.container(border=True):
                m_plan = st.radio("Périmètre", ["Par Jour & Scène", "Global"], key="mp")
                s_j_p = st.selectbox("Jour", l_jours) if m_plan == "Par Jour & Scène" else None
                s_s_p = st.selectbox("Scène", l_scenes) if m_plan == "Par Jour & Scène" else None
                
                if st.button("Générer PDF Planning", use_container_width=True):
                    df_p = st.session_state.planning.copy()
                    dico_sections = {}
                    jours_a_traiter = [s_j_p] if m_plan == "Par Jour & Scène" else l_jours
                    scenes_a_traiter = [s_s_p] if m_plan == "Par Jour & Scène" else l_scenes
                    
                    for j in jours_a_traiter:
                        for s in scenes_a_traiter:
                            sub_df = df_p[(df_p["Jour"] == str(j)) & (df_p["Scène"] == s)]
                            df_chrono = get_chronological_planning(sub_df)
                            if not df_chrono.empty:
                                dico_sections[f"JOUR : {j} | SCENE : {s}"] = df_chrono
                    
                    orient = 'L' if m_plan == "Global" else 'P'
                    fmt = 'A3' if m_plan == "Global" else 'A4'
                    
                    pdf_bytes = generer_pdf_complet(f"PLANNING {m_plan.upper()}", dico_sections, orientation=orient, format=fmt)
                    st.download_button("📥 Télécharger PDF Planning", pdf_bytes, "planning.pdf", "application/pdf")

        with cex2:
            st.subheader("📦 Export Besoins")
            with st.container(border=True):
                m_bes = st.radio("Type", ["Par Jour & Scène", "Total Période par Scène"], key="mb")
                s_s_m = st.selectbox("Scène (Besoins)", l_scenes, key="ssm")
                s_j_m = None
                sel_grp_exp = "Tous"
                if m_bes == "Par Jour & Scène":
                    s_j_m = st.selectbox("Jour (Besoins)", l_jours, key="sjm")
                    arts_du_jour = st.session_state.planning[(st.session_state.planning["Jour"] == s_j_m) & (st.session_state.planning["Scène"] == s_s_m)]["Artiste"].unique()
                    sel_grp_exp = st.selectbox("Filtrer par Groupe (Optionnel)", ["Tous"] + list(arts_du_jour))
                
                col_btn_pdf, col_btn_ej = st.columns(2)
                
                with col_btn_pdf:
                    if st.button("Générer PDF Besoins", use_container_width=True):
                        df_base = st.session_state.fiches_tech[(st.session_state.fiches_tech["Scène"] == s_s_m) & (st.session_state.fiches_tech["Artiste_Apporte"] == False)]
                        if sel_grp_exp != "Tous": df_base = df_base[df_base["Groupe"] == sel_grp_exp]
                         
                        dico_besoins = {}
                        
                        if sel_grp_exp != "Tous":
                            df_alim_besoin = st.session_state.alim_elec[
                                (st.session_state.alim_elec["Groupe"] == sel_grp_exp) & 
                                (st.session_state.alim_elec["Scène"] == s_s_m)
                            ]
                            if m_bes == "Par Jour & Scène":
                                df_alim_besoin = df_alim_besoin[df_alim_besoin["Jour"] == s_j_m]
                            if not df_alim_besoin.empty:
                                dico_besoins["--- ALIMENTATION ELECTRIQUE ---"] = df_alim_besoin[["Format", "Métier", "Emplacement"]]

                        if sel_grp_exp != "Tous" and sel_grp_exp in st.session_state.artist_circuits:
                            c = st.session_state.artist_circuits[sel_grp_exp]
                            q_in, q_ear, q_ms, q_mm = c.get("inputs", 0), c.get("ear_stereo", 0), c.get("mon_stereo", 0), c.get("mon_mono", 0)
                            if q_in == 0 and q_ear == 0 and q_ms == 0 and q_mm == 0:
                                dico_besoins["--- CONFIGURATION CIRCUITS ---"] = "Non renseigné"
                            else:
                                dico_besoins["--- CONFIGURATION CIRCUITS ---"] = pd.DataFrame({
                                    "Type de Circuit": ["Circuits d'entrées", "EAR MONITOR // Circuits stéréo", "MONITOR // circuits stéréo", "MONITOR // circuits mono"],
                                    "Quantité": [q_in, q_ear, q_ms, q_mm]
                                })

                        def calcul_pic(df_input, jour, scene):
                            if sel_grp_exp != "Tous":
                                plan = st.session_state.planning[(st.session_state.planning["Jour"] == jour) & (st.session_state.planning["Scène"] == scene) & (st.session_state.planning["Artiste"] == sel_grp_exp)]
                            else:
                                plan = st.session_state.planning[(st.session_state.planning["Jour"] == jour) & (st.session_state.planning["Scène"] == scene)]
                            arts = plan["Artiste"].tolist()
                            if not arts or df_input.empty: return pd.DataFrame()
                            mat = df_input.groupby(["Catégorie", "Marque", "Modèle", "Groupe"])["Quantité"].sum().unstack(fill_value=0)
                            for a in arts: 
                                if a not in mat.columns: mat[a] = 0
                            res = pd.concat([mat[arts].iloc[:, i] + mat[arts].iloc[:, i+1] for i in range(len(arts)-1)], axis=1).max(axis=1) if len(arts) > 1 else mat[arts].iloc[:, 0]
                            df_res = res.reset_index()
                            df_res.columns = list(df_res.columns[:-1]) + ["Total"]
                            return df_res

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
                                if not res_j.empty: all_days_res.append(res_j.set_index(["Catégorie", "Marque", "Modèle"]))
                            if all_days_res:
                                final = pd.concat(all_days_res, axis=1).max(axis=1).reset_index().rename(columns={0: "Max_Periode"})
                                for cat in final["Catégorie"].unique():
                                    cols_dispo_glob = [c for c in ["Marque", "Modèle", "Max_Periode"] if c in final.columns]
                                    dico_besoins[f"CATEGORIE : {cat}"] = final[final["Catégorie"] == cat][cols_dispo_glob]

                        df_apporte = st.session_state.fiches_tech[(st.session_state.fiches_tech["Scène"] == s_s_m) & (st.session_state.fiches_tech["Artiste_Apporte"] == True)]
                        if m_bes == "Par Jour & Scène": df_apporte = df_apporte[df_apporte["Jour"] == s_j_m]
                        if sel_grp_exp != "Tous": df_apporte = df_apporte[df_apporte["Groupe"] == sel_grp_exp]
                        artistes_apporte = df_apporte["Groupe"].unique()
                        if len(artistes_apporte) > 0:
                            dico_besoins[" "] = pd.DataFrame() 
                            dico_besoins["--- MATERIEL APPORTE PAR LES ARTISTES ---"] = pd.DataFrame()
                            for art in artistes_apporte:
                                items_art = df_apporte[df_apporte["Groupe"] == art][["Catégorie", "Marque", "Modèle", "Quantité"]]
                                dico_besoins[f"FOURNI PAR : {art}"] = items_art
                        
                        titre_besoin = f"BESOINS {s_s_m} ({m_bes})"
                        if sel_grp_exp != "Tous": titre_besoin += f" - {sel_grp_exp}"
                        
                        if m_bes == "Par Jour & Scène": arts_scope = arts_du_jour if sel_grp_exp == "Tous" else [sel_grp_exp]
                        else:
                            plan_scene = st.session_state.planning[st.session_state.planning["Scène"] == s_s_m]
                            arts_scope = plan_scene["Artiste"].unique() if sel_grp_exp == "Tous" else [sel_grp_exp]
                        
                        notes_list_text = []
                        for a in arts_scope:
                            n = st.session_state.notes_artistes.get(a, "").strip()
                            if n: notes_list_text.append(f"- {a} :\n{n}")
                        if notes_list_text: dico_besoins["--- INFORMATIONS COMPLEMENTAIRES / NOTES ---"] = "\n\n".join(notes_list_text)

                        pdf_bytes_b = generer_pdf_complet(titre_besoin, dico_besoins)
                        st.download_button("📥 Télécharger PDF Besoins", pdf_bytes_b, "besoins.pdf", "application/pdf")

                with col_btn_ej:
                    if st.button("Export Easyjob", use_container_width=True):
                        df_base_ej = st.session_state.fiches_tech[(st.session_state.fiches_tech["Scène"] == s_s_m) & (st.session_state.fiches_tech["Artiste_Apporte"] == False)]
                        if sel_grp_exp != "Tous": df_base_ej = df_base_ej[df_base_ej["Groupe"] == sel_grp_exp]

                        def calcul_pic_ej(df_input, jour, scene):
                            if sel_grp_exp != "Tous": plan = st.session_state.planning[(st.session_state.planning["Jour"] == jour) & (st.session_state.planning["Scène"] == scene) & (st.session_state.planning["Artiste"] == sel_grp_exp)]
                            else: plan = st.session_state.planning[(st.session_state.planning["Jour"] == jour) & (st.session_state.planning["Scène"] == scene)]
                            arts = plan["Artiste"].tolist()
                            if not arts or df_input.empty: return pd.DataFrame()
                            mat = df_input.groupby(["Catégorie", "Marque", "Modèle", "Groupe"])["Quantité"].sum().unstack(fill_value=0)
                            for a in arts: 
                                if a not in mat.columns: mat[a] = 0
                            res = pd.concat([mat[arts].iloc[:, i] + mat[arts].iloc[:, i+1] for i in range(len(arts)-1)], axis=1).max(axis=1) if len(arts) > 1 else mat[arts].iloc[:, 0]
                            df_res = res.reset_index()
                            df_res.columns = list(df_res.columns[:-1]) + ["Total"]
                            return df_res

                        export_data = []

                        if m_bes == "Par Jour & Scène":
                            data_pic = calcul_pic_ej(df_base_ej[df_base_ej["Jour"] == s_j_m], s_j_m, s_s_m)
                            if not data_pic.empty:
                                for _, row in data_pic.iterrows():
                                    qty = row["Total"]
                                    if qty > 0:
                                        cat, marque, modele = row['Catégorie'], row['Marque'], row['Modèle']
                                        item_name = f"{marque} {modele}".strip()
                                        if st.session_state.easyjob_mapping.get(cat, {}).get(marque, {}).get(modele):
                                            item_name = st.session_state.easyjob_mapping[cat][marque][modele]
                                        export_data.append({"Quantity": qty, "Items": item_name})
                        else:
                            all_days_res = []
                            for j in df_base_ej["Jour"].unique():
                                res_j = calcul_pic_ej(df_base_ej[df_base_ej["Jour"] == j], j, s_s_m)
                                if not res_j.empty: all_days_res.append(res_j.set_index(["Catégorie", "Marque", "Modèle"]))
                            if all_days_res:
                                final = pd.concat(all_days_res, axis=1).max(axis=1).reset_index().rename(columns={0: "Max_Periode"})
                                for _, row in final.iterrows():
                                    qty = row["Max_Periode"]
                                    if qty > 0:
                                        cat, marque, modele = row['Catégorie'], row['Marque'], row['Modèle']
                                        item_name = f"{marque} {modele}".strip()
                                        if st.session_state.easyjob_mapping.get(cat, {}).get(marque, {}).get(modele):
                                            item_name = st.session_state.easyjob_mapping[cat][marque][modele]
                                        export_data.append({"Quantity": qty, "Items": item_name})
                        
                        df_export = pd.DataFrame(export_data, columns=["Quantity", "Items"])
                        output = io.BytesIO()
                        with pd.ExcelWriter(output) as writer:
                            df_export.to_excel(writer, index=False, sheet_name='Easyjob')
                        excel_data = output.getvalue()
                        st.download_button("📥 Télécharger Excel", excel_data, "easyjob_export.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # --- EXPORT PATCH IN/OUT ---
        st.divider()
        st.subheader("🎛️ Export Patch IN / OUT")
        with st.container(border=True):
            if st.session_state.planning.empty:
                st.info("Aucun artiste dans le planning pour générer un patch.")
            else:
                col_ep1, col_ep2, col_ep3, col_ep4 = st.columns(4)
                with col_ep1:
                    l_jours_p = sorted(st.session_state.planning["Jour"].unique())
                    s_j_patch = st.selectbox("Jour (Patch)", l_jours_p, key="export_j_patch")
                with col_ep2:
                    scenes_jour = st.session_state.planning[st.session_state.planning["Jour"] == s_j_patch]["Scène"].unique()
                    s_s_patch = st.selectbox("Scène (Patch)", scenes_jour, key="export_s_patch")
                with col_ep3:
                    artistes_patch = st.session_state.planning[(st.session_state.planning["Jour"] == s_j_patch) & (st.session_state.planning["Scène"] == s_s_patch)]["Artiste"].unique()
                    s_a_patch = st.selectbox("Groupe (Patch)", artistes_patch, key="export_a_patch")
                with col_ep4:
                    s_m_patch = st.selectbox("Format", ["12N", "20H"], key="export_m_patch")

                if s_a_patch in st.session_state.patches_io and st.session_state.patches_io[s_a_patch].get(s_m_patch) is not None:
                    dico_patch = {}
                    note_patch = st.session_state.notes_artistes.get(s_a_patch, "").strip()
                    if note_patch: dico_patch["--- INFORMATIONS / NOTES ---"] = note_patch
                    
                    df_alim_patch = st.session_state.alim_elec[
                        (st.session_state.alim_elec["Groupe"] == s_a_patch) & 
                        (st.session_state.alim_elec["Scène"] == s_s_patch) & 
                        (st.session_state.alim_elec["Jour"] == s_j_patch)
                    ][["Format", "Métier", "Emplacement"]]
                    
                    if not df_alim_patch.empty: dico_patch["--- ALIMENTATION ELECTRIQUE ---"] = df_alim_patch
                    dico_patch.update(st.session_state.patches_io[s_a_patch][s_m_patch])
                    titre_patch = f"PATCH {s_m_patch} - {s_a_patch} ({s_j_patch} | {s_s_patch})"
                    pdf_bytes_p = generer_pdf_patch(titre_patch, dico_patch)
                    st.download_button("📥 Télécharger PDF Patch", pdf_bytes_p, f"patch_{s_m_patch}_{s_a_patch}.pdf", "application/pdf", use_container_width=True)
                else:
                    st.info(f"ℹ️ Aucun Patch {s_m_patch} encodé pour {s_a_patch}. Veuillez le créer dans l'onglet Technique.")

# ==========================================
# ONGLET 2 : GESTION DES ARTISTES / PLANNING
# ==========================================
with main_tabs[1]:
    
    # --- BLOC 1 : AJOUTER UN ARTISTE ---
    with st.expander("➕ Ajouter un Artiste", expanded=True):
        c1, c2, c3 = st.columns(3)
        sc = c1.text_input("Scène", "MainStage")
        jo = c2.date_input("Date de passage", datetime.date.today())
        ar = c3.text_input("Nom Artiste")
        
        st.write("⏱️ **Horaires des phases**")
        r2_1, r2_2, r2_3 = st.columns(3)
        with r2_1:
            st.markdown("**Load IN**")
            li_d = st.selectbox("Début", time_options, key="li_d")
            li_f = st.selectbox("Fin", time_options, key="li_f")
        with r2_2:
            st.markdown("**Installation Off Stage**")
            ioff_d = st.selectbox("Début", time_options, key="ioff_d")
            ioff_f = st.selectbox("Fin", time_options, key="ioff_f")
        with r2_3:
            st.markdown("**Installation On Stage**")
            ion_d = st.selectbox("Début", time_options, key="ion_d")
            ion_f = st.selectbox("Fin", time_options, key="ion_f")

        r3_1, r3_2, r3_3 = st.columns(3)
        with r3_1:
            st.markdown("**Balances**")
            bal_d = st.selectbox("Début", time_options, key="bal_d")
            bal_f = st.selectbox("Fin", time_options, key="bal_f")
        with r3_2:
            st.markdown("**Change Over**")
            co_d = st.selectbox("Début", time_options, key="co_d")
            co_f = st.selectbox("Fin", time_options, key="co_f")
        with r3_3:
            st.markdown("**Show**")
            sh_d = st.selectbox("Début", time_options, key="sh_d")
            sh_f = st.selectbox("Fin", time_options, key="sh_f")

        pdfs = st.file_uploader("Fiches Techniques (PDF)", accept_multiple_files=True, key=f"upl_{st.session_state.uploader_key}")
        
        if st.button("Valider Artiste", type="primary"):
            if ar:
                new_row = pd.DataFrame([{
                    "Scène": sc, "Jour": str(jo), "Artiste": ar, 
                    "Load IN Début": li_d, "Load IN Fin": li_f,
                    "Inst Off Début": ioff_d, "Inst Off Fin": ioff_f,
                    "Inst On Début": ion_d, "Inst On Fin": ion_f,
                    "Balance Début": bal_d, "Balance Fin": bal_f,
                    "Change Over Début": co_d, "Change Over Fin": co_f,
                    "Show Début": sh_d, "Show Fin": sh_f
                }])
                st.session_state.planning = pd.concat([st.session_state.planning, new_row], ignore_index=True)
                if ar not in st.session_state.riders_stockage: st.session_state.riders_stockage[ar] = {}
                if pdfs:
                    for f in pdfs: st.session_state.riders_stockage[ar][f.name] = f.read()
                st.session_state.uploader_key += 1
                st.rerun()

    # --- BLOC 2 : PLANNING GLOBAL ---
    with st.expander("📋 Planning Global (Modifiable)", expanded=False):
        if st.session_state.delete_confirm_idx is not None:
            idx = st.session_state.delete_confirm_idx
            with st.status("⚠️ Confirmation de suppression", expanded=True):
                st.write(f"Supprimer définitivement l'artiste : **{st.session_state.planning.iloc[idx]['Artiste']}** ?")
                col_cfg1, col_cfg2 = st.columns(2)
                if col_cfg1.button("✅ OUI, Supprimer", use_container_width=True):
                    nom_art = st.session_state.planning.iloc[idx]['Artiste']
                    st.session_state.planning = st.session_state.planning.drop(idx).reset_index(drop=True)
                    artistes_actifs = st.session_state.planning["Artiste"].unique()
                    keys_to_delete = [k for k in st.session_state.riders_stockage.keys() if k not in artistes_actifs]
                    for k in keys_to_delete: del st.session_state.riders_stockage[k]
                    st.session_state.delete_confirm_idx = None
                    st.rerun()
                if col_cfg2.button("❌ Annuler", use_container_width=True):
                    st.session_state.delete_confirm_idx = None
                    st.rerun()

        if not st.session_state.planning.empty:
            df_visu = st.session_state.planning.copy()
            df_visu.insert(0, "Rider", df_visu["Artiste"].apply(lambda x: "✅" if st.session_state.riders_stockage.get(x) else "❌"))
            edited_df = st.data_editor(df_visu, use_container_width=True, num_rows="dynamic", key="main_editor", hide_index=True)
            if st.session_state.main_editor["deleted_rows"]:
                st.session_state.delete_confirm_idx = df_visu.index[st.session_state.main_editor["deleted_rows"][0]]
                st.rerun()
            df_to_save = edited_df.drop(columns=["Rider"])
            if not df_to_save.equals(st.session_state.planning):
                 st.session_state.planning = df_to_save.reset_index(drop=True)
                 artistes_actifs = st.session_state.planning["Artiste"].unique()
                 keys_to_delete = [k for k in st.session_state.riders_stockage.keys() if k not in artistes_actifs]
                 for k in keys_to_delete: del st.session_state.riders_stockage[k]
                 st.rerun()

    # --- BLOC 3 : GESTION PDF ---
    with st.expander("📁 Gestion des Fichiers PDF", expanded=False):
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

    # --- BLOC 4 : PLANNING QUOTIDIEN ---
    with st.expander("📅 Planning Quotidien (Gantt)", expanded=True):
        if not st.session_state.planning.empty:
            l_jours_g = sorted(st.session_state.planning["Jour"].unique())
            cg_1, cg_2 = st.columns(2)
            s_j_g = cg_1.selectbox("Sélectionner le Jour", l_jours_g)
            l_scenes_g = sorted(st.session_state.planning[st.session_state.planning["Jour"] == s_j_g]["Scène"].unique())
            s_s_g = cg_2.selectbox("Sélectionner la Scène", l_scenes_g)
            
            df_g = st.session_state.planning[(st.session_state.planning["Jour"] == s_j_g) & (st.session_state.planning["Scène"] == s_s_g)]
            
            gantt_data = []
            phases = [
                ("Load IN", "Load IN Début", "Load IN Fin"),
                ("Inst Off Stage", "Inst Off Début", "Inst Off Fin"),
                ("Inst On Stage", "Inst On Début", "Inst On Fin"),
                ("Balance", "Balance Début", "Balance Fin"),
                ("Change Over", "Change Over Début", "Change Over Fin"),
                ("Show", "Show Début", "Show Fin")
            ]
            
            for _, row in df_g.iterrows():
                art = row["Artiste"]
                for phase_name, c_deb, c_fin in phases:
                    deb = row.get(c_deb, "-- none --")
                    fin = row.get(c_fin, "-- none --")
                    if deb != "-- none --" and fin != "-- none --":
                        start_time = pd.to_datetime(f"2024-01-01 {deb}")
                        end_time = pd.to_datetime(f"2024-01-01 {fin}")
                        if end_time < start_time: end_time += pd.Timedelta(days=1)
                        gantt_data.append(dict(Artiste=art, Phase=phase_name, Début=start_time, Fin=end_time))
            
            if gantt_data:
                df_gantt = pd.DataFrame(gantt_data)
                fig = px.timeline(df_gantt, x_start="Début", x_end="Fin", y="Artiste", color="Phase", title=f"Planning {s_s_g} - {s_j_g}")
                fig.update_yaxes(autorange="reversed")
                fig.update_layout(xaxis=dict(tickformat="%H:%M"))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aucune plage horaire valide renseignée pour cette date et cette scène.")
        else:
            st.info("Ajoutez des artistes et leurs horaires pour générer le planning quotidien.")

# ==========================================
# ONGLET 3 : TECHNIQUE
# ==========================================
with main_tabs[2]:
    sub_tabs_tech = st.tabs(["Saisie du matériel", "Création des Patch IN/OUT"])
    
    # --- SOUS-ONGLET 1 : SAISIE MATERIEL ---
    with sub_tabs_tech[0]:
        if not st.session_state.planning.empty:
            f1, f2, f3 = st.columns(3)
            with f1: sel_j = st.selectbox("📅 Jour", sorted(st.session_state.planning["Jour"].unique()))
            with f2:
                scenes = st.session_state.planning[st.session_state.planning["Jour"] == sel_j]["Scène"].unique()
                sel_s = st.selectbox("🏗️ Scène", scenes)
            with f3:
                artistes = st.session_state.planning[(st.session_state.planning["Jour"] == sel_j) & (st.session_state.planning["Scène"] == sel_s)]["Artiste"].unique()
                sel_a = st.selectbox("🎸 Groupe", artistes)
                
                if sel_a and sel_a in st.session_state.riders_stockage:
                    riders_groupe = list(st.session_state.riders_stockage[sel_a].keys())
                    if riders_groupe:
                        sel_file = st.selectbox("📂 Voir Rider(s)", ["-- Choisir un fichier --"] + riders_groupe, key=f"view_{sel_a}")
                        if sel_file != "-- Choisir un fichier --":
                            pdf_data = st.session_state.riders_stockage[sel_a][sel_file]
                            b64_pdf = base64.b64encode(pdf_data).decode('utf-8')
                            pdf_link = f'<a href="data:application/pdf;base64,{b64_pdf}" download="{sel_file}" target="_blank" style="text-decoration:none; color:white; background-color:#FF4B4B; padding:6px 12px; border-radius:5px; font-weight:bold; display:inline-block; margin-top:5px;">👁️ Ouvrir / Télécharger {sel_file}</a>'
                            st.markdown(pdf_link, unsafe_allow_html=True)

            if sel_a:
                st.divider()
                
                col_circ, col_alim = st.columns(2)
                
                with col_circ:
                    st.subheader(f"⚙️ Configuration circuits : {sel_a}")
                    if sel_a not in st.session_state.artist_circuits:
                        st.session_state.artist_circuits[sel_a] = {"inputs": 0, "ear_stereo": 0, "mon_stereo": 0, "mon_mono": 0}
                    
                    c_circ1, c_circ2 = st.columns(2)
                    with c_circ1:
                        st.session_state.artist_circuits[sel_a]["inputs"] = st.number_input("Circuits d'entrées", min_value=0, value=int(st.session_state.artist_circuits[sel_a].get("inputs", 0)), key=f"in_{sel_a}")
                        st.session_state.artist_circuits[sel_a]["mon_stereo"] = st.number_input("MONITOR // stéréo", min_value=0, value=int(st.session_state.artist_circuits[sel_a].get("mon_stereo", 0)), key=f"ms_{sel_a}")
                    with c_circ2:
                        st.session_state.artist_circuits[sel_a]["ear_stereo"] = st.number_input("EAR MONITOR // stéréo", min_value=0, value=int(st.session_state.artist_circuits[sel_a].get("ear_stereo", 0)), key=f"ear_{sel_a}")
                        st.session_state.artist_circuits[sel_a]["mon_mono"] = st.number_input("MONITOR // mono", min_value=0, value=int(st.session_state.artist_circuits[sel_a].get("mon_mono", 0)), key=f"mm_{sel_a}")

                with col_alim:
                    st.subheader(f"⚡ Alimentation électrique : {sel_a}")
                    df_alim_art = st.session_state.alim_elec[
                        (st.session_state.alim_elec["Groupe"] == sel_a) &
                        (st.session_state.alim_elec["Scène"] == sel_s) &
                        (st.session_state.alim_elec["Jour"] == sel_j)
                    ]
                    
                    edited_alim = st.data_editor(
                        df_alim_art[["Format", "Métier", "Emplacement"]],
                        column_config={
                            "Format": st.column_config.SelectboxColumn("Format", options=["PC16", "P17 32M", "P17 32T", "P17 63T", "P17 125T"], required=True),
                            "Métier": st.column_config.SelectboxColumn("Métier", options=["SON", "BACKLINE", "LUMIERE", "VIDEO", "STRUCTURE", "TOURBUS"], required=True),
                            "Emplacement": st.column_config.SelectboxColumn("Emplacement", options=["FOH", "JARDIN", "COUR", "LOINTAIN"], required=True)
                        },
                        num_rows="dynamic",
                        use_container_width=True,
                        hide_index=True,
                        key=f"ed_alim_{sel_a}_{sel_s}_{sel_j}"
                    )
                    
                    if not edited_alim.equals(df_alim_art[["Format", "Métier", "Emplacement"]]):
                        st.session_state.alim_elec = st.session_state.alim_elec[
                            ~((st.session_state.alim_elec["Groupe"] == sel_a) &
                              (st.session_state.alim_elec["Scène"] == sel_s) &
                              (st.session_state.alim_elec["Jour"] == sel_j))
                        ]
                        if not edited_alim.empty:
                            new_alim = edited_alim.copy()
                            new_alim["Groupe"] = sel_a
                            new_alim["Scène"] = sel_s
                            new_alim["Jour"] = sel_j
                            st.session_state.alim_elec = pd.concat([st.session_state.alim_elec, new_alim], ignore_index=True)
                        st.rerun()

                st.divider()
                st.subheader(f"📝 Informations complémentaires / Matériel apporté : {sel_a}")
                note_val = st.session_state.notes_artistes.get(sel_a, "")
                new_note = st.text_area("Précisez ici si le groupe fournit ses micros, du câblage spécifique, etc.", value=note_val, key=f"note_area_{sel_a}")
                if new_note != note_val:
                    st.session_state.notes_artistes[sel_a] = new_note
                    st.rerun()

                st.divider()
                st.subheader(f"📥 Saisie Matériel : {sel_a}")
                with st.container(border=True):
                    CATALOGUE = st.session_state.custom_catalog
                    if CATALOGUE:
                        st.write("🔍 **Recherche rapide (Catalogue)**")
                        all_items = []
                        for cat, marques in CATALOGUE.items():
                            for marq, modeles in marques.items():
                                for mod in modeles:
                                    if not str(mod).startswith("//") and not str(mod).startswith("🔹"):
                                        all_items.append(f"{mod} ({marq} - {cat})")
                        
                        c_rech, c_qte_r, c_app_r, c_btn_r = st.columns([3, 1, 1, 1])
                        recherche = c_rech.selectbox("Modèle", ["-- Sélectionner --"] + sorted(all_items), label_visibility="collapsed")
                        qte_r = c_qte_r.number_input("Qté", 1, 500, 1, key="qte_r")
                        app_r = c_app_r.checkbox("Artiste Apporte", key="app_r")
                        
                        if c_btn_r.button("⚡ Ajouter", use_container_width=True):
                            if recherche != "-- Sélectionner --":
                                mod_part = recherche.split(" (")[0]
                                rest = recherche.split(" (")[1].replace(")", "")
                                marq_part = rest.split(" - ")[0]
                                cat_part = rest.split(" - ")[1]
                                mask = (st.session_state.fiches_tech["Groupe"] == sel_a) & (st.session_state.fiches_tech["Modèle"] == mod_part) & (st.session_state.fiches_tech["Marque"] == marq_part) & (st.session_state.fiches_tech["Artiste_Apporte"] == app_r)
                                if not st.session_state.fiches_tech[mask].empty:
                                    st.session_state.fiches_tech.loc[mask, "Quantité"] += qte_r
                                else:
                                    new_item = pd.DataFrame([{"Scène": sel_s, "Jour": sel_j, "Groupe": sel_a, "Catégorie": cat_part, "Marque": marq_part, "Modèle": mod_part, "Quantité": qte_r, "Artiste_Apporte": app_r}])
                                    st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, new_item], ignore_index=True)
                                st.rerun()
                        st.divider()
                        st.write("⚙️ **Saisie par Catégorie & Marque**")
                    
                    c_cat, c_mar, c_mod, c_qte, c_app = st.columns([2, 2, 2, 1, 1])
                    liste_categories = list(CATALOGUE.keys()) if CATALOGUE else ["MICROS FILAIRE", "HF", "EAR MONITOR", "BACKLINE", "SYMETRISEUR"]
                    v_cat = c_cat.selectbox("Catégorie", liste_categories)
                    liste_marques = []
                    if CATALOGUE and v_cat in CATALOGUE: liste_marques = list(CATALOGUE[v_cat].keys())
                    else: liste_marques = ["SHURE", "SENNHEISER", "AKG", "NEUMANN", "YAMAHA", "FENDER", "BSS", "RADIAL"]
                    v_mar = c_mar.selectbox("Marque", liste_marques)
                    v_mod = ""
                    if CATALOGUE and v_cat in CATALOGUE and v_mar in CATALOGUE[v_cat]:
                        raw_modeles = CATALOGUE[v_cat][v_mar]
                        display_modeles = [f"🔹 {str(m).replace('//','').strip()} 🔹" if str(m).startswith("//") else m for m in raw_modeles]
                        v_mod = c_mod.selectbox("Modèle", display_modeles)
                    else:
                        v_mod = c_mod.text_input("Modèle", "SM58")
                    v_qte = c_qte.number_input("Qté", 1, 500, 1, key="qte_classique")
                    v_app = c_app.checkbox("Artiste Apporte", key="app_classique")
                    if st.button("Ajouter au Patch"):
                        if isinstance(v_mod, str) and (v_mod.startswith("🔹") or v_mod.startswith("//")): st.error("⛔ Impossible d'ajouter un titre de section.")
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
                    st.subheader(f"📋 Items pour {sel_a}")
                    df_patch_art = st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"] == sel_a].sort_values(by=["Catégorie", "Marque"])
                    edited_patch = st.data_editor(
                        df_patch_art, use_container_width=True, num_rows="dynamic", key=f"ed_patch_{sel_a}", hide_index=True,
                        column_config={"Scène": None, "Jour": None, "Groupe": None}
                    )
                    if st.session_state[f"ed_patch_{sel_a}"]["deleted_rows"]:
                        st.session_state.delete_confirm_patch_idx = df_patch_art.index[st.session_state[f"ed_patch_{sel_a}"]["deleted_rows"][0]]
                        st.rerun()
                    if not edited_patch.equals(df_patch_art):
                        st.session_state.fiches_tech.update(edited_patch)
                        st.rerun()

                with col_besoin:
                    st.subheader(f"📊 Besoin {sel_s} - {sel_j}")
                    plan_trié = st.session_state.planning[(st.session_state.planning["Jour"] == sel_j) & (st.session_state.planning["Scène"] == sel_s)]
                    liste_art = plan_trié["Artiste"].tolist()
                    df_b = st.session_state.fiches_tech[(st.session_state.fiches_tech["Scène"] == sel_s) & (st.session_state.fiches_tech["Jour"] == sel_j) & (st.session_state.fiches_tech["Artiste_Apporte"] == False)]
                    if not df_b.empty:
                        matrice = df_b.groupby(["Catégorie", "Marque", "Modèle", "Groupe"])["Quantité"].sum().unstack(fill_value=0)
                        for a in liste_art: 
                            if a not in matrice.columns: matrice[a] = 0
                        matrice = matrice[liste_art]
                        res = pd.concat([matrice.iloc[:, i] + matrice.iloc[:, i+1] for i in range(len(liste_art)-1)], axis=1).max(axis=1) if len(liste_art) > 1 else matrice.iloc[:, 0]
                        df_res = res.reset_index()
                        df_res.columns = list(df_res.columns[:-1]) + ["Total"]
                        st.dataframe(df_res, use_container_width=True, hide_index=True)

    # --- SOUS-ONGLET 2 : CREATION DES PATCH IN/OUT ---
    with sub_tabs_tech[1]:
        st.subheader("📋 Patch IN / OUT")
        
        if not st.session_state.planning.empty:
            f1_p, f2_p, f3_p = st.columns(3)
            with f1_p: sel_j_p = st.selectbox("📅 Jour ", sorted(st.session_state.planning["Jour"].unique()), key="jour_patch")
            with f2_p:
                scenes_p = st.session_state.planning[st.session_state.planning["Jour"] == sel_j_p]["Scène"].unique()
                sel_s_p = st.selectbox("🏗️ Scène ", scenes_p, key="scene_patch")
            with f3_p:
                artistes_p = st.session_state.planning[(st.session_state.planning["Jour"] == sel_j_p) & (st.session_state.planning["Scène"] == sel_s_p)]["Artiste"].unique()
                sel_a_p = st.selectbox("🎸 Groupe ", artistes_p, key="art_patch")

                if sel_a_p and sel_a_p in st.session_state.riders_stockage:
                    riders_groupe_p = list(st.session_state.riders_stockage[sel_a_p].keys())
                    if riders_groupe_p:
                        sel_file_p = st.selectbox("📂 Voir Rider(s)", ["-- Choisir un fichier --"] + riders_groupe_p, key=f"view_p_{sel_a_p}")
                        if sel_file_p != "-- Choisir un fichier --":
                            pdf_data_p = st.session_state.riders_stockage[sel_a_p][sel_file_p]
                            b64_pdf_p = base64.b64encode(pdf_data_p).decode('utf-8')
                            pdf_link_p = f'<a href="data:application/pdf;base64,{b64_pdf_p}" download="{sel_file_p}" target="_blank" style="text-decoration:none; color:white; background-color:#FF4B4B; padding:6px 12px; border-radius:5px; font-weight:bold; display:inline-block; margin-top:5px;">👁️ Ouvrir / Télécharger {sel_file_p}</a>'
                            st.markdown(pdf_link_p, unsafe_allow_html=True)

            if sel_a_p:
                plan_patch = st.session_state.planning[(st.session_state.planning["Jour"] == sel_j_p) & (st.session_state.planning["Scène"] == sel_s_p)]
                liste_art_patch = plan_patch["Artiste"].tolist()

                def get_circ(art, key): return int(st.session_state.artist_circuits.get(art, {}).get(key, 0))

                max_inputs, max_ear, max_mon_s, max_mon_m = 0, 0, 0, 0

                if len(liste_art_patch) == 1:
                    a1 = liste_art_patch[0]
                    max_inputs = get_circ(a1, "inputs")
                    max_ear = get_circ(a1, "ear_stereo")
                    max_mon_s = get_circ(a1, "mon_stereo")
                    max_mon_m = get_circ(a1, "mon_mono")
                elif len(liste_art_patch) > 1:
                    for i in range(len(liste_art_patch) - 1):
                        a1, a2 = liste_art_patch[i], liste_art_patch[i+1]
                        max_inputs = max(max_inputs, get_circ(a1, "inputs") + get_circ(a2, "inputs"))
                        max_ear = max(max_ear, get_circ(a1, "ear_stereo") + get_circ(a2, "ear_stereo"))
                        max_mon_s = max(max_mon_s, get_circ(a1, "mon_stereo") + get_circ(a2, "mon_stereo"))
                        max_mon_m = max(max_mon_m, get_circ(a1, "mon_mono") + get_circ(a2, "mon_mono"))

                st.divider()
                st.subheader(f"🎛️ Besoins spécifiques au groupe : {sel_a_p}")
                col_grp1, col_grp2, col_grp3, col_grp4 = st.columns(4)
                with col_grp1: st.metric("Circuits Entrées", get_circ(sel_a_p, "inputs"))
                with col_grp2: st.metric("EAR Stéréo", get_circ(sel_a_p, "ear_stereo"))
                with col_grp3: st.metric("MON Stéréo", get_circ(sel_a_p, "mon_stereo"))
                with col_grp4: st.metric("MON Mono", get_circ(sel_a_p, "mon_mono"))

                st.divider()
                nb_inputs_groupe = get_circ(sel_a_p, "inputs")
                
                if nb_inputs_groupe > 0:
                    col_mode1, col_mode2 = st.columns([1, 3])
                    with col_mode1: mode_patch = st.radio("Saisie :", ["PATCH 12N", "PATCH 20H"], horizontal=True)
                    
                    step = 12 if mode_patch == "PATCH 12N" else 20
                    prefix_box = "B12M/F" if mode_patch == "PATCH 12N" else "B20"
                    num_tabs = (nb_inputs_groupe // step) + (1 if nb_inputs_groupe % step > 0 else 0)

                    if sel_a_p not in st.session_state.patches_io: st.session_state.patches_io[sel_a_p] = {"12N": None, "20H": None, "nb_inputs": 0}
                    curr_state = st.session_state.patches_io[sel_a_p]
                    
                    if curr_state["nb_inputs"] != nb_inputs_groupe:
                        curr_state["12N"], curr_state["20H"] = None, None
                        curr_state["nb_inputs"] = nb_inputs_groupe
                        
                    mode_key = "12N" if mode_patch == "PATCH 12N" else "20H"

                    if curr_state[mode_key] is None:
                        tables = {}
                        if mode_patch == "PATCH 20H" and max_inputs <= 60:
                            tables["MASTER"] = pd.DataFrame({
                                "Input": [None]*nb_inputs_groupe, "Micro / DI": [None]*nb_inputs_groupe,
                                "Source": [""]*nb_inputs_groupe, "Stand": [None]*nb_inputs_groupe, "48V": [False]*nb_inputs_groupe
                            })
                        for i in range(1, num_tabs + 1):
                            tables[f"DEPART_{i}"] = pd.DataFrame({
                                "Boîtier": [None]*step, "Input": [None]*step, "Micro / DI": [None]*step,
                                "Source": [""]*step, "Stand": [None]*step, "48V": [False]*step
                            })
                        curr_state[mode_key] = tables

                    tables_data = curr_state[mode_key]
                    df_mat = st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"] == sel_a_p]
                    excl_micros = ["EAR MONITOR", "PIEDS MICROS", "MONITOR", "PRATICABLE & CADRE ROULETTE", "REGIE", "MULTI"]
                    
                    micros_instances = []
                    df_micros = df_mat[~df_mat["Catégorie"].isin(excl_micros)]
                    for _, row in df_micros.iterrows():
                        qty = int(row["Quantité"])
                        for i in range(1, qty + 1): micros_instances.append(f"{row['Modèle']} #{i}")
                            
                    liste_micros = [None] + sorted(micros_instances)
                    liste_stands = [None] + df_mat[df_mat["Catégorie"] == "PIEDS MICROS"]["Modèle"].unique().tolist()
                    color_map = {1: "🟤", 2: "🔴", 3: "🟠", 4: "🟡", 5: "🟢", 6: "🔵", 7: "🟣", 8: "⚪", 9: "🍏"}
                    all_boxes = [None] + [f"{prefix_box} {j} {color_map[j]}" for j in range(1, 10)]

                    def clean_input(val):
                        if pd.isna(val) or not isinstance(val, str): return val
                        res = val
                        for e in color_map.values(): res = res.replace(f" {e}", "").replace(e, "").strip()
                        return res

                    used_inputs_master = set(tables_data["MASTER"]["Input"].dropna().tolist()) if "MASTER" in tables_data else set()
                    used_inputs_departs, used_boxes_departs = {}, {}
                    used_micros_all = set()
                    
                    if "MASTER" in tables_data: used_micros_all.update(tables_data["MASTER"]["Micro / DI"].dropna().tolist())
                        
                    for i in range(1, num_tabs + 1):
                        t_name = f"DEPART_{i}"
                        used_inputs_departs[t_name] = set(clean_input(x) for x in tables_data[t_name]["Input"].dropna().tolist())
                        used_boxes_departs[t_name] = set(tables_data[t_name]["Boîtier"].dropna().tolist())
                        used_micros_all.update(tables_data[t_name]["Micro / DI"].dropna().tolist())

                    if "MASTER" in tables_data:
                        label_master = "MASTER PATCH 40" if max_inputs <= 40 else "MASTER PATCH 60"
                        st.subheader(f"🛠️ {label_master}")
                        
                        all_master_inputs = [f"INPUT {j}" for j in range(1, nb_inputs_groupe + 1)]
                        used_in_any_depart = set().union(*used_inputs_departs.values()) if used_inputs_departs else set()
                        avail_master_inputs = [None] + [x for x in all_master_inputs if x not in used_in_any_depart]
                        
                        current_micros_master = tables_data["MASTER"]["Micro / DI"].dropna().tolist()
                        avail_micros_master = [m for m in liste_micros if m not in used_micros_all or m in current_micros_master]

                        with st.expander(f"{label_master} ({nb_inputs_groupe} Lignes limitées par max circuits entrées)", expanded=True):
                            edited_master = st.data_editor(
                                tables_data["MASTER"],
                                column_config={
                                    "Input": st.column_config.SelectboxColumn("Input", options=avail_master_inputs),
                                    "Micro / DI": st.column_config.SelectboxColumn("Micro / DI", options=avail_micros_master),
                                    "Stand": st.column_config.SelectboxColumn("Stand", options=liste_stands),
                                    "48V": st.column_config.CheckboxColumn("48V")
                                },
                                hide_index=True, use_container_width=True, key=f"ed_master_{mode_key}_{sel_a_p}"
                            )
                            if not edited_master.equals(tables_data["MASTER"]):
                                curr_state[mode_key]["MASTER"] = edited_master
                                st.rerun()

                    for i in range(1, num_tabs + 1):
                        t_name = f"DEPART_{i}"
                        start_idx = (i-1)*step + 1
                        end_idx = min(i*step, nb_inputs_groupe)
                        
                        st.subheader(f"📤 DEPART {i} ({start_idx} --> {end_idx})")
                        
                        used_in_other_departs = set().union(*[used_boxes_departs[k] for k in used_boxes_departs if k != t_name])
                        avail_boxes = [x for x in all_boxes if x not in used_in_other_departs]
                        
                        all_depart_inputs = [f"INPUT {j}" for j in range(start_idx, i*step + 1) if j <= nb_inputs_groupe]
                        avail_inputs_base = [x for x in all_depart_inputs if x not in used_inputs_master]

                        for idx in tables_data[t_name].index:
                            box_val = tables_data[t_name].at[idx, "Boîtier"]
                            p_val = ""
                            if pd.notna(box_val) and isinstance(box_val, str):
                                for emoji in color_map.values():
                                    if emoji in box_val:
                                        p_val = emoji
                                        break
                                        
                            input_val = tables_data[t_name].at[idx, "Input"]
                            if pd.notna(input_val) and isinstance(input_val, str):
                                base_input = clean_input(input_val)
                                tables_data[t_name].at[idx, "Input"] = f"{base_input} {p_val}" if p_val else base_input

                        current_inputs_in_table = [x for x in tables_data[t_name]["Input"].dropna().unique()]
                        options_inputs = list(dict.fromkeys([None] + avail_inputs_base + current_inputs_in_table))
                        
                        current_micros_dep = tables_data[t_name]["Micro / DI"].dropna().tolist()
                        avail_micros_dep = [m for m in liste_micros if m not in used_micros_all or m in current_micros_dep]

                        with st.expander(f"Tableau DEPART {i}", expanded=True):
                            edited_dep = st.data_editor(
                                tables_data[t_name],
                                column_config={
                                    "Boîtier": st.column_config.SelectboxColumn("Boîtier", options=avail_boxes),
                                    "Input": st.column_config.SelectboxColumn("Input", options=options_inputs),
                                    "Micro / DI": st.column_config.SelectboxColumn("Micro / DI", options=avail_micros_dep),
                                    "Stand": st.column_config.SelectboxColumn("Stand", options=liste_stands),
                                    "48V": st.column_config.CheckboxColumn("48V")
                                },
                                hide_index=True, use_container_width=True, key=f"ed_{t_name}_{mode_key}_{sel_a_p}"
                            )
                            if not edited_dep.equals(tables_data[t_name]):
                                curr_state[mode_key][t_name] = edited_dep
                                st.rerun()
                else: st.info("ℹ️ Veuillez renseigner le nombre de circuits d'entrées de l'artiste dans 'Saisie du matériel' pour générer le Patch.")
        else: st.info("⚠️ Ajoutez d'abord des artistes dans le planning et renseignez leurs circuits pour gérer le patch.")
