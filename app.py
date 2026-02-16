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

# Initialisation des variables
if 'nom_festival' not in st.session_state: st.session_state.nom_festival = "Mon Festival"
if 'logo_festival' not in st.session_state: st.session_state.logo_festival = None

# Structure du Planning (Colonnes fixes)
if 'planning' not in st.session_state:
    st.session_state.planning = pd.DataFrame(columns=["Scène", "Jour", "Artiste", "Balance", "Show"])

# Structure des Fiches Techniques
if 'fiches_tech' not in st.session_state:
    st.session_state.fiches_tech = pd.DataFrame(columns=["Scène", "Jour", "Groupe", "Catégorie", "Marque", "Modèle", "Quantité", "Artiste_Apporte"])

# Stockage des PDF (Dictionnaire: Artiste -> {NomFichier: Bytes})
if 'riders_stockage' not in st.session_state:
    st.session_state.riders_stockage = {} 

# Bibliothèque Matériel par défaut
if 'bibliotheque' not in st.session_state:
    st.session_state.bibliotheque = {
        "MICROS FILAIRE": {"SHURE": ["SM58", "SM57", "BETA52"], "SENNHEISER": ["MD421", "E906", "E604"]},
        "REGIE": {"YAMAHA": ["QL1", "CL5"], "MIDAS": ["M32", "PRO1"]},
        "MICROS HF": {"SHURE": ["AD4D", "ULXD"], "SENNHEISER": ["6000 Series", "EW-DX"]},
        "DI / LINE": {"BSS": ["AR133"], "RADIAL": ["J48", "JDI"]},
        "STANDS": {"K&M": ["Grand Perche", "Petit Perche", "Droit"]}
    }

# --- 2. FONCTIONS MÉTIER ---

def charger_bibliotheque_excel(file):
    """Charge le fichier Excel et met à jour les menus déroulants"""
    try:
        dict_final = {}
        all_sheets = pd.read_excel(file, sheet_name=None)
        for sheet_name, df in all_sheets.items():
            cat_name = sheet_name.replace("DONNEES ", "").upper()
            dict_final[cat_name] = {}
            for col in df.columns:
                brand_name = col.split('_')[0].upper()
                models = df[col].dropna().astype(str).tolist()
                if models:
                    dict_final[cat_name][brand_name] = models
        return dict_final
    except Exception as e:
        st.error(f"Erreur format Excel : {e}")
        return st.session_state.bibliotheque

def calculer_besoin_max_scene(df_tech, planning, scene, jour):
    """
    CALCUL N + N+1 (Ta demande spécifique)
    1. On prend les artistes dans l'ordre du SHOW.
    2. On calcule le cumul (Artiste N + Artiste N+1).
    3. On prend le MAX de ces cumuls pour définir le besoin scène.
    """
    # 1. Récupérer l'ordre de passage
    plan = planning[(planning["Scène"] == scene) & (planning["Jour"] == jour)].copy()
    if plan.empty: return pd.DataFrame()
    
    # Tri par heure de Show (essentiel pour le N+1)
    plan = plan.sort_values(by="Show")
    artistes_ordonnes = plan["Artiste"].tolist()
    
    # Filtrer le matos nécessaire (exclure ce qui est apporté par l'artiste)
    matos_jour = df_tech[
        (df_tech["Scène"] == scene) & 
        (df_tech["Jour"] == jour) & 
        (df_tech["Artiste_Apporte"] == False)
    ]
    
    if matos_jour.empty: return pd.DataFrame()

    # Si un seul artiste, c'est simple
    if len(artistes_ordonnes) == 1:
        return matos_jour.groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].sum().reset_index()

    # Calcul des binômes (Changeovers)
    requirements_per_changeover = []
    
    # Pour chaque transition (Groupe i et Groupe i+1)
    for i in range(len(artistes_ordonnes) - 1):
        groupe_actuel = artistes_ordonnes[i]
        groupe_suivant = artistes_ordonnes[i+1]
        
        # Matos cumulé des deux
        df_binome = matos_jour[matos_jour["Groupe"].isin([groupe_actuel, groupe_suivant])]
        
        # Somme par modèle pour ce moment T
        sum_binome = df_binome.groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].sum().reset_index()
        requirements_per_changeover.append(sum_binome)
        
    # On ajoute aussi le cas du dernier groupe seul (optionnel mais prudent si c'est le plus gros)
    last_grp = matos_jour[matos_jour["Groupe"] == artistes_ordonnes[-1]]
    requirements_per_changeover.append(last_grp.groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].sum().reset_index())

    # CALCUL FINAL : On prend le MAX de tous les scénarios (Changeovers)
    if requirements_per_changeover:
        # On concatène tous les besoins calculés
        all_scenarios = pd.concat(requirements_per_changeover)
        # On prend le MAX pour chaque item
        final_req = all_scenarios.groupby(["Catégorie", "Marque", "Modèle"])["Quantité"].max().reset_index()
        return final_req
    
    return pd.DataFrame()

def calculer_besoin_global_festival(df_tech, planning):
    """
    RECAP ITEM FESTIVAL : Max ( Total J1, Total J2, Total J3... ) par Scène
    """
    scenes = planning["Scène"].unique()
    jours = planning["Jour"].unique()
    
    all_max_days = []
    
    for scene in scenes:
        daily_reqs = []
        for jour in jours:
            # Calcule le besoin MAX de la journée (selon logique N+N+1)
            req_jour = calculer_besoin_max_scene(df_tech, planning, scene, jour)
            if not req_jour.empty:
                req_jour["Scène_Ref"] = scene # Pour garder la trace
                daily_reqs.append(req_jour)
        
        if daily_reqs:
            # On prend le MAX parmi tous les jours pour cette scène
            df_scene_days = pd.concat(daily_reqs)
            max_scene = df_scene_days.groupby(["Scène_Ref", "Catégorie", "Marque", "Modèle"])["Quantité"].max().reset_index()
            all_max_days.append(max_scene)
            
    if all_max_days:
        return pd.concat(all_max_days)
    return pd.DataFrame()

# --- 3. MOTEUR PDF (Version Robuste) ---
class ReportPDF(FPDF):
    def header(self):
        if st.session_state.logo_festival:
            with io.BytesIO() as buf:
                st.session_state.logo_festival.save(buf, format='PNG')
                with open("logo_tmp.png", "wb") as f: f.write(buf.getvalue())
            self.image("logo_tmp.png", 10, 8, 30)
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, st.session_state.nom_festival, 0, 1, 'R')
        self.ln(15)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, label):
        self.set_fill_color(200, 220, 255)
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, label, 0, 1, 'L', True)
        self.ln(4)

    def add_table(self, df):
        if df.empty:
            self.set_font('Arial', 'I', 10)
            self.cell(0, 10, "Aucune donnée.", 1, 1)
            return
            
        # Headers
        self.set_font('Arial', 'B', 10)
        self.set_fill_color(240, 240, 240)
        cols = [c for c in df.columns if c not in ["Scène_Ref", "Jour", "Groupe", "Artiste_Apporte"]]
        
        # Largeurs colonnes auto-adaptatives (simple)
        w = [50, 80, 25] # Marque, Modèle, Qté (approx)
        
        self.cell(60, 7, "Catégorie", 1, 0, 'C', True)
        self.cell(50, 7, "Marque", 1, 0, 'C', True)
        self.cell(60, 7, "Modèle", 1, 0, 'C', True)
        self.cell(20, 7, "Qté", 1, 1, 'C', True)
        
        # Data
        self.set_font('Arial', '', 10)
        for _, row in df.iterrows():
            self.cell(60, 7, str(row["Catégorie"]), 1)
            self.cell(50, 7, str(row["Marque"]), 1)
            self.cell(60, 7, str(row["Modèle"]), 1)
            self.cell(20, 7, str(row["Quantité"]), 1, 1, 'C')
        self.ln(5)

def generer_pdf_global():
    pdf = ReportPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 20)
    pdf.cell(0, 10, "DOSSIER TECHNIQUE GLOBAL", 0, 1, 'C')
    pdf.ln(10)
    
    # 1. PLANNING
    pdf.chapter_title("1. PLANNING GÉNÉRAL")
    if not st.session_state.planning.empty:
        # Tri complet
        df_plan = st.session_state.planning.sort_values(by=["Jour", "Show"])
        for jour in df_plan["Jour"].unique():
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 8, f"DATE : {jour}", 0, 1)
            
            sub = df_plan[df_plan["Jour"] == jour]
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(30, 7, "Scène", 1)
            pdf.cell(30, 7, "Heure Show", 1)
            pdf.cell(80, 7, "Artiste", 1)
            pdf.cell(30, 7, "Balance", 1, 1)
            
            pdf.set_font('Arial', '', 10)
            for _, row in sub.iterrows():
                pdf.cell(30, 7, str(row["Scène"]), 1)
                pdf.cell(30, 7, str(row["Show"]), 1)
                pdf.cell(80, 7, str(row["Artiste"]), 1)
                pdf.cell(30, 7, str(row["Balance"]), 1, 1)
            pdf.ln(5)
    
    pdf.add_page()
    
    # 2. BESOINS PAR JOUR ET SCÈNE (N+N+1)
    pdf.chapter_title("2. BESOINS PAR SCÈNE (Calcul N + N+1)")
    
    scenes = st.session_state.planning["Scène"].unique()
    jours = sorted(st.session_state.planning["Jour"].unique())
    
    for jour in jours:
        for scene in scenes:
            df_besoin = calculer_besoin_max_scene(st.session_state.fiches_tech, st.session_state.planning, scene, jour)
            if not df_besoin.empty:
                pdf.set_font('Arial', 'B', 11)
                pdf.cell(0, 8, f">> {jour} - SCÈNE : {scene}", 0, 1)
                pdf.add_table(df_besoin)
    
    pdf.add_page()
    
    # 3. RECAP FESTIVAL GLOBAL
    pdf.chapter_title("3. TOTAL FESTIVAL (Max des Jours)")
    df_global = calculer_besoin_global_festival(st.session_state.fiches_tech, st.session_state.planning)
    
    if not df_global.empty:
        for scene in df_global["Scène_Ref"].unique():
            pdf.set_font('Arial', 'B', 11)
            pdf.cell(0, 8, f"TOTAL GLOBAL POUR : {scene}", 0, 1)
            pdf.add_table(df_global[df_global["Scène_Ref"] == scene])
    else:
        pdf.cell(0, 10, "Pas assez de données pour le calcul global.", 0, 1)

    return pdf.output(dest='S').encode('latin-1')

# --- 4. INTERFACE UTILISATEUR ---

c_head1, c_head2 = st.columns([1, 5])
with c_head1:
    if st.session_state.logo_festival: st.image(st.session_state.logo_festival, width=100)
with c_head2:
    st.title(st.session_state.nom_festival)

tabs = st.tabs(["🏗️ Configuration", "⚙️ Patch & Régie", "📄 Exports & Rapports"])

# ==================== TAB 1 : CONFIGURATION ====================
with tabs[0]:
    with st.expander("Paramètres Généraux (Logo, Nom, Import Excel)"):
        c1, c2 = st.columns(2)
        st.session_state.nom_festival = c1.text_input("Nom", st.session_state.nom_festival)
        upl = c2.file_uploader("Logo", type=["png", "jpg"])
        if upl: st.session_state.logo_festival = Image.open(upl)
        
        st.divider()
        st.write("📂 **Bibliothèque Matériel (Excel)**")
        f_xlsx = st.file_uploader("Fichier Excel", type=["xlsx"], label_visibility="collapsed")
        if f_xlsx and st.button("Mettre à jour la Bibliothèque"):
            st.session_state.bibliotheque = charger_bibliotheque_excel(f_xlsx)
            st.success("Bibliothèque chargée !")

    st.subheader("➕ Ajouter un Artiste")
    with st.container(border=True):
        colA, colB, colC, colD, colE = st.columns([1.5, 1.5, 3, 1, 1])
        new_scene = colA.text_input("Scène", "MainStage")
        new_jour = colB.date_input("Date", datetime.date.today())
        new_artiste = colC.text_input("Nom Artiste")
        # FORMAT HORAIRE 24H : Utilisation de time_input
        new_bal = colD.time_input("Heure Balance", datetime.time(14, 0))
        new_show = colE.time_input("Heure Show", datetime.time(20, 0))
        
        # Uploader de PDF
        new_pdfs = st.file_uploader("Fiches Techniques (PDF)", accept_multiple_files=True)
        
        if st.button("Valider l'Artiste", type="primary", use_container_width=True):
            if new_artiste:
                # Conversion Heure -> String HH:MM pour affichage propre et tri
                str_bal = new_bal.strftime("%H:%M")
                str_show = new_show.strftime("%H:%M")
                
                row = pd.DataFrame([{
                    "Scène": new_scene, "Jour": new_jour, "Artiste": new_artiste, 
                    "Balance": str_bal, "Show": str_show
                }])
                st.session_state.planning = pd.concat([st.session_state.planning, row], ignore_index=True)
                
                # Ajout PDF
                if new_pdfs:
                    if new_artiste not in st.session_state.riders_stockage:
                        st.session_state.riders_stockage[new_artiste] = {}
                    for f in new_pdfs:
                        st.session_state.riders_stockage[new_artiste][f.name] = f.read()
                st.rerun()

    col_plan_L, col_plan_R = st.columns([2, 1])
    
    with col_plan_L:
        st.subheader("📅 Planning Actuel")
        if not st.session_state.planning.empty:
            # Affichage Planning
            st.dataframe(st.session_state.planning, use_container_width=True, hide_index=True)
            if st.button("🗑️ Reset Planning Complet"):
                st.session_state.planning = st.session_state.planning.iloc[0:0]
                st.session_state.riders_stockage = {}
                st.session_state.fiches_tech = st.session_state.fiches_tech.iloc[0:0]
                st.rerun()

    with col_plan_R:
        st.subheader("📁 Gestion des Fiches PDF")
        # Interface pour SUPPRIMER ou voir les PDF
        list_artistes_pdf = list(st.session_state.riders_stockage.keys())
        if list_artistes_pdf:
            art_pdf_choice = st.selectbox("Choisir Artiste", list_artistes_pdf)
            files = st.session_state.riders_stockage[art_pdf_choice]
            
            if files:
                file_to_del = st.selectbox("Fichier à gérer", list(files.keys()))
                if st.button(f"🗑️ Supprimer {file_to_del}"):
                    del st.session_state.riders_stockage[art_pdf_choice][file_to_del]
                    st.success("Fichier supprimé.")
                    st.rerun()
            else:
                st.info("Dossier vide pour cet artiste.")
        else:
            st.info("Aucun PDF chargé.")

# ==================== TAB 2 : PATCH & RÉGIE ====================
with tabs[1]:
    if st.session_state.planning.empty:
        st.warning("Ajoute d'abord des artistes dans l'onglet Configuration.")
    else:
        # 1. SÉLECTEURS
        c_s1, c_s2, c_s3, c_s4 = st.columns([1, 1, 1.5, 1.5])
        
        # Filtres dynamiques
        jours_dispo = sorted(st.session_state.planning["Jour"].astype(str).unique())
        s_jour = c_s1.selectbox("Jour", jours_dispo)
        
        scenes_dispo = st.session_state.planning[st.session_state.planning["Jour"].astype(str) == s_jour]["Scène"].unique()
        s_scene = c_s2.selectbox("Scène", scenes_dispo)
        
        # Tri des artistes par heure de show pour le menu
        df_filter = st.session_state.planning[
            (st.session_state.planning["Jour"].astype(str) == s_jour) & 
            (st.session_state.planning["Scène"] == s_scene)
        ].sort_values(by="Show")
        
        s_artiste = c_s3.selectbox("Artiste", df_filter["Artiste"].unique())
        
        # 2. BOUTON VERT PDF
        with c_s4:
            pdfs_art = st.session_state.riders_stockage.get(s_artiste, {})
            if pdfs_art:
                pdf_name = st.selectbox("Choisir Fiche", list(pdfs_art.keys()), label_visibility="collapsed")
                b64_pdf = base64.b64encode(pdfs_art[pdf_name]).decode('utf-8')
                # LE BOUTON VERT HTML
                html_btn = f"""
                <a href="data:application/pdf;base64,{b64_pdf}" download="{pdf_name}" target="_blank" style="text-decoration:none;">
                    <div style="background-color:#28a745;color:white;padding:10px;text-align:center;border-radius:5px;font-weight:bold;margin-top:20px;">
                        📄 OUVRIR FICHE TECHNIQUE
                    </div>
                </a>
                """
                st.markdown(html_btn, unsafe_allow_html=True)
            else:
                st.markdown("<div style='margin-top:25px;color:grey;'>Pas de PDF</div>", unsafe_allow_html=True)

        st.divider()

        # 3. SAISIE DU PATCH
        col_input, col_view = st.columns([1, 1])
        
        with col_input:
            st.subheader(f"📥 Saisie : {s_artiste}")
            with st.container(border=True):
                # Formulaire
                cat = st.selectbox("Catégorie", list(st.session_state.bibliotheque.keys()))
                mar = st.selectbox("Marque", list(st.session_state.bibliotheque[cat].keys()))
                mod_list = st.session_state.bibliotheque[cat][mar] + ["AUTRE"]
                mod = st.selectbox("Modèle", mod_list)
                if mod == "AUTRE": mod = st.text_input("Référence exacte")
                
                c_q1, c_q2 = st.columns(2)
                qte = c_q1.number_input("Quantité", 1, 100, 1)
                is_perso = c_q2.checkbox("Fourni Artiste")
                
                if st.button("Ajouter / Mettre à jour", use_container_width=True):
                    # LOGIQUE CUMUL : On vérifie si la ligne existe déjà
                    df_curr = st.session_state.fiches_tech
                    mask = (
                        (df_curr["Groupe"] == s_artiste) &
                        (df_curr["Scène"] == s_scene) &
                        (df_curr["Jour"].astype(str) == str(s_jour)) &
                        (df_curr["Catégorie"] == cat) &
                        (df_curr["Marque"] == mar) &
                        (df_curr["Modèle"] == mod) &
                        (df_curr["Artiste_Apporte"] == is_perso)
                    )
                    
                    if df_curr[mask].any():
                        # Si existe : on ajoute la quantité
                        idx = df_curr[mask].index[0]
                        st.session_state.fiches_tech.at[idx, "Quantité"] += qte
                        st.success(f"Quantité mise à jour (+{qte})")
                    else:
                        # Sinon : nouvelle ligne
                        new_line = pd.DataFrame([{
                            "Scène": s_scene, "Jour": s_jour, "Groupe": s_artiste,
                            "Catégorie": cat, "Marque": mar, "Modèle": mod, 
                            "Quantité": qte, "Artiste_Apporte": is_perso
                        }])
                        st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, new_line], ignore_index=True)
                        st.success("Ajouté !")
                    st.rerun()

            # Liste Patch Artiste
            st.caption("Matériel saisi pour ce groupe :")
            mask_art = (st.session_state.fiches_tech["Groupe"] == s_artiste)
            # Data Editor pour permettre suppression/modif rapide
            edited_patch = st.data_editor(st.session_state.fiches_tech[mask_art], use_container_width=True, num_rows="dynamic", key="patch_editor")
            
            if st.button("Sauvegarder Modifs Tableau"):
                # Mise à jour globale
                st.session_state.fiches_tech = st.session_state.fiches_tech[~mask_art] # On retire l'ancien
                st.session_state.fiches_tech = pd.concat([st.session_state.fiches_tech, edited_patch], ignore_index=True) # On met le nouveau
                st.rerun()

        # 4. TABLEAU DE DROITE : BESOIN JOUR X SCENE X (Calcul N+N+1)
        with col_view:
            st.markdown(f"### 📊 Besoin {s_jour} - {s_scene}")
            st.caption("Calcul : MAX ( Groupe N + Groupe N+1 )")
            
            # Appel de la fonction de calcul
            df_besoin = calculer_besoin_max_scene(st.session_state.fiches_tech, st.session_state.planning, s_scene, s_jour)
            
            if not df_besoin.empty:
                st.dataframe(df_besoin, use_container_width=True, height=500)
            else:
                st.info("Pas encore de matériel validé pour cette journée/scène.")

# ==================== TAB 3 : EXPORTS ====================
with tabs[2]:
    st.title("🖨️ Édition des Rapports")
    st.write("Génération du dossier complet incluant : Planning, Détail par Scène (N+N+1) et Récapitulatif Festival.")
    
    col_exp_1, col_exp_2 = st.columns(2)
    
    with col_exp_1:
        st.info("Ce rapport contient exactement les mêmes données que les tableaux de l'application.")
        if st.button("GÉNÉRER LE DOSSIER PDF COMPLET", type="primary"):
            pdf_bytes = generer_pdf_global()
            st.download_button(
                label="📥 Télécharger Dossier_Technique.pdf",
                data=pdf_bytes,
                file_name=f"Dossier_Tech_{st.session_state.nom_festival}.pdf",
                mime="application/pdf"
            )
            
    with col_exp_2:
        st.write("Sauvegarde Projet (JSON)")
        # Export JSON pour backup
        data_json = {
            "planning": st.session_state.planning.to_json(),
            "fiches": st.session_state.fiches_tech.to_json(),
            "nom": st.session_state.nom_festival
        }
        st.download_button("📥 Sauvegarder Projet (.json)", json.dumps(data_json), "backup_festival.json")
