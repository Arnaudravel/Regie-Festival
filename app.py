# --- FONCTIONS POP-UP DE CONFIRMATION (CORRIGÉES) ---

@st.dialog("Confirmer la suppression")
def confirmer_suppression(index_to_del):
    artiste_nom = st.session_state.planning.iloc[index_to_del]["Artiste"]
    st.write(f"Voulez-vous vraiment supprimer le groupe : **{artiste_nom}** ?")
    
    # Si on clique sur le bouton, on applique la suppression physiquement
    if st.button("✅ OUI, Supprimer l'artiste", use_container_width=True, type="primary"):
        st.session_state.planning = st.session_state.planning.drop(index_to_del).reset_index(drop=True)
        if artiste_nom in st.session_state.riders_stockage:
            del st.session_state.riders_stockage[artiste_nom]
        st.rerun()
    
    # IMPORTANT : Si l'utilisateur sort de la pop-up sans cliquer sur le bouton ci-dessus, 
    # au prochain tour de boucle, le script va détecter que "deleted_rows" est toujours plein 
    # mais que rien n'a été fait. On ne fait rien ici, le "st.rerun()" de l'annulation 
    # est géré par la logique du tableau ci-dessous.

# --- LOGIQUE DANS L'ONGLET 1 ---
# Remplacez la partie "Planning Global" par celle-ci :

    st.subheader("📋 Planning Global")
    if not st.session_state.planning.empty:
        df_visu = st.session_state.planning.copy()
        df_visu.insert(0, "Rider", df_visu["Artiste"].apply(lambda x: "✅" if st.session_state.riders_stockage.get(x) else "❌"))
        
        # Le data_editor
        ed_plan = st.data_editor(df_visu, use_container_width=True, num_rows="dynamic", key="main_editor")
        
        # GESTION DE LA SUPPRESSION AVEC ANNULATION SI FERMETURE
        if st.session_state.main_editor["deleted_rows"]:
            confirmer_suppression(st.session_state.main_editor["deleted_rows"][0])
            # Si on arrive ici, c'est que la pop-up est ouverte ou a été fermée sans clic.
            # Pour annuler l'effet visuel de suppression de Streamlit, on force un rerun
            # qui va recharger st.session_state.planning (où la ligne existe toujours).
            if st.button("Cliquer ici pour rafraîchir le tableau si annulation"):
                st.rerun()

# --- LOGIQUE DANS L'ONGLET 2 ---
# Appliquez la même logique pour le patch :

@st.dialog("Supprimer cet item")
def confirmer_suppression_patch(index_to_del, df_source):
    item = df_source.iloc[index_to_del]
    st.write(f"Retirer l'item : **{item['Modèle']}** du patch ?")
    
    if st.button("✅ OUI, Supprimer la ligne", use_container_width=True, type="primary"):
        real_idx = df_source.index[index_to_del]
        st.session_state.fiches_tech = st.session_state.fiches_tech.drop(real_idx).reset_index(drop=True)
        st.rerun()
