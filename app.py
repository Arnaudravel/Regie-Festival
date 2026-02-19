import streamlit as st
import pandas as pd
import datetime
from fpdf import FPDF
import io
import pickle
import streamlit.components.v1 as components

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Regie-Festival", layout="wide", initial_sidebar_state="collapsed")

# --- RAPPEL DE SAUVEGARDE (JS) ---
st.components.v1.html(
    """
    <script>
    setInterval(function(){
        alert("💾 RAPPEL : Pensez à sauvegarder votre projet dans l'onglet 'Admin' !");
    }, 600000);
    </script>
    """,
    height=0, width=0
)

# --- INITIALISATION ---
if 'planning' not in st.session_state:
    st.session_state.planning = pd.DataFrame(columns=["Scène", "Jour", "Artiste", "Balance", "Durée Balance", "Show"])
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
if 'festival_name' not in st.session_state:
    st.session_state.festival_name = "MON FESTIVAL"
if 'festival_logo' not in st.session_state:
    st.session_state.festival_logo = None
if 'custom_catalog' not in st.session_state:
    st.session_state.custom_catalog = {} 

# --- MOTEUR PDF ---
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

# --- INTERFACE ---
st.title(f"{st.session_state.festival_name} - Gestion Régie")
tabs = st.tabs(["🏗️ Configuration", "⚙️ Patch & Régie", "📄 Exports PDF", "🛠️ Admin & Sauvegarde"])

# --- ONGLET 1 : CONFIGURATION ---
with tabs[0]:
    st.subheader("➕ Ajouter un Artiste")
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1, 1, 2, 1])
        sc = c1.text_input("Scène", "MainStage")
        jo = c2.date_input("Date de passage", datetime.date.today())
        ar = c3.text_input("Nom Artiste")
        sh = c4.time_input("Heure du Show", datetime.time(20, 0))
        
        opt_balance = st.checkbox("Faire une balance ?", value=True)
        ba = st.time_input("Heure Balance", datetime.time(14, 0)) if opt_balance else None
        du = st.text_input("Durée Balance", "45 min") if opt_balance else ""

        pdfs = st.file_uploader("Fiches Techniques (PDF)", accept_multiple_files=True, key=f"upl_{st.session_state.uploader_key}")
        
        if st.button("Valider Artiste"):
            if ar:
                val_ba = ba.strftime("%H:%M") if ba else ""
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
        # Gestion suppression simplifiée
        if not edited_df.drop(columns=["Rider"]).equals(st.session_state.planning):
            st.session_state.planning = edited_df.drop(columns=["Rider"]).reset_index(drop=True)

# --- ONGLET 2 : PATCH & RÉGIE ---
with tabs[1]:
    if not st.session_state.planning.empty:
        f1, f2, f3 = st.columns(3)
        sel_j = f1.selectbox("📅 Jour", sorted(st.session_state.planning["Jour"].unique()))
        scenes = st.session_state.planning[st.session_state.planning["Jour"] == sel_j]["Scène"].unique()
        sel_s = f2.selectbox("🏗️ Scène", scenes)
        artistes = st.session_state.planning[(st.session_state.planning["Jour"] == sel_j) & (st.session_state.planning["Scène"] == sel_s)]["Artiste"].unique()
        sel_a = f3.selectbox("🎸 Groupe", artistes)

        if sel_a:
            st.subheader(f"📥 Saisie Matériel : {sel_a}")
            with st.container(border=True):
                CATALOGUE = st.session_state.custom_catalog
                c_cat, c_mar, c_mod, c_qte, c_app = st.columns([2, 2, 2, 1, 1])
                v_cat = c_cat.selectbox("Catégorie", list(CATALOGUE.keys()) if CATALOGUE else ["MICROS FILAIRE", "HF", "EAR MONITOR"])
                v_mar = c_mar.selectbox("Marque", list(CATALOGUE[v_cat].keys()) if (CATALOGUE and v_cat in CATALOGUE) else ["SHURE", "SENNHEISER"])
                v_mod = c_mod.selectbox("Modèle", CATALOGUE[v_cat][v_mar]) if (CATALOGUE and v_cat in CATALOGUE and v_mar in CATALOGUE[v_cat]) else c_mod.text_input("Modèle")
                v_qte = c_qte.number_input("Qté", 1, 500, 1)
                v_app = c_app.checkbox("Artiste Apporte")
                
                if st.button("Ajouter au Patch"):
                    new_item = pd.DataFrame([{"Scène": sel_s, "Jour": sel_j, "Groupe": sel_a, "Catégorie": v_cat, "Marque": v_mar, "Modèle": v_mod, "Quantité": v_qte, "Artiste_Apporte": v_app}])
                    st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, new_item], ignore_index=True)
                    st.rerun()

            col_patch, col_besoin = st.columns(2)
            with col_patch:
                st.subheader("📋 Patch Groupe")
                df_p = st.session_state.fiches_tech[st.session_state.fiches_tech["Groupe"] == sel_a]
                st.data_editor(df_p, use_container_width=True, hide_index=True, key=f"edit_{sel_a}")

            with col_besoin:
                st.subheader(f"📊 Pic de besoin {sel_s}")
                df_b = st.session_state.fiches_tech[(st.session_state.fiches_tech["Scène"] == sel_s) & (st.session_state.fiches_tech["Jour"] == sel_j) & (st.session_state.fiches_tech["Artiste_Apporte"] == False)]
                if not df_b.empty:
                    matrice = df_b.groupby(["Catégorie", "Marque", "Modèle", "Groupe"])["Quantité"].sum().unstack(fill_value=0)
                    res = matrice.max(axis=1).reset_index().rename(columns={0: "Quantité"})
                    st.dataframe(res, use_container_width=True, hide_index=True)

# --- ONGLET 3 : EXPORTS ---
with tabs[2]:
    st.header("📄 Exports PDF")
    l_jours = sorted(st.session_state.planning["Jour"].unique())
    l_scenes = sorted(st.session_state.planning["Scène"].unique())
    
    if st.button("🚀 Générer Rapport Complet (Besoins par Scène)"):
        dico_global = {}
        for s in l_scenes:
            df_s = st.session_state.fiches_tech[(st.session_state.fiches_tech["Scène"] == s) & (st.session_state.fiches_tech["Artiste_Apporte"] == False)]
            if not df_s.empty:
                res_s = df_s.groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].sum().reset_index()
                dico_global[f"BESOINS TOTAUX : {s}"] = res_s
        pdf_b = generer_pdf_complet("RAPPORT TECHNIQUE GLOBAL", dico_global)
        st.download_button("📥 Télécharger Rapport", pdf_b, "rapport_regie.pdf")

# --- ONGLET 4 : ADMIN ---
with tabs[3]:
    st.header("🛠️ Admin")
    if st.button("💾 Sauvegarder Session"):
        st.download_button("Télécharger Backup", pickle.dumps(st.session_state.to_dict()), "festival_backup.pkl")
