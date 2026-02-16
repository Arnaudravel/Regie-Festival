import streamlit as st
import pandas as pd
from fpdf import FPDF
from PIL import Image
import base64
import io
import datetime
import json

# --- 1. CONFIGURATION & STATE ---
st.set_page_config(page_title="Régie Festival Pro", layout="wide")

# Initialisation des variables (mémoire de l'appli)
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
    # Bibliothèque par défaut (sera écrasée si tu charges ton Excel)
    st.session_state.bibliotheque = {
        "MICROS FILAIRE": {"SHURE": ["SM58", "SM57", "BETA52"], "SENNHEISER": ["MD421", "E906"]},
        "REGIE": {"YAMAHA": ["QL1", "CL5"], "MIDAS": ["M32"]},
        "MICROS HF": {"SHURE": ["AD4D"], "SENNHEISER": ["6000 Series"]},
        "EAR MONITOR": {"SHURE": ["PSM1000"]}
    }

# --- 2. FONCTIONS TECHNIQUES (Excel, Calcul, PDF) ---

def charger_bibliotheque_excel(file):
    """Lit ton fichier Excel et met à jour les menus déroulants"""
    try:
        dict_final = {}
        all_sheets = pd.read_excel(file, sheet_name=None)
        for sheet_name, df in all_sheets.items():
            # On retire "DONNEES" pour avoir le nom propre de la catégorie
            cat_name = sheet_name.replace("DONNEES ", "").upper()
            dict_final[cat_name] = {}
            for col in df.columns:
                # On prend le nom avant le tiret (ex: SHURE_FILAIRE -> SHURE)
                brand_name = col.split('_')[0].upper()
                models = df[col].dropna().astype(str).tolist()
                if models:
                    dict_final[cat_name][brand_name] = models
        return dict_final
    except Exception as e:
        st.error(f"Erreur lecture Excel : {e}")
        return st.session_state.bibliotheque

def calculer_besoin_journee(df_tech, planning, scene, jour):
    """Le fameux calcul N+N+1"""
    # 1. On récupère l'ordre de passage
    plan = planning[(planning["Scène"] == scene) & (planning["Jour"] == jour)].copy().sort_values(by="Show")
    artistes = plan["Artiste"].tolist()
    
    if not artistes: return pd.DataFrame() # Pas d'artistes ce jour là
    
    # 2. On filtre le matériel demandé (en excluant ce que l'artiste amène lui-même)
    matos_regie = df_tech[(df_tech["Scène"] == scene) & (df_tech["Jour"] == jour) & (df_tech["Artiste_Apporte"] == False)]
    
    if matos_regie.empty: return pd.DataFrame() # Rien demandé
    
    # Cas simple : 1 seul artiste
    if len(artistes) == 1:
        return matos_regie.groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].sum().reset_index()

    # Cas N+N+1 : On compare les artistes par paires (Binômes)
    besoins_binomes = []
    for i in range(len(artistes) - 1):
        groupe_A = artistes[i]
        groupe_B = artistes[i+1]
        
        # On prend le matos de A et B
        df_binome = matos_regie[matos_regie["Groupe"].isin([groupe_A, groupe_B])]
        # On somme les quantités par modèle pour ce binôme
        sum_binome = df_binome.groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].sum()
        besoins_binomes.append(sum_binome)
    
    # On prend le maximum de tous les binômes
    if besoins_binomes:
        res = pd.concat(besoins_binomes, axis=1).max(axis=1).reset_index()
        res.columns = ["Catégorie", "Marque", "Modèle", "Quantité"]
        return res
    
    return pd.DataFrame()

class FestivalPDF(FPDF):
    def header(self):
        if st.session_state.logo_festival:
            # Astuce pour mettre le logo PIL dans le PDF
            img = st.session_state.logo_festival
            with io.BytesIO() as buf:
                img.save(buf, format='PNG')
                with open("temp_logo.png", "wb") as f: f.write(buf.getvalue())
            self.image("temp_logo.png", 10, 8, 25)
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, st.session_state.nom_festival, 0, 1, 'R')
        self.ln(12)

def export_categorized_pdf(df, title):
    pdf = FestivalPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, title, ln=True, align='C'); pdf.ln(10)
    
    if df.empty:
        pdf.set_font("Arial", 'I', 12); pdf.cell(0, 10, "Aucun matériel requis.", ln=True)
        return pdf.output(dest='S').encode('latin-1')

    # Grouper par catégorie
    for cat in df["Catégorie"].unique():
        pdf.set_fill_color(200, 220, 255)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, f"Catégorie : {cat}", ln=True, fill=True)
        
        # En-têtes tableau
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(60, 8, "Marque", 1, 0, 'L', True)
        pdf.cell(100, 8, "Modèle", 1, 0, 'L', True)
        pdf.cell(30, 8, "Quantité", 1, 1, 'C', True)
        
        pdf.set_font("Arial", '', 10)
        for _, row in df[df["Catégorie"] == cat].iterrows():
            pdf.cell(60, 7, str(row["Marque"]), 1)
            pdf.cell(100, 7, str(row["Modèle"]), 1)
            pdf.cell(30, 7, str(row["Quantité"]), 1, 1, 'C')
        pdf.ln(5)
    
    return pdf.output(dest='S').encode('latin-1')

def export_planning_structured(df, title):
    pdf = FestivalPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 15, title, ln=True, align='C')
    pdf.ln(10)
    
    jours = sorted(df["Jour"].unique())
    for jour in jours:
        pdf.set_fill_color(0, 0, 0)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, f"DATE : {jour}", 1, 1, 'L', True)
        pdf.set_text_color(0, 0, 0)
        
        scenes_jour = df[df["Jour"] == jour]["Scène"].unique()
        for scene in scenes_jour:
            pdf.ln(2)
            pdf.set_fill_color(230, 230, 230)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 8, f"SCÈNE : {scene}", "L", 1, 'L', True)
            
            # Tableau des artistes
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(30, 8, "Show", 1, 0, 'C')
            pdf.cell(120, 8, "Artiste", 1, 0, 'L')
            pdf.cell(30, 8, "Balance", 1, 1, 'C')
            
            pdf.set_font("Arial", '', 10)
            subset = df[(df["Jour"] == jour) & (df["Scène"] == scene)].sort_values(by="Show")
            for _, row in subset.iterrows():
                pdf.cell(30, 8, str(row["Show"]), 1, 0, 'C')
                pdf.cell(120, 8, str(row["Artiste"]), 1, 0, 'L')
                pdf.cell(30, 8, str(row["Balance"]), 1, 1, 'C')
            pdf.ln(5)
        pdf.ln(5)
    return pdf.output(dest='S').encode('latin-1')


# --- 3. INTERFACE UTILISATEUR ---

# En-tête avec Logo et Titre
col_header_1, col_header_2 = st.columns([1, 5])
with col_header_1:
    if st.session_state.logo_festival:
        st.image(st.session_state.logo_festival, width=120)
with col_header_2:
    st.title(st.session_state.nom_festival)

# Onglets principaux
tabs = st.tabs(["🏗️ Configuration & Planning", "⚙️ Patch & Régie", "📄 Exports PDF"])

# ==================== ONGLET 1 : CONFIGURATION ====================
with tabs[0]:
    # -- Zone Options Avancées (fermée par défaut pour ne pas polluer) --
    with st.expander("🛠️ Options Avancées (Excel, Sauvegarde, Logo) - CLIQUE ICI POUR OUVRIR"):
        c1, c2 = st.columns(2)
        st.session_state.nom_festival = c1.text_input("Nom du Festival", st.session_state.nom_festival)
        upl_logo = c2.file_uploader("Logo du Festival", type=["png", "jpg"])
        if upl_logo: st.session_state.logo_festival = Image.open(upl_logo)
        
        st.divider()
        col_ex_1, col_ex_2 = st.columns(2)
        with col_ex_1:
            st.markdown("### 1. Importer Bibliothèque Excel")
            st.info("Glisse ton fichier Excel ici pour mettre à jour les marques/modèles.")
            base_excel = st.file_uploader("Fichier Excel", type=["xlsx"], label_visibility="collapsed")
            if base_excel and st.button("Charger le fichier Excel"):
                st.session_state.bibliotheque = charger_bibliotheque_excel(base_excel)
                st.success("✅ Bibliothèque mise à jour avec succès !")
        
        with col_ex_2:
            st.markdown("### 2. Sauvegarder / Charger Projet")
            # Export JSON
            data_to_save = {
                "planning": st.session_state.planning.to_json(),
                "fiches": st.session_state.fiches_tech.to_json(),
                "nom": st.session_state.nom_festival
            }
            st.download_button("📥 Sauvegarder tout le travail (.json)", json.dumps(data_to_save), f"backup_{st.session_state.nom_festival}.json")
            
            # Import JSON
            load_proj = st.file_uploader("Charger une sauvegarde", type=["json"])
            if load_proj:
                d = json.load(load_proj)
                st.session_state.planning = pd.read_json(io.StringIO(d["planning"]))
                st.session_state.fiches_tech = pd.read_json(io.StringIO(d["fiches"]))
                st.session_state.nom_festival = d["nom"]
                st.rerun()

    st.divider()

    # -- Saisie Artiste (Interface "Clean") --
    st.subheader("➕ Ajouter un Artiste au Planning")
    with st.container(border=True):
        col1, col2, col3, col4, col5 = st.columns([2, 2, 3, 1, 1])
        in_sc = col1.text_input("Scène", "MainStage")
        in_jo = col2.date_input("Date du passage", datetime.date.today())
        in_art = col3.text_input("Nom de l'Artiste / Groupe")
        in_bal = col4.text_input("Heure Balance", "14:00")
        in_sho = col5.text_input("Heure Show", "20:00")
        
        in_files = st.file_uploader("Glisser les Fiches Techniques (PDF) ici", accept_multiple_files=True, key=f"pdf_up_{st.session_state.pdf_uploader_key}")
        
        if st.button("Valider l'Artiste", type="primary", use_container_width=True):
            if in_art:
                # Ajout au planning
                new_row = pd.DataFrame([{"Scène": in_sc, "Jour": in_jo, "Artiste": in_art, "Balance": in_bal, "Show": in_sho}])
                st.session_state.planning = pd.concat([st.session_state.planning, new_row], ignore_index=True)
                
                # Stockage des PDF
                if in_files:
                    st.session_state.riders_stockage[in_art] = {f.name: f.read() for f in in_files}
                
                # Reset uploader
                st.session_state.pdf_uploader_key += 1
                st.rerun()
            else:
                st.warning("Il faut au moins un nom d'artiste !")

    # -- Tableau Planning avec Croix Rouge/Verte --
    st.subheader("📅 Planning Global")
    if not st.session_state.planning.empty:
        # Création colonne visuelle pour PDF
        df_display = st.session_state.planning.copy()
        
        # Fonction pour dire si PDF existe ou pas
        def check_pdf(nom_artiste):
            if nom_artiste in st.session_state.riders_stockage and st.session_state.riders_stockage[nom_artiste]:
                return "✅ Oui"
            return "❌ Non"
            
        df_display.insert(0, "PDF Reçu ?", df_display["Artiste"].apply(check_pdf))
        
        edited_df = st.data_editor(
            df_display,
            column_config={
                "PDF Reçu ?": st.column_config.TextColumn("Fiche Tech", disabled=True),
            },
            use_container_width=True,
            num_rows="dynamic"
        )
        
        # Bouton sauvegarde modifs tableau
        if st.button("Enregistrer les modifications du tableau"):
            # On remet le dataframe propre (sans la colonne visuelle PDF) dans le state
            cols_to_keep = ["Scène", "Jour", "Artiste", "Balance", "Show"]
            st.session_state.planning = edited_df[cols_to_keep]
            st.rerun()


# ==================== ONGLET 2 : PATCH (L'interface que tu aimais) ====================
with tabs[1]:
    if st.session_state.planning.empty:
        st.info("Commence par ajouter des artistes dans l'onglet Configuration.")
    else:
        # Sélecteurs en haut
        c_sel1, c_sel2, c_sel3, c_sel4 = st.columns([1, 1, 1, 2])
        
        # Listes dynamiques basées sur le planning
        liste_jours = sorted(st.session_state.planning["Jour"].astype(str).unique())
        choix_jour = c_sel1.selectbox("Sélectionner le Jour", liste_jours)
        
        liste_scenes = st.session_state.planning[st.session_state.planning["Jour"].astype(str) == choix_jour]["Scène"].unique()
        choix_scene = c_sel2.selectbox("Sélectionner la Scène", liste_scenes)
        
        liste_artistes = st.session_state.planning[
            (st.session_state.planning["Jour"].astype(str) == choix_jour) & 
            (st.session_state.planning["Scène"] == choix_scene)
        ]["Artiste"].unique()
        choix_artiste = c_sel3.selectbox("Sélectionner l'Artiste", liste_artistes)

        # Visionneuse PDF rapide
        with c_sel4:
            pdfs = st.session_state.riders_stockage.get(choix_artiste, {})
            if pdfs:
                pdf_choisi = st.selectbox("Voir fiche technique :", list(pdfs.keys()))
                if pdf_choisi:
                    base64_pdf = base64.b64encode(pdfs[pdf_choisi]).decode('utf-8')
                    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="200" type="application/pdf"></iframe>'
                    # Petit bouton pour ouvrir en grand
                    href = f'<a href="data:application/pdf;base64,{base64_pdf}" download="{pdf_choisi}" target="_blank">Ouvrir {pdf_choisi} en grand</a>'
                    st.markdown(href, unsafe_allow_html=True)
            else:
                st.warning("⚠️ Pas de PDF pour cet artiste")

        st.divider()

        # --- ZONE DE SAISIE OPTIMISÉE (Catégorie | Marque | Modèle | Qté | Checkbox) ---
        st.markdown(f"### 📥 Saisie Patch : {choix_artiste}")
        
        with st.container(border=True):
            # Colonnes ratio : Catégorie(2), Marque(2), Modèle(2), Qté(1), Checkbox(1), Bouton(1)
            col_in1, col_in2, col_in3, col_in4, col_in5 = st.columns([2, 2, 2, 1, 1.5])
            
            cat_list = list(st.session_state.bibliotheque.keys())
            s_cat = col_in1.selectbox("Catégorie", cat_list)
            
            mar_list = list(st.session_state.bibliotheque.get(s_cat, {}).keys())
            s_mar = col_in2.selectbox("Marque", mar_list)
            
            mod_list = st.session_state.bibliotheque.get(s_cat, {}).get(s_mar, []) + ["+ AUTRE (Saisie Libre)"]
            s_mod = col_in3.selectbox("Modèle", mod_list)
            
            if s_mod == "+ AUTRE (Saisie Libre)":
                s_mod = col_in3.text_input("Tapez la référence...")
            
            s_qte = col_in4.number_input("Qté", min_value=1, value=1)
            
            # CHECKBOX "AMENÉ PAR L'ARTISTE" (Directement accessible ici)
            is_brought = col_in5.checkbox("Amené par Artiste ?")
            
            if st.button("Ajouter ligne", use_container_width=True):
                new_line = {
                    "Scène": choix_scene,
                    "Jour": choix_jour,
                    "Groupe": choix_artiste,
                    "Catégorie": s_cat,
                    "Marque": s_mar,
                    "Modèle": s_mod,
                    "Quantité": s_qte,
                    "Artiste_Apporte": is_brought
                }
                st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, pd.DataFrame([new_line])], ignore_index=True)
                st.rerun()

        # --- AFFICHAGE CÔTE À CÔTE (Patch Individuel vs Cumul) ---
        col_gauche, col_droite = st.columns([1, 1])
        
        with col_gauche:
            st.subheader(f"📋 Liste Matériel : {choix_artiste}")
            # Filtre pour n'afficher que l'artiste en cours
            mask = (st.session_state.fiches_tech["Groupe"] == choix_artiste) & \
                   (st.session_state.fiches_tech["Jour"].astype(str) == str(choix_jour))
            
            df_art = st.session_state.fiches_tech[mask]
            
            # Editeur pour pouvoir supprimer ou modifier des lignes
            df_edited = st.data_editor(df_art, num_rows="dynamic", use_container_width=True, key="editor_patch")
            
            # Bouton de sauvegarde spécifique au patch
            if st.button("💾 Sauvegarder modifications patch"):
                # On met à jour le DataFrame principal
                # 1. On enlève les anciennes lignes de cet artiste
                st.session_state.fiches_tech = st.session_state.fiches_tech[~mask]
                # 2. On remet les nouvelles
                st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, df_edited], ignore_index=True)
                st.rerun()

        with col_droite:
            st.subheader(f"📊 Cumul Journée (N+N+1)")
            # Calcul en temps réel
            df_besoin = calculer_besoin_journee(st.session_state.fiches_tech, st.session_state.planning, choix_scene, choix_jour)
            
            if df_besoin.empty:
                st.info("Rien à calculer pour l'instant (ou pas assez d'artistes).")
            else:
                st.dataframe(df_besoin, use_container_width=True, hide_index=True)
                st.caption("Ce tableau montre ce que la régie doit fournir (Max des binômes).")


# ==================== ONGLET 3 : EXPORTS (Fonctionnels) ====================
with tabs[2]:
    st.header("📄 Génération des documents PDF")
    
    c_exp1, c_exp2 = st.columns(2)
    
    with c_exp1:
        st.subheader("1. Planning Officiel")
        if st.button("Générer le PDF Planning"):
            pdf_data = export_planning_structured(st.session_state.planning, f"Planning - {st.session_state.nom_festival}")
            st.download_button("📥 Télécharger Planning.pdf", pdf_data, "planning_festival.pdf", "application/pdf")
            
    with c_exp2:
        st.subheader("2. Liste Matériel (Régie)")
        st.write("Génère la liste du matériel que la régie doit fournir (calcul N+N+1).")
        
        # Choix contextuel pour l'export
        if not st.session_state.planning.empty:
            jour_export = st.selectbox("Pour quel jour ?", sorted(st.session_state.planning["Jour"].astype(str).unique()), key="exp_j")
            scene_export = st.selectbox("Pour quelle scène ?", st.session_state.planning["Scène"].unique(), key="exp_s")
            
            if st.button("Générer Liste Matériel"):
                # On fait le calcul pour le PDF
                df_calc = calculer_besoin_journee(st.session_state.fiches_tech, st.session_state.planning, scene_export, jour_export)
                
                pdf_matos = export_categorized_pdf(df_calc, f"Besoin Matériel - {scene_export} - {jour_export}")
                st.download_button("📥 Télécharger Liste Matériel.pdf", pdf_matos, f"matos_{scene_export}_{jour_export}.pdf", "application/pdf")
        else:
            st.warning("Remplissez d'abord le planning.")
