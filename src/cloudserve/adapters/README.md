# Adapters

Infrastructure implementations of the ports. Must not import application, orchestration or API code.

- `persistence/`: encrypted SQLite ticket store and outbox (`ticket_store.py`), knowledge store (`knowledge_store.py`), Fernet encryption (`encryption.py`).
- `retrieval/`: approved passage index and lexical/hybrid search (`knowledge_index.py`), Chroma + all-MiniLM-L6-v2 dense index and cross-encoder reranker (`dense_index.py`).
- `ml/`: calibrated classifier (`classifier.py`), model registry and drift monitors (`registry.py`).
- `azure/openai_client.py`: Azure OpenAI chat and embeddings with bounded timeouts.
- Channels: the local channel sender lives with the outbox dispatcher; live channel adapters are out of scope.
