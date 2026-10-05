import os
from langchain_core.prompts import PromptTemplate
from huggingface_hub import InferenceClient
from dotenv import load_dotenv
from .retrieval_strategy import RetrievalStrategy

load_dotenv()

MAX_CHARS_PER_DOC = 5000

def format_docs(docs):
    formatted = []
    for doc in docs:
        title    = doc.get('title', 'N/A')
        company  = doc.get('company', 'N/A')
        location = doc.get('location', 'N/A')
        url = doc.get('url', 'N/A')
        # Truncate long descriptions so the total prompt stays within token limits
        content  = doc.get('description', '')[:MAX_CHARS_PER_DOC]
        if len(doc.get('description', '')) > MAX_CHARS_PER_DOC:
            content += "..."
        formatted.append(f"{title} at {company}, {location}: {content}. Source: {url}")
    return "\n\n".join(formatted)

class LLMService:
    def __init__(self, vector_db, strategy: RetrievalStrategy):
        self.model_id = "meta-llama/Llama-3.1-8B-Instruct"
        self.vector_db = vector_db
        self.client = InferenceClient(
            api_key=os.environ["HF_TOKEN"],
        )
        self.strategy = strategy        
        self.prompt = PromptTemplate.from_template("""You are a friendly and helpful job search assistant.

Your goal is to help the user find the best job matches based on the provided context. 

Start your response with a brief, friendly introduction about what you found (or didn't find).

For each relevant job found, provide a concise summary using the following format:

1. **[Job Title]** at **[Company]**
   - **Location**: [Location]
   - **Salary**: [Salary or "Not specified"]
   - **Summary**: [A 3-4 sentence summary of key responsibilities and requirements]
   - **Link**: [URL Source]

Separate each job with a numbered label (1., 2., 3., etc.).

After the list, provide a brief, encouraging closing statement.

If there is no relevant context or job given to you, say something friendly like "I couldn't find any exact matches for that right now, but I'll keep an eye out as more jobs are posted!"

---
CONTEXT:
{context}
---

Answer the question based on the above context: {question}
""")       

    def set_strategy(self, strategy: RetrievalStrategy):
        """Setter function for retrievel strategy"""
        self.strategy = strategy

    def query(self, question: str):
        try:
            docs = self.strategy.retrieve(question, self.vector_db)
            context = format_docs(docs=docs)
            prompt = self.prompt.format(context=context, question=question)

            completion = self.client.chat.completions.create(
                model="meta-llama/Llama-3.1-8B-Instruct",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=2048, # Increased to allow for longer descriptions
            )

            return completion.choices[0].message.content
        except Exception as e:
            print(f"Query error: {e}")
            return f"Error processing query: {str(e)}"
        
    def get_data_count(self):
        return self.vector_db.get_data_count()
    
    def debug_retriever(self, question: str):
        """Debug method to check what the retriever returns"""
        try:
            docs = self.strategy.retrieve(question, self.vector_db)
            print(f"Retriever returned {len(docs)} documents")
            for i, doc in enumerate(docs):
                print(f"  Doc {i}: {doc.get('description', '')[:100]}...")
            return docs
        except Exception as e:
            print(f"Retriever debug error: {e}")
            return []
    
    def debug_chain(self, question: str):
        """Debug each step of the RAG chain separately"""
        print("=" * 50)
        print("STEP 1: Testing Retriever")
        print("=" * 50)
        try:
            retriever = self.vector_db.as_retriever(k=5)
            docs = retriever.invoke(question)
            print(f"✓ Retriever returned {len(docs)} documents")
        except Exception as e:
            print(f"✗ Retriever failed: {e}")
            return
        
        print("\n" + "=" * 50)
        print("STEP 2: Testing format_docs")
        print("=" * 50)
        try:
            context = format_docs(docs)
            print(f"✓ Context formatted ({len(context)} chars):")
            print(context[:300] + "..." if len(context) > 300 else context)
        except Exception as e:
            print(f"✗ format_docs failed: {e}")
            return
        
        print("\n" + "=" * 50)
        print("STEP 3: Testing Prompt")
        print("=" * 50)
        try:
            prompt_value = self.prompt.invoke({"context": context, "question": question})
            print(f"✓ Prompt created:")
            print(str(prompt_value)[:500] + "..." if len(str(prompt_value)) > 500 else prompt_value)
        except Exception as e:
            print(f"✗ Prompt failed: {e}")
            return
        
        print("\n" + "=" * 50)
        print("STEP 4: Testing LLM")
        print("=" * 50)
        
        # Check HF_TOKEN
        hf_token = os.getenv("HF_TOKEN")
        if not hf_token:
            print("✗ HF_TOKEN environment variable is NOT set!")
            return None
        print(f"✓ HF_TOKEN is set (starts with: {hf_token[:10]}...)")
        print(f"  Using model: {self.model_id}")
        
        try:
            llm_response = self.llm.invoke(prompt_value)
            print(f"✓ LLM response type: {type(llm_response)}")
            print(f"✓ LLM response: {llm_response}")
            return llm_response
        except Exception as e:
            print(f"✗ LLM failed: {type(e).__name__}: {e}")
            print("\nPossible fixes:")
            print("  1. Check if HF_TOKEN is valid")
            print("  2. Accept model terms at: https://huggingface.co/meta-llama/Llama-3.2-1B")
            print("  3. Try a different model (e.g., 'mistralai/Mistral-7B-Instruct-v0.2')")
            return None
    


    





