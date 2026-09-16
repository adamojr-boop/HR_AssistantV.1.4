import chromadb
from pathlib import Path

class Database:
    def __init__(self, collection_name="hr_resumes", persist_directory: str = "./chroma_db"):
        """Inizializza un database ChromaDB persistente su disco per il vero recupero semantico."""
        self.persist_path = Path(persist_directory)
        self.persist_path.mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=str(self.persist_path))
        
        self._collection = self.client.get_or_create_collection(name=collection_name)

    def get_or_create_collection(self, name=None):
        if name and name != self._collection.name:
            return self.client.get_or_create_collection(name=name)
        return self._collection

    def get_collection(self):
        return self._collection