import streamlit as st
import pandas as pd
import datetime
from fpdf import FPDF
import io
import pickle
import base64
import streamlit.components.v1 as components
import math

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
if 'artist_circuits' not in st.session_state:
    st.session_state.artist_circuits = {}
if 'patch_data' not in st.session_state: # Nouvelle variable pour le Patch
    st.session_state.patch_data = {}
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

main_tabs = st.tabs(["Configuration", "Technique"])

# ==========================================
# ONGLET 1 : CONFIGURATION
# ==========================================
with main_tabs[0]:
    sub_tabs_config = st.tabs(["Gestion / Planning des Artistes", "Admin & Sauvegarde", "Exports PDF"])
    
    with sub_tabs_config[0]:
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
                        "Scène": sc, "Jour": str(jo), "Artiste": ar, 
                        "Balance": val_ba, "Durée Balance": val_du, "Show": sh.strftime("%H:%M")
                    }])
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
            # FIX : hide_index=True pour éviter les "None" dans la colonne d'index
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
                with cg1: choix_art_pdf = st.selectbox("Choisir Artiste pour gérer ses PDF :", keys_list)
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

    with sub_tabs_config[1]:
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
            st.subheader("💾 Sauvegarde Projet")
            with st.container(border=True):
                data_to_save = {
                    "planning": st.session_state.planning,
                    "fiches_tech": st.session_state.fiches_tech,
                    "riders_stockage": st.session_state.riders_stockage,
                    "artist_circuits": st.session_state.artist_circuits,
                    "festival_name": st.session_state.festival_name,
                    "festival_logo": st.session_state.festival_logo,
                    "custom_catalog": st.session_state.custom_catalog
                }
                pickle_out = pickle.dumps(data_to_save)
                st.download_button("💾 Sauvegarder ma Session (.pkl)", pickle_out, f"backup_festival_{datetime.date.today()}.pkl")
                uploaded_session = st.file_uploader("📂 Charger une sauvegarde (.pkl)", type=['pkl'])
                if uploaded_session:
                    if st.button("Restaurer la sauvegarde"):
                        data_loaded = pickle.loads(uploaded_session.read())
                        st.session_state.planning = data_loaded["planning"]
                        st.session_state.fiches_tech = data_loaded["fiches_tech"]
                        st.session_state.riders_stockage = data_loaded["riders_stockage"]
                        st.session_state.artist_circuits = data_loaded.get("artist_circuits", {})
                        st.session_state.festival_name = data_loaded.get("festival_name", "Mon Festival")
                        st.session_state.festival_logo = data_loaded.get("festival_logo", None)
                        st.session_state.custom_catalog = data_loaded.get("custom_catalog", {})
                        st.success("Session restaurée avec succès !")
                        st.rerun()
        with col_adm2:
            st.subheader("📚 Catalogue Matériel (Excel)")
            code_secret = st.text_input("🔒 Code Admin", type="password")
            if code_secret == "0000":
                xls_file = st.file_uploader("Fichier Excel Items", type=['xlsx', 'xls'])
                if xls_file:
                    if st.button("Analyser et Charger le Catalogue"):
                        xls = pd.ExcelFile(xls_file)
                        new_catalog = {}
                        for sheet in xls.sheet_names:
                            df = pd.read_excel(xls, sheet_name=sheet)
                            new_catalog[sheet] = {brand: df[brand].dropna().astype(str).tolist() for brand in df.columns}
                        st.session_state.custom_catalog = new_catalog
                        st.success("Catalogue chargé !")
                if st.session_state.custom_catalog:
                    if st.button("🗑️ Réinitialiser Catalogue"):
                        st.session_state.custom_catalog = {}
                        st.rerun()

    with sub_tabs_config[2]:
        st.header("📄 Exports PDF")
        l_jours = sorted(st.session_state.planning["Jour"].unique())
        l_scenes = sorted(st.session_state.planning["Scène"].unique())
        cex1, cex2 = st.columns(2)
        with cex1:
            st.subheader("🗓️ Export Plannings")
            m_plan = st.radio("Périmètre", ["Global", "Par Jour", "Par Scène"], key="mp")
            s_j_p = st.selectbox("Jour", l_jours) if m_plan == "Par Jour" else None
            s_s_p = st.selectbox("Scène", l_scenes) if m_plan == "Par Scène" else None
            if st.button("Générer PDF Planning", use_container_width=True):
                dico_sections = {}
                jours_a_traiter = [s_j_p] if m_plan == "Par Jour" else l_jours
                scenes_a_traiter = [s_s_p] if m_plan == "Par Scène" else l_scenes
                for j in jours_a_traiter:
                    for s in scenes_a_traiter:
                        sub_df = st.session_state.planning[(st.session_state.planning["Jour"] == j) & (st.session_state.planning["Scène"] == s)].sort_values("Show")
                        if not sub_df.empty:
                            dico_sections[f"JOUR : {j} | SCENE : {s}"] = sub_df[["Artiste", "Balance", "Durée Balance", "Show"]]
                st.download_button("📥 Télécharger PDF Planning", generer_pdf_complet("PLANNING", dico_sections), "planning.pdf")

        with cex2:
            st.subheader("📦 Export Besoins")
            m_bes = st.radio("Type", ["Par Jour & Scène", "Total Période par Scène"], key="mb")
            s_s_m = st.selectbox("Scène", l_scenes, key="ssm")
            s_j_m = st.selectbox("Jour", l_jours, key="sjm") if m_bes == "Par Jour & Scène" else None
            if st.button("Générer PDF Besoins", use_container_width=True):
                dico_besoins = {}
                df_exp = st.session_state.fiches_tech[(st.session_state.fiches_tech["Scène"] == s_s_m)]
                if s_j_m: df_exp = df_exp[df_exp["Jour"] == s_j_m]
                for cat in df_exp["Catégorie"].unique():
                    dico_besoins[f"CATEGORIE : {cat}"] = df_exp[df_exp["Catégorie"] == cat][["Marque", "Modèle", "Quantité", "Groupe"]]
                st.download_button("📥 Télécharger PDF Besoins", generer_pdf_complet("BESOINS MATERIEL", dico_besoins), "besoins.pdf")

# ==========================================
# ONGLET 2 : TECHNIQUE
# ==========================================
with main_tabs[1]:
    sub_tabs_tech = st.tabs(["Saisie du matériel", "Patch IN / OUT"])
    
    with sub_tabs_tech[0]:
        if not st.session_state.planning.empty:
            f1, f2, f3 = st.columns(3)
            with f1: sel_j = st.selectbox("📅 Jour", sorted(st.session_state.planning["Jour"].unique()))
            with f2: sel_s = st.selectbox("🏗️ Scène", st.session_state.planning[st.session_state.planning["Jour"] == sel_j]["Scène"].unique())
            with f3: sel_a = st.selectbox("🎸 Groupe", st.session_state.planning[(st.session_state.planning["Jour"] == sel_j) & (st.session_state.planning["Scène"] == sel_s)]["Artiste"].unique())

            if sel_a:
                # Bloc Rider PDF
                if sel_a in st.session_state.riders_stockage:
                    riders_groupe = list(st.session_state.riders_stockage[sel_a].keys())
                    if riders_groupe:
                        sel_file = st.selectbox("📂 Voir Rider(s)", ["-- Choisir --"] + riders_groupe, key=f"v_{sel_a}")
                        if sel_file != "-- Choisir --":
                            pdf_data = st.session_state.riders_stockage[sel_a][sel_file]
                            b64 = base64.b64encode(pdf_data).decode('utf-8')
                            pdf_link = f'<a href="data:application/pdf;base64,{b64}" download="{sel_file}" target="_blank" style="text-decoration:none; color:white; background-color:#FF4B4B; padding:6px 12px; border-radius:5px;">👁️ Ouvrir {sel_file}</a>'
                            st.markdown(pdf_link, unsafe_allow_html=True)

                st.subheader(f"⚙️ Configuration Circuits : {sel_a}")
                if sel_a not in st.session_state.artist_circuits: st.session_state.artist_circuits[sel_a] = {"inputs": 0, "ear_stereo": 0, "mon_stereo": 0, "mon_mono": 0}
                c_c1, c_c2, c_c3, c_c4 = st.columns(4)
                st.session_state.artist_circuits[sel_a]["inputs"] = c_c1.number_input("Entrées", min_value=0, value=int(st.session_state.artist_circuits[sel_a]["inputs"]), key=f"in_{sel_a}")
                st.session_state.artist_circuits[sel_a]["ear_stereo"] = c_c2.number_input("EAR Stereo", min_value=0, value=int(st.session_state.artist_circuits[sel_a]["ear_stereo"]), key=f"ear_{sel_a}")
                st.session_state.artist_circuits[sel_a]["mon_stereo"] = c_c3.number_input("MON Stereo", min_value=0, value=int(st.session_state.artist_circuits[sel_a]["mon_stereo"]), key=f"ms_{sel_a}")
                st.session_state.artist_circuits[sel_a]["mon_mono"] = c_c4.number_input("MON Mono", min_value=0, value=int(st.session_state.artist_circuits[sel_a]["mon_mono"]), key=f"mm_{sel_a}")

                st.subheader(f"📥 Saisie Matériel : {sel_a}")
                with st.container(border=True):
                    CAT = st.session_state.custom_catalog
                    c_cat, c_mar, c_mod, c_qte, c_app = st.columns([2, 2, 2, 1, 1])
                    v_cat = c_cat.selectbox("Catégorie", list(CAT.keys()) if CAT else ["MICROS", "BACKLINE"])
                    v_mar = c_mar.selectbox("Marque", list(CAT[v_cat].keys()) if CAT and v_cat in CAT else ["SHURE"])
                    v_mod = c_mod.selectbox("Modèle", CAT[v_cat][v_mar]) if CAT and v_cat in CAT and v_mar in CAT[v_cat] else c_mod.text_input("Modèle")
                    v_qte = c_qte.number_input("Qté", 1, 100, 1)
                    v_app = c_app.checkbox("Artiste Apporte")
                    if st.button("Ajouter"):
                        new_item = pd.DataFrame([{"Scène": sel_s, "Jour": sel_j, "Groupe": sel_a, "Catégorie": v_cat, "Marque": v_mar, "Modèle": v_mod, "Quantité": v_qte, "Artiste_Apporte": v_app}])
                        st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, new_item], ignore_index=True)
                        st.rerun()

                df_patch_art = st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"] == sel_a]
                st.data_editor(df_patch_art, use_container_width=True, num_rows="dynamic", key=f"ed_{sel_a}", hide_index=True)

    with sub_tabs_tech[1]:
        st.subheader("📋 Patch IN / OUT")
        if not st.session_state.planning.empty:
            f1p, f2p, f3p = st.columns(3)
            sel_j_p = f1p.selectbox("Jour ", sorted(st.session_state.planning["Jour"].unique()), key="j_p")
            sel_s_p = f2p.selectbox("Scène ", st.session_state.planning[st.session_state.planning["Jour"] == sel_j_p]["Scène"].unique(), key="s_p")
            sel_a_p = f3p.selectbox("Groupe ", st.session_state.planning[(st.session_state.planning["Jour"] == sel_j_p) & (st.session_state.planning["Scène"] == sel_s_p)]["Artiste"].unique(), key="a_p")

            if sel_a_p:
                def get_c(a, k): return int(st.session_state.artist_circuits.get(a, {}).get(k, 0))
                
                # Calcul PIC (Max G1+G2)
                plan_p = st.session_state.planning[(st.session_state.planning["Jour"] == sel_j_p) & (st.session_state.planning["Scène"] == sel_s_p)].sort_values("Show")
                l_art = plan_p["Artiste"].tolist()
                max_in = 0
                if len(l_art) > 1:
                    for i in range(len(l_art)-1): max_in = max(max_in, get_c(l_art[i], "inputs") + get_c(l_art[i+1], "inputs"))
                else: max_in = get_c(sel_a_p, "inputs")
                st.metric("Patch Max Scène (Entrées)", max_in)
                
                # --- TABLEAUX DE PATCH DYNAMIQUES ---
                num_in = get_c(sel_a_p, "inputs")
                if num_in > 0:
                    divisor = 12 
                    nb_tabs = math.ceil(num_in / divisor)
                    p_key = f"data_{sel_a_p}"
                    if p_key not in st.session_state.patch_data:
                        st.session_state.patch_data[p_key] = [pd.DataFrame(columns=["Boitier", "Input", "Item", "Désignation"]) for _ in range(nb_tabs)]

                    l_inputs = [f"INPUT {i+1}" for i in range(num_in)]
                    l_items = sorted(st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"] == sel_a_p]["Modèle"].unique().tolist())
                    
                    all_used_inputs = []
                    for d in st.session_state.patch_data[p_key]: all_used_inputs.extend(d["Input"].dropna().tolist())

                    for t_idx in range(nb_tabs):
                        st.write(f"### DEPART {t_idx + 1}")
                        curr_df = st.session_state.patch_data[p_key][t_idx].reset_index(drop=True)
                        avail_inputs = [i for i in l_inputs if i not in all_used_inputs or i in curr_df["Input"].tolist()]

                        ed_df = st.data_editor(
                            curr_df,
                            column_config={
                                "Boitier": st.column_config.SelectboxColumn("Boitier", options=[f"B12 {i+1}" for i in range(12)]),
                                "Input": st.column_config.SelectboxColumn("Input", options=avail_inputs),
                                "Item": st.column_config.SelectboxColumn("Item", options=l_items),
                            },
                            num_rows="dynamic",
                            use_container_width=True,
                            key=f"patch_ed_{p_key}_{t_idx}",
                            hide_index=True # FIX : Cache l'index pour éviter le "None"
                        )
                        if not ed_df.equals(curr_df):
                            st.session_state.patch_data[p_key][t_idx] = ed_df.reset_index(drop=True)
                            st.rerun()
