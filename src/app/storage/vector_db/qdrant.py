import json
import logging
import os
import uuid
from typing import Any

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from .base import AbstractVectorDB
from .gemma_embedding import GemmaEmbedding

load_dotenv()

class QdrantService(AbstractVectorDB):
    def __init__(
        self,
        url: str = os.getenv("QDRANT_LOCAL_HOST_URL"),
        api_key: str | None = None,
    ):
        self.logger = logging.getLogger(__name__)
        self.embedding_model = GemmaEmbedding()

        self.client = QdrantClient(url=url, api_key=api_key, timeout=60)
        self.logger.info("Using QDRANT local collection")    
        self.logger.info("Connected to QDRANT cloud successfully")
            
        if not self.client.collection_exists('job_collection'):
            self.client.create_collection(
                collection_name='job_collection',
                vectors_config=VectorParams(size=self.embedding_model.dimension, distance=Distance.COSINE) 
            )

    def create_embeddings(self, jobs: list[dict[str, Any]]) -> list[list[float]]:
        jobs_to_embed = [f"""
                    {job.get("title", "")}
                    {job.get("company", "")}
                    {job.get("description", "")}
                    {job.get("location", "")}
                    {job.get("posted_date", "")}
                    {job.get("url", "")}
                    {job.get("category", "")}
                        """.strip() for job in jobs]
                        
        embedding_list = self.embedding_model.embed_documents(jobs_to_embed)
        self.logger.info(f"Generated {len(embedding_list)} embeddings")
        return embedding_list

    def add_jobs(self, jobs: list[dict[str, Any]]) -> list[str]:
        """Process, embed, and add a batch of jobs to Qdrant. Returns list of IDs."""
        if not jobs:
            return []
            
        try:
            embeddings = self.create_embeddings(jobs)
            points = []
            success_ids = []
            for i, (job, vector) in enumerate(zip(jobs, embeddings)):
                # Handle UUID conversion from hex string if possible, else use URL hash or random
                try:
                    point_id = str(uuid.UUID(hex=job["id"][:32])) if "id" in job else str(uuid.uuid4())
                except (ValueError, KeyError):
                    job_url = job.get('url', '')
                    point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(job_url))) if job_url else str(uuid.uuid4())
                
                # Clean payload: remove tracking fields
                payload = json.loads(json.dumps(job, default=str))
                payload.pop('has_embedded', None)
                payload.pop('embedded_at', None)
                
                points.append(PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload
                ))
                if "id" in job:
                    success_ids.append(job["id"])
            
            self.client.upsert(
                collection_name='job_collection',
                wait=True,
                points=points
            )
            self.logger.info(f"Successfully upserted {len(points)} jobs")
            return success_ids
        except Exception as e:
            self.logger.error(f"Error in add_jobs: {e}")
            return []

    def search(self, query: str, n_results: int = 5) -> list[dict[str, Any]]:
        try:
            query_vector = self.embedding_model.embed_query(query)
            results = self.client.query_points(
                collection_name='job_collection',
                query=query_vector,
                limit=n_results
            ).points
            
            return [hit.payload for hit in results]
        except Exception as e:
            self.logger.error(f"Search error: {e}")
            return []

    def get_stats(self) -> dict[str, Any]:
        try:
            collection_info = self.client.get_collection('job_collection')
            return {
                "total_points": collection_info.points_count,
                "status": collection_info.status,
                "vector_size": collection_info.config.params.vectors.size
            }
        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
            return {}
