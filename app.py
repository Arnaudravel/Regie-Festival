import streamlit as st
import pandas as pd
import datetime
from fpdf import FPDF
import io
import pickle
import base64
import math
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
if 'artist_circuits' not in st.session_state:
    st.session_state.artist_circuits = {}
if 'patch_in_out' not in st.session_state:
    st.session_state.patch_in_out = {}
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0
if 'festival_name' not in st.session_state:
    st.session_state.festival_name = "MON FESTIVAL"
if 'festival_logo' not in st.session_state:
    st.session_state.festival_logo = None
if 'custom_catalog' not in st.session_state:
    st.session_state.custom_catalog = {} 

# --- FONCTIONS TECHNIQUES ---

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
                ba = st.time_input("Heure Balance", datetime.time(14, 0)) if opt_balance else None
            with col_d_bal:
                du = st.text_input("Durée Balance", "45 min") if opt_balance else ""
            
            pdfs = st.file_uploader("Fiches Techniques (PDF)", accept_multiple_files=True, key=f"upl_{st.session_state.uploader_key}")
            if st.button("Valider Artiste"):
                if ar:
                    val_ba = ba.strftime("%H:%M") if ba and opt_balance else ""
                    new_row = pd.DataFrame([{"Scène": sc, "Jour": str(jo), "Artiste": ar, "Balance": val_ba, "Durée Balance": du, "Show": sh.strftime("%H:%M")}])
                    st.session_state.planning = pd.concat([st.session_state.planning, new_row], ignore_index=True)
                    if ar not in st.session_state.riders_stockage: st.session_state.riders_stockage[ar] = {}
                    if pdfs:
                        for f in pdfs: st.session_state.riders_stockage[ar][f.name] = f.read()
                    st.session_state.uploader_key += 1
                    st.rerun()

        st.subheader("📋 Planning Global")
        if not st.session_state.planning.empty:
            df_visu = st.session_state.planning.sort_values(by=["Jour", "Scène", "Show"]).copy()
            df_visu.insert(0, "Rider", df_visu["Artiste"].apply(lambda x: "✅" if st.session_state.riders_stockage.get(x) else "❌"))
            edited_df = st.data_editor(df_visu, use_container_width=True, num_rows="dynamic", key="main_editor", hide_index=True)
            st.session_state.planning = edited_df

    with sub_tabs_config[1]:
        st.header("🛠️ Administration & Sauvegarde")
        col_adm1, col_adm2 = st.columns(2)
        with col_adm1:
            st.subheader("🆔 Identité Festival")
            new_name = st.text_input("Nom du Festival", st.session_state.festival_name)
            if new_name != st.session_state.festival_name: st.session_state.festival_name = new_name; st.rerun()
            new_logo = st.file_uploader("Logo du Festival (Image)", type=['png', 'jpg', 'jpeg'])
            if new_logo: st.session_state.festival_logo = new_logo.read(); st.success("Logo chargé !")
            
            st.subheader("💾 Sauvegarde Projet")
            data_to_save = {k: v for k, v in st.session_state.items() if k in ["planning", "fiches_tech", "riders_stockage", "artist_circuits", "patch_in_out", "festival_name", "festival_logo", "custom_catalog"]}
            st.download_button("💾 Sauvegarder ma Session (.pkl)", pickle.dumps(data_to_save), f"backup_festival.pkl")
            
        with col_adm2:
            st.subheader("📚 Catalogue Matériel (Excel)")
            code_secret = st.text_input("🔒 Code Admin", type="password")
            if code_secret == "0000":
                xls_file = st.file_uploader("Fichier Excel Items", type=['xlsx', 'xls'])
                if xls_file and st.button("Charger le Catalogue"):
                    xls = pd.ExcelFile(xls_file)
                    new_catalog = {sheet: {brand: pd.read_excel(xls, sheet_name=sheet)[brand].dropna().astype(str).tolist() for brand in pd.read_excel(xls, sheet_name=sheet).columns} for sheet in xls.sheet_names}
                    st.session_state.custom_catalog = new_catalog
                    st.success("Catalogue chargé !")

    with sub_tabs_config[2]:
        st.header("📄 Exports PDF")
        if st.button("Générer PDF Planning"):
            pdf_bytes = generer_pdf_complet("PLANNING GLOBAL", {"Plannings": st.session_state.planning})
            st.download_button("📥 Télécharger", pdf_bytes, "planning.pdf")

# ==========================================
# ONGLET 2 : TECHNIQUE
# ==========================================
with main_tabs[1]:
    sub_tabs_tech = st.tabs(["Saisie du matériel", "Patch IN / OUT"])
    
    with sub_tabs_tech[0]:
        if not st.session_state.planning.empty:
            f1, f2, f3 = st.columns(3)
            sel_j = f1.selectbox("📅 Jour", sorted(st.session_state.planning["Jour"].unique()), key="j1")
            sel_s = f2.selectbox("🏗️ Scène", st.session_state.planning[st.session_state.planning["Jour"] == sel_j]["Scène"].unique(), key="s1")
            sel_a = f3.selectbox("🎸 Groupe", st.session_state.planning[(st.session_state.planning["Jour"] == sel_j) & (st.session_state.planning["Scène"] == sel_s)]["Artiste"].unique(), key="a1")

            if sel_a:
                st.subheader(f"⚙️ Circuits : {sel_a}")
                if sel_a not in st.session_state.artist_circuits: st.session_state.artist_circuits[sel_a] = {"inputs": 0, "ear_stereo": 0, "mon_stereo": 0, "mon_mono": 0}
                c_c1, c_c2, c_c3, c_c4 = st.columns(4)
                st.session_state.artist_circuits[sel_a]["inputs"] = c_c1.number_input("Entrées", 0, 128, int(st.session_state.artist_circuits[sel_a]["inputs"]))
                st.session_state.artist_circuits[sel_a]["ear_stereo"] = c_c2.number_input("EAR Stéréo", 0, 32, int(st.session_state.artist_circuits[sel_a]["ear_stereo"]))
                st.session_state.artist_circuits[sel_a]["mon_stereo"] = c_c3.number_input("MON Stéréo", 0, 32, int(st.session_state.artist_circuits[sel_a]["mon_stereo"]))
                st.session_state.artist_circuits[sel_a]["mon_mono"] = c_c4.number_input("MON Mono", 0, 32, int(st.session_state.artist_circuits[sel_a]["mon_mono"]))

                st.divider()
                st.subheader(f"📥 Matériel : {sel_a}")
                CAT = st.session_state.custom_catalog
                c_cat, c_mar, c_mod, c_qte, c_app = st.columns([2, 2, 2, 1, 1])
                v_cat = c_cat.selectbox("Catégorie", list(CAT.keys()) if CAT else ["MICROS"])
                v_mar = c_mar.selectbox("Marque", list(CAT[v_cat].keys()) if CAT and v_cat in CAT else ["SHURE"])
                v_mod = c_mod.selectbox("Modèle", CAT[v_cat][v_mar] if CAT and v_cat in CAT and v_mar in CAT[v_cat] else ["SM58"])
                v_qte = c_qte.number_input("Qté", 1, 100, 1)
                v_app = c_app.checkbox("Apporte")
                if st.button("Ajouter"):
                    new_item = pd.DataFrame([{"Scène": sel_s, "Jour": sel_j, "Groupe": sel_a, "Catégorie": v_cat, "Marque": v_mar, "Modèle": v_mod, "Quantité": v_qte, "Artiste_Apporte": v_app}])
                    st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, new_item], ignore_index=True)
                    st.rerun()
                
                # Affichage des items sous le bouton ajouter
                st.dataframe(st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"] == sel_a], use_container_width=True)

    with sub_tabs_tech[1]:
        st.subheader("📋 Patch IN / OUT")
        if not st.session_state.planning.empty:
            f1p, f2p, f3p = st.columns(3)
            sel_j_p = f1p.selectbox("📅 Jour ", sorted(st.session_state.planning["Jour"].unique()), key="j2")
            sel_s_p = f2p.selectbox("🏗️ Scène ", st.session_state.planning[st.session_state.planning["Jour"] == sel_j_p]["Scène"].unique(), key="s2")
            sel_a_p = f3p.selectbox("🎸 Groupe ", st.session_state.planning[(st.session_state.planning["Jour"] == sel_j_p) & (st.session_state.planning["Scène"] == sel_s_p)]["Artiste"].unique(), key="a2")

            if sel_a_p:
                # Récupération du total des entrées
                total_in = int(st.session_state.artist_circuits.get(sel_a_p, {}).get("inputs", 0))
                
                # Formatage
                st.divider()
                type_p = st.radio("Format Boîtier :", ["12N", "20H"], horizontal=True)
                step = 12 if "12N" in type_p else 20
                nb_departs = math.ceil(total_in / step) if total_in > 0 else 1
                
                # Initialisation de la structure de stockage si inexistante
                # On utilise un dictionnaire par Artiste pour stocker les DataFrames des différents départs
                pk_artiste = f"{sel_s_p}_{sel_j_p}_{sel_a_p}"
                if pk_artiste not in st.session_state.patch_in_out:
                    st.session_state.patch_in_out[pk_artiste] = {}

                all_inputs = [f"INPUT {i}" for i in range(1, total_in + 1)]
                matos_groupe = [""] + st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"] == sel_a_p]["Modèle"].unique().tolist()
                list_boitiers = [f"B{step}-{i}" for i in range(1, 10)]

                # Calcul des entrées déjà utilisées sur TOUS les tableaux de cet artiste pour le filtrage
                used_inputs = []
                for d_idx in range(1, nb_departs + 1):
                    if d_num_df := st.session_state.patch_in_out[pk_artiste].get(d_idx):
                        used_inputs.extend(d_num_df["Input Console"].dropna().tolist())

                # GENERATION DES TABLEAUX PAR DEPART
                for d in range(1, nb_departs + 1):
                    st.markdown(f"### 📦 DEPART {d}")
                    
                    # Si le tableau pour ce départ n'existe pas, on le crée
                    if d not in st.session_state.patch_in_out[pk_artiste]:
                        st.session_state.patch_in_out[pk_artiste][d] = pd.DataFrame(columns=["Boîtier", "Position", "Input Console", "Nom Canal", "Micro", "Stand"])

                    df_current = st.session_state.patch_in_out[pk_artiste][d]
                    
                    # Filtrage : On propose les entrées libres + celles déjà sélectionnées dans CE tableau
                    inputs_utilises_ici = df_current["Input Console"].tolist()
                    options_disponibles = [i for i in all_inputs if i not in used_inputs or i in inputs_utilises_ici]

                    edited_df = st.data_editor(
                        df_current,
                        key=f"patch_ed_{pk_artiste}_{d}",
                        num_rows="dynamic",
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Boîtier": st.column_config.SelectboxColumn(options=list_boitiers, width="small"),
                            "Position": st.column_config.NumberColumn(min_value=1, max_value=step),
                            "Input Console": st.column_config.SelectboxColumn(options=options_disponibles, required=True),
                            "Micro": st.column_config.SelectboxColumn(options=matos_groupe),
                            "Stand": st.column_config.SelectboxColumn(options=matos_groupe),
                        }
                    )
                    # Sauvegarde du tableau
                    st.session_state.patch_in_out[pk_artiste][d] = edited_df

                if total_in == 0:
                    st.warning("⚠️ Définissez le nombre d'entrées (Inputs) dans 'Saisie du matériel' pour voir les tableaux.")
