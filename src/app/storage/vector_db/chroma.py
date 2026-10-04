from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEndpointEmbeddings
import os
import json
from typing import List, Dict, Any
from langchain_core.documents import Document

from app.models import Job
from .base import AbstractVectorDB

class ChromaService(AbstractVectorDB):
    def __init__(self,  persist_directory: str = "./data/category-db/chroma_db"):
        self.model_id = "BAAI/bge-small-en-v1.5"

        self.embd = HuggingFaceEndpointEmbeddings(
            model=self.model_id,
            huggingfacehub_api_token=os.getenv('HF_TOKEN'))
        
        self.vectorstore = Chroma(
            collection_name="jobs", 
            embedding_function=self.embd, 
            persist_directory=persist_directory)

    def create_embeddings(self, jobs: List[Dict[str, Any]]) -> List[List[float]]:
        """Create embeddings using HuggingFace API."""
        texts = [f"""
                    {job.get("title", "")}
                    {job.get("company", "")}
                    {job.get("description", "")}
                    {job.get("location", "")}
                    {job.get("posted_date", "")}
                    {job.get("url", "")}
                    {job.get("category", "")}
                """.strip() for job in jobs]
        
        embedding_list = self.embd.embed_documents(texts)
        return embedding_list
    
    def add_jobs(self, jobs: List[Dict[str, Any]]) -> List[str]:
        """Add jobs to vector database"""
        try:
            documents = []
            ids = []
            for job in jobs:
                text = f"""
                        {job.get("title", "")}
                        {job.get("company", "")}
                        {job.get("description", "")}
                        {job.get("location", "")}
                        {job.get("posted_date", "")}
                        {job.get("url", "")}
                        {job.get("category", "")}
                        """.strip()
                
                # Clean metadata
                metadata = json.loads(json.dumps(job, default=str))
                metadata.pop('has_embedded', None)
                metadata.pop('embedded_at', None)
                
                document = Document(
                    page_content=text,
                    metadata=metadata
                )
                
                job_id = job.get('id') or job.get('job_id')
                documents.append(document)
                ids.append(str(job_id) if job_id else None)

            # Add to vector database
            self.vectorstore.add_documents(documents, ids=ids)

            return [i for i in ids if i]
        except Exception as e:
            print(f"Error adding jobs: {e}")
            return []
        
    def search(self, query: str, n_results: int=10) -> List[Dict[str, Any]]:
        try:
            results = self.vectorstore.similarity_search(
                query, 
                k=n_results
            )
            return [doc.metadata for doc in results]
        except Exception as e:
            print(f"Search error: {e}")
            return []
        
    def get_stats(self) -> Dict[str, Any]:
        count = self.vectorstore._collection.count()
        return {
            "total_embeddings": count,
            "collection_name": "jobs"
        }
