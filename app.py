# --- FONCTION POP-UP DE CONFIRMATION (PLANNING) ---
@st.dialog("Confirmation de suppression")
def confirmer_suppression(index_to_del):
    artiste_nom = st.session_state.planning.iloc[index_to_del]["Artiste"]
    st.warning(f"Êtes-vous sûr de vouloir supprimer le groupe **{artiste_nom}** ?")
    
    col1, col2 = st.columns(2)
    # Cas OUI : On supprime et on force le rafraîchissement
    if col1.button("✅ Oui, supprimer", use_container_width=True):
        st.session_state.planning = st.session_state.planning.drop(index_to_del).reset_index(drop=True)
        if artiste_nom in st.session_state.riders_stockage:
            del st.session_state.riders_stockage[artiste_nom]
        st.rerun()
    
    # Cas NON : On utilise simplement st.rerun() pour recharger le tableau 
    # dans son état initial (avant la demande de suppression), ce qui ferme la pop-up.
    if col2.button("❌ Annuler", use_container_width=True):
        st.rerun()

# --- FONCTION POP-UP DE CONFIRMATION (PATCH MATÉRIEL) ---
@st.dialog("Supprimer cet item ?")
def confirmer_suppression_patch(index_to_del, df_source):
    item = df_source.iloc[index_to_del]
    st.warning(f"Supprimer l'item : **{item['Modèle']}** ?")
    
    col1, col2 = st.columns(2)
    # Cas OUI : On supprime via l'index réel du dataframe source
    if col1.button("✅ Confirmer", use_container_width=True):
        real_idx = df_source.index[index_to_del]
        st.session_state.fiches_tech = st.session_state.fiches_tech.drop(real_idx).reset_index(drop=True)
        st.rerun()
    
    # Cas NON : On recharge pour fermer la pop-up et restaurer l'affichage
    if col2.button("❌ Annuler", use_container_width=True):
        st.rerun()
