from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings
from assistant3.config import OPENAI_API_KEY

class SemanticChunkerProcessor:
    @staticmethod
    def chunk_it(text: str) -> list:
        """Divide il testo in modo semantico usando gli embedding di OpenAI."""
        if not text.strip():
            return []
            
        embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
        
        splitter = SemanticChunker(
            embeddings=embeddings,
            breakpoint_threshold_type="percentile"
        )
        
        docs = splitter.create_documents([text])
        return [doc.page_content for doc in docs]