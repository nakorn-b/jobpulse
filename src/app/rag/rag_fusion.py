import ast
import json
import os
import re

import httpx
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda

from .retrieval_strategy import RetrievalStrategy


class RAGFusionStrategy(RetrievalStrategy):
    def __init__(self):
        self.model_id = "nvidia/nemotron-3.5-lightning:free"
        template = """You generate search queries for a vector database of job postings
(each posting has a title, company, location, description and category).

Rewrite the user's request into 4 alternative queries that would match relevant job postings,
e.g. using synonyms for the job title, related skills, or seniority levels.
Do not ask about salaries, interviews, or career advice.

Output ONLY a Python list of strings, no markdown, no explanation.

User request: {question}"""
        self.rag_fusion_prompt = PromptTemplate.from_template(template)

    def reciprocal_rank_fusion(self, results: list[list], k=60):
        fused_scores = {}

        for docs in results:
            for rank, doc in enumerate(docs):
                doc = json.dumps(doc, sort_keys=True) # hashable key for dedup across queries
                if doc not in fused_scores:
                    fused_scores[doc] = 0
                fused_scores[doc] += 1 / (rank + k)
        
        reranked_results = [
            (doc, score) for doc, score in sorted(fused_scores.items(), key=lambda x: x[1], reverse=True) 
        ]

        return [json.loads(doc) for doc, score in reranked_results]
            

    def retrieve(self, query: str, vector_db, k: int = 5):

        # generated_queries = self.rag_fusion_prompt | self.client | StrOutputParser() | (lambda x: x.split("\n"))
        # retrieval_chain = generated_queries | retriever.map() | self.reciprocal_rank_fusion()
        # docs = retrieval_chain.invoke({"question": query})

        print("Run Fusion retrieval")
        def gen_queries(prompt_value):
            response = httpx.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
                json={
                    "model": self.model_id,
                    "messages": [{"role": "user", "content": prompt_value.to_string()}],
                },
                # Generation is slow on free models; httpx's 5s default is too short
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()

            return data['choices'][0]['message']['content']

        def parse_queries(text):
            # Drop markdown code fences (```python ... ```) the model may add despite the prompt
            text = re.sub(r"^```\w*\s*|\s*```$", "", text.strip())
            try:
                parsed = ast.literal_eval(text.strip())
                if isinstance(parsed, list):
                    return [str(q).strip() for q in parsed if str(q).strip()]
            except (ValueError, SyntaxError):
                pass
            return [q.strip() for q in text.split("\n") if q.strip()]
            
        query_chain = (
            self.rag_fusion_prompt 
            | RunnableLambda(gen_queries) # Call LLM to create queries
            | StrOutputParser() 
            | RunnableLambda(parse_queries)
            )
        
        # Always search the user's own query too, so results stay anchored to what they asked
        queries = [query] + query_chain.invoke({"question": query})

        print("Fusion query:", queries)
        all_docs = [vector_db.search(q) for q in queries]
        
        fused_docs = self.reciprocal_rank_fusion(all_docs)
        return fused_docs[:k]


    def get_name(self):
        return "RAG Fusion"