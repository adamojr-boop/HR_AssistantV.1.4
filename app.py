import os
import shutil
import chainlit as cl
from chainlit.action import Action
from openai import OpenAI
from assistant.database import Database
from assistant.document_processor import DocumentProcessor

db = Database()
processor = DocumentProcessor(db)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@cl.on_chat_start
async def start():
    """Inizializza la chat inviando i pulsanti di gestione del database tramite il System Assistant."""
    actions = [
        Action(
            name="db_stats",
            icon="bar-chart",
            label="Statistiche Database",
            value="db_stats",
            payload={}
        ),
        Action(
            name="db_reindex",
            icon="refresh-cw",
            label="Reindex Database",
            value="db_reindex",
            payload={}
        ),
        Action(
            name="db_clear",
            icon="trash-2",
            label="Svuota completamente il Database",
            value="db_clear",
            payload={}
        ),
    ]
    
    await cl.Message(
        content="**Informazioni del sistema:**", 
        actions=actions,
        author="system_assistant"
    ).send()

@cl.action_callback("db_stats")
async def on_db_stats(action: Action):
    """Mostra le statistiche attuali del database ChromaDB."""
    collection = db.get_collection()
    count = collection.count() if collection else 0
    await cl.Message(
        content=f"📊 **Statistiche Database:** Il database contiene attualmente `{count}` chunk indicizzati.",
        author="system_assistant"
    ).send()

@cl.action_callback("db_reindex")
async def on_db_reindex(action: Action):
    """Sincronizza/reindicizza i file presenti nella cartella resumes."""
    processor.sync_documents()
    await cl.Message(
        content="🔄 **Reindex completato:** La cartella resumes è stata sincronizzata con successo nel database.",
        author="system_assistant"
    ).send()

@cl.action_callback("db_clear")
async def on_db_clear(action: Action):
    """Svuota completamente la collezione del database."""
    db.delete_collection()
    await cl.Message(
        content="🗑️ **Database svuotato:** L'intera collezione è stata eliminata. È necessario lanciare il reindex per ricaricare i file.",
        author="system_assistant"
    ).send()

@cl.on_message
async def main(message: cl.Message):
    """Gestisce i messaggi di chat dell'utente e gli eventuali file allegati."""
    
    if message.elements:
        processing_msg = cl.Message(
            content="📁 Ho rilevato un file allegato. Lo sto elaborando e aggiungendo al database...",
            author="hr_assistant"
        )
        await processing_msg.send()
        
        for file in message.elements:
            try:
                target_path = os.path.join("resumes", file.name)
                os.makedirs("resumes", exist_ok=True)
                shutil.copy(file.path, target_path)
                
                processor.sync_documents()
                
                processing_msg.content = f"✅ Il file **{file.name}** è stato caricato e indicizzato con successo nel database! Ora puoi chiedermi informazioni su questo candidato."
                await processing_msg.update()
                return
            except Exception as e:
                processing_msg.content = f"❌ Errore durante l'elaborazione del file: {str(e)}"
                await processing_msg.update()
                return

    msg = cl.Message(
        content="Sto cercando nei documenti e formulando la risposta...",
        author="hr_assistant"
    )
    await msg.send()

    user_query = message.content
    query_lower = user_query.lower()

    collection = db.get_collection()

    if any(keyword in query_lower for keyword in ["elenco", "quanti profili", "tutti i candidati", "lista"]):
        all_data = collection.get(include=["metadatas", "documents"])
        metadatas = all_data.get("metadatas", [])
        documents = all_data.get("documents", [])
        
        unique_sources = set()
        for meta in metadatas:
            if meta and "source" in meta:
                unique_sources.add(meta["source"])
                
        context = f"Candidati totali nel database: {len(unique_sources)}\nFile registrati: {list(unique_sources)}\n\n" + "\n\n--- DOCUMENTO ---\n\n".join(documents)

        prompt = f"""
Sei un assistente HR. L'utente sta chiedendo una panoramica generale e l'elenco completo dei candidati presenti nel database.

Regole:
1. Elenca TUTTI i candidati trovati nei documenti e nei file di origine.
2. Indica chiaramente il numero totale dei profili disponibili.
3. Per ciascun candidato, fornisci nome, cognome e una sintesi rapida delle sue competenze principali.

Contesto:
{context}

Domanda: {user_query}
"""

    else:
        results = collection.query(
            query_texts=[user_query],
            n_results=12
        )
        retrieved_chunks = results.get("documents", [[]])[0]
        context = "\n\n".join(retrieved_chunks) if retrieved_chunks else "Nessun documento rilevante trovato."

        prompt = f"""
Sei un assistente HR esperto, preciso e rigoroso. 
Analizza il contesto dei curriculum forniti per rispondere alla domanda dell'utente.

REGOLE FONDAMENTALI:
1. Basati ESCLUSIVAMENTE sulle informazioni presenti nel contesto. Non inventare mai candidati, esperienze o competenze che non compaiono nei testi.
2. Estrai sempre il nome e cognome reale del candidato leggendolo dal testo o dal nome del file di origine.
3. Se la risposta non è presente nei documenti o il requisito non è soddisfatto, rispondi chiaramente che non ci sono candidati con quei requisiti nel database.
4. Concentrati sull'accuratezza e sull'estrazione puntuale delle competenze del candidato o dei candidati pertinenti trovati nel contesto.

Struttura la risposta in questo modo:
- **Candidato/i Individuati:** (Nome e Cognome reali, oppure "Nessuno")
- **Competenze Rilevanti / Analisi:** (Elenco puntato delle competenze estratte dai testi coerenti con la domanda)
- **Motivazione:** (Spiegazione chiara del perché il profilo è idoneo o perché non sono presenti risposte)

Contesto (Curriculum):
{context}

Domanda: {user_query}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Sei un assistente HR preciso e professionale."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    answer = response.choices[0].message.content

    msg.content = answer
    msg.author = "hr_assistant"
    await msg.update()