from .retrieval_strategy import RetrievalStrategy
from huggingface_hub import InferenceClient
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
import os
from langchain_core.load import dumps, loads
import ast

class RAGFusionStrategy(RetrievalStrategy):
    def __init__(self):
        self.model_id = "meta-llama/Llama-3.1-8B-Instruct"
        self.client = InferenceClient(
            api_key=os.environ["HF_TOKEN"],
        )
        template = "You are a helpful assistant that generates multiple search queries in multiple perspectives based on input query to retrieve relevant documents from vector database \n Rules: \n - Output ONLY a Python list of 5 strings. \n - Do NOT explain. \n - Do not add headings and markdown. \n Generate exactly 5 search queries related to: {question}" 
        self.rag_fusion_prompt = PromptTemplate.from_template(template)

    def reciprocal_rank_fusion(self, results: list[list], k=60):
        fused_scores = {}

        for docs in results:
            for rank, doc in enumerate(docs):
                doc = dumps(doc) # convert to JSON string
                if doc not in fused_scores:
                    fused_scores[doc] = 0
                fused_scores[doc] += 1 / (rank + k)
        
        reranked_results = [
            (doc, score) for doc, score in sorted(fused_scores.items(), key=lambda x: x[1], reverse=True) 
        ]

        return [loads(doc) for doc, score in reranked_results] # convert back to LangChain Document objects
            

    def retrieve(self, query: str, vector_db, k: int = 5):

        # generated_queries = self.rag_fusion_prompt | self.client | StrOutputParser() | (lambda x: x.split("\n"))
        # retrieval_chain = generated_queries | retriever.map() | self.reciprocal_rank_fusion()
        # docs = retrieval_chain.invoke({"question": query})

        print("Run Fusion retrieval")
        def gen_queries(prompt_value):
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": "user", "content": prompt_value.to_string()}],
                max_tokens=200
            )
            return response.choices[0].message.content

        def parse_queries(text):
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
        
        queries = query_chain.invoke({"question": query})
        
        if not queries:
            queries = [query]
        
        print("Fusion query:", queries)
        all_docs = [vector_db.search(query) for query in queries]
        
        fused_docs = self.reciprocal_rank_fusion(all_docs)
        return fused_docs[:k]


    def get_name(self):
        return "RAG Fusion"

    
    