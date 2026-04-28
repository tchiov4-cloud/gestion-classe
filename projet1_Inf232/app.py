# app_classe_tidb.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import pymysql

# Configuration responsive
st.set_page_config(
    page_title="Analyse de classe",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="auto"
)

# CSS pour améliorer le responsive
st.markdown("""
<style>
    @media (max-width: 768px) {
        .stButton button {
            width: 100%;
        }
        .stMetric {
            text-align: center;
        }
    }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("📚 Analyse de performance - Gestion de classe")
st.caption("Version TiDB - Données en ligne")

# ========== CONNEXION TiDB ==========
@st.cache_resource
def init_connection():
    return pymysql.connect(
        host=st.secrets["TIDB_HOST"],
        port=st.secrets["TIDB_PORT"],
        user=st.secrets["TIDB_USER"],
        password=st.secrets["TIDB_PASSWORD"],
        database=st.secrets["TIDB_DATABASE"],
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor
    )

conn = init_connection()

# ========== FONCTIONS BDD ==========
def get_all_notes():
    query = """
        SELECT n.id, n.eleve_id, n.matiere, n.note, n.appreciation, n.type_eval, n.date_note,
               e.nom, e.prenom, e.genre, e.date_naissance
        FROM notes n
        JOIN eleves e ON n.eleve_id = e.id
        ORDER BY n.date_note DESC
    """
    return pd.read_sql(query, conn)

def get_all_eleves():
    return pd.read_sql("SELECT id, nom, prenom, genre, date_naissance FROM eleves ORDER BY nom, prenom", conn)

def get_absences():
    return pd.read_sql("""
        SELECT a.id, a.eleve_id, a.date_absence, a.justifie, a.motif,
               e.nom, e.prenom
        FROM absences a
        JOIN eleves e ON a.eleve_id = e.id
    """, conn)

def add_note(eleve_id, matiere, note, appreciation, type_eval):
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO notes (eleve_id, matiere, note, appreciation, type_eval, date_note) VALUES (%s, %s, %s, %s, %s, %s)",
            (eleve_id, matiere, note, appreciation, type_eval, date.today())
        )
        conn.commit()

def add_eleve(nom, prenom, genre, date_naissance):
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO eleves (nom, prenom, genre, date_naissance) VALUES (%s, %s, %s, %s)",
            (nom.upper(), prenom.capitalize(), genre, date_naissance)
        )
        conn.commit()
        return cursor.lastrowid

def add_absence(eleve_id, date_absence, justifie, motif):
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO absences (eleve_id, date_absence, justifie, motif) VALUES (%s, %s, %s, %s)",
            (eleve_id, date_absence, justifie, motif)
        )
        conn.commit()

# Menu
menu = st.sidebar.radio(
    "📱 Navigation",
    ["🏠 Tableau de bord", "📝 Saisir une note", "👥 Gérer les élèves", 
     "📊 Analyses descriptives", "⚠️ Élèves en difficulté", "📁 Exporter", "🚫 Absences"],
    format_func=lambda x: x.split(" ")[1] if " " in x else x
)

# ========== 1. TABLEAU DE BORD ==========
if menu == "🏠 Tableau de bord":
    st.header("📊 Vue d'ensemble")
    
    df_notes = get_all_notes()
    
    if df_notes.empty:
        st.info("💡 Aucune donnée pour le moment. Commencez par saisir des notes dans le menu 📝")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            nb_eleves = df_notes['eleve_id'].nunique()
            st.metric("👨‍🎓 Élèves", nb_eleves)
        with col2:
            nb_notes = len(df_notes)
            st.metric("📝 Notes saisies", nb_notes)
        with col3:
            moyenne = df_notes['note'].mean()
            st.metric("📊 Moyenne générale", f"{moyenne:.1f}/20")
        
        if not df_notes.empty:
            st.subheader("🏆 Top 3 des meilleurs élèves")
            moyennes_eleves = df_notes.groupby(['nom', 'prenom'])['note'].mean().sort_values(ascending=False).head(3)
            for (nom, prenom), note in moyennes_eleves.items():
                st.success(f"**{prenom} {nom}** : {note:.1f}/20")

# ========== 2. SAISIR UNE NOTE ==========
elif menu == "📝 Saisir une note":
    st.header("➕ Nouvelle note")
    
    df_eleves = get_all_eleves()
    
    if df_eleves.empty:
        st.warning("⚠️ Aucun élève dans la base. Allez d'abord dans 'Gérer les élèves' pour en ajouter.")
    else:
        with st.form("form_note", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                eleve = st.selectbox(
                    "Élève",
                    df_eleves.itertuples(),
                    format_func=lambda x: f"{x.prenom} {x.nom}"
                )
            with col2:
                matiere = st.selectbox("Matière", ["Mathématiques", "Français", "Histoire", "Sciences", "Anglais", "EPS"])
                note = st.number_input("Note /20", 0.0, 20.0, 10.0, step=0.5)
            
            appreciation = st.text_area("Appréciation (optionnel)", placeholder="Bon travail, peut mieux faire...")
            type_eval = st.selectbox("Type d'évaluation", ["Devoir", "Interrogation", "Projet", "Participation"])
            
            submitted = st.form_submit_button("✅ Enregistrer la note", use_container_width=True)
            
            if submitted:
                add_note(eleve.id, matiere, note, appreciation, type_eval)
                st.success(f"✅ Note enregistrée pour {eleve.prenom} {eleve.nom} - {note}/20")
                st.balloons()

# ========== 3. GÉRER LES ÉLÈVES ==========
elif menu == "👥 Gérer les élèves":
    st.header("📋 Liste des élèves")
    
    # Ajout d'élève
    with st.expander("➕ Ajouter un élève"):
        with st.form("add_eleve"):
            col1, col2 = st.columns(2)
            with col1:
                nom = st.text_input("Nom")
                prenom = st.text_input("Prénom")
            with col2:
                genre = st.selectbox("Genre", ["F", "M", "Autre"])
                date_naissance = st.date_input("Date de naissance", date(2010, 1, 1))
            
            if st.form_submit_button("Ajouter l'élève"):
                if nom and prenom:
                    add_eleve(nom, prenom, genre, date_naissance)
                    st.success(f"✅ {prenom} {nom} ajouté")
                    st.rerun()
                else:
                    st.error("Veuillez remplir nom et prénom")
    
    # Affichage des élèves
    df_eleves = get_all_eleves()
    if df_eleves.empty:
        st.warning("Aucun élève pour le moment")
    else:
        st.dataframe(df_eleves, use_container_width=True, hide_index=True)

# ========== 4. ANALYSES DESCRIPTIVES ==========
elif menu == "📊 Analyses descriptives":
    st.header("📈 Statistiques détaillées")
    
    df = get_all_notes()
    
    if df.empty:
        st.warning("Aucune note à analyser")
    else:
        st.subheader("📊 Résumé des notes")
        
        col1, col2 = st.columns(2)
        with col1:
            moyenne = df['note'].mean()
            mediane = df['note'].median()
            st.metric("🎯 Moyenne", f"{moyenne:.2f}/20")
            st.metric("📌 Médiane (note centrale)", f"{mediane:.2f}/20")
        
        with col2:
            min_note = df['note'].min()
            max_note = df['note'].max()
            st.metric("📉 Note la plus basse", f"{min_note:.1f}/20")
            st.metric("📈 Note la plus haute", f"{max_note:.1f}/20")
        
        # Distribution
        st.subheader("📊 Distribution des notes")
        fig = px.histogram(df, x='note', nbins=20, 
                          title="Comment se répartissent les notes ?",
                          labels={'note': 'Note /20', 'count': "Nombre de notes"},
                          color_discrete_sequence=['#2E86AB'])
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # Boxplot par matière
        st.subheader("📊 Comparaison par matière")
        fig = px.box(df, x='matiere', y='note', 
                    title="Performance par matière",
                    labels={'note': 'Note /20', 'matiere': 'Matière'})
        fig.update_layout(height=450)
        st.plotly_chart(fig, use_container_width=True)
        
        # Classement
        st.subheader("🏆 Classement des élèves")
        classement = df.groupby(['nom', 'prenom'])['note'].mean().sort_values(ascending=False).reset_index()
        classement.columns = ['Nom', 'Prénom', 'Moyenne']
        classement['Rang'] = range(1, len(classement)+1)
        
        fig = px.bar(classement.head(10), x='Moyenne', y='Prénom', 
                    orientation='h', title="Top 10 des élèves",
                    text='Moyenne', color='Moyenne',
                    color_continuous_scale='Viridis')
        fig.update_traces(texttemplate='%{text:.1f}', textposition='outside')
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

# ========== 5. ÉLÈVES EN DIFFICULTÉ ==========
elif menu == "⚠️ Élèves en difficulté":
    st.header("🔔 Alertes et suivi personnalisé")
    
    df = get_all_notes()
    
    if df.empty:
        st.info("Aucune donnée pour analyser les difficultés")
    else:
        moyennes = df.groupby(['nom', 'prenom', 'eleve_id'])['note'].mean().reset_index()
        difficulte = moyennes[moyennes['note'] < 10]
        
        if not difficulte.empty:
            st.error(f"🚨 {len(difficulte)} élève(s) nécessitent une attention particulière")
            
            for _, row in difficulte.iterrows():
                with st.container():
                    st.warning(f"**{row['prenom']} {row['nom']}**")
                    st.write(f"📉 Moyenne : {row['note']:.1f}/20")
                    
                    notes_eleve = df[df['eleve_id'] == row['eleve_id']]
                    st.write("Ses matières faibles :")
                    faibles = notes_eleve.groupby('matiere')['note'].mean()
                    faibles = faibles[faibles < 10]
                    if not faibles.empty:
                        for mat, note in faibles.items():
                            st.write(f"- {mat} : {note:.1f}/20")
                    st.divider()
        else:
            st.success("✅ Excellent ! Tous les élèves ont une moyenne ≥ 10/20")

# ========== 6. EXPORTER ==========
elif menu == "📁 Exporter":
    st.header("💾 Sauvegarde des données")
    
    df_notes = get_all_notes()
    df_eleves = get_all_eleves()
    
    if df_notes.empty:
        st.warning("Aucune donnée à exporter")
    else:
        st.write("Aperçu des notes :")
        st.dataframe(df_notes, use_container_width=True)
        
        csv = df_notes.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger toutes les notes (CSV)",
            data=csv,
            file_name="notes_classe.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        if st.button("📄 Générer un rapport texte", use_container_width=True):
            rapport = f"""
            ===== RAPPORT DE CLASSE =====
            Date : {datetime.now().strftime('%d/%m/%Y')}
            
            Effectif : {df_notes['eleve_id'].nunique()} élèves
            Notes saisies : {len(df_notes)}
            
            Statistiques générales :
            - Moyenne : {df_notes['note'].mean():.2f}/20
            - Médiane : {df_notes['note'].median():.2f}/20
            - Écart-type : {df_notes['note'].std():.2f}
            - Minimum : {df_notes['note'].min()}/20
            - Maximum : {df_notes['note'].max()}/20
            
            Meilleure matière : {df_notes.groupby('matiere')['note'].mean().idxmax()} 
            ({df_notes.groupby('matiere')['note'].mean().max():.2f})
            
            Matière la plus difficile : {df_notes.groupby('matiere')['note'].mean().idxmin()} 
            ({df_notes.groupby('matiere')['note'].mean().min():.2f})
            """
            st.text(rapport)
            st.download_button(
                label="📋 Télécharger le rapport",
                data=rapport,
                file_name="rapport_classe.txt",
                use_container_width=True
            )

# ========== 7. ABSENCES ==========
elif menu == "🚫 Absences":
    st.header("📅 Gestion des absences")
    
    df_eleves = get_all_eleves()
    
    if df_eleves.empty:
        st.warning("Aucun élève dans la base")
    else:
        with st.form("form_absence", clear_on_submit=True):
            eleve = st.selectbox(
                "Élève",
                df_eleves.itertuples(),
                format_func=lambda x: f"{x.prenom} {x.nom}"
            )
            date_absence = st.date_input("Date d'absence", date.today())
            justifie = st.checkbox("Absence justifiée")
            motif = st.text_input("Motif (optionnel)")
            
            if st.form_submit_button("Enregistrer l'absence"):
                add_absence(eleve.id, date_absence, justifie, motif)
                st.success(f"✅ Absence enregistrée pour {eleve.prenom} {eleve.nom}")
                st.rerun()
        
        # Affichage des absences
        st.subheader("📋 Historique des absences")
        df_absences = get_absences()
        if not df_absences.empty:
            st.dataframe(df_absences, use_container_width=True)

# Pied de page
st.markdown("---")
st.caption("📱 App adaptée à tous les appareils | Données sur TiDB Cloud")