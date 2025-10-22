import json
from pathlib import Path
from typing import List, Optional

import faiss
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from datasets.fingerprint import Hasher
from llama_index.core import StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core.objects import ObjectIndex
from llama_index.core.settings import Settings
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from llama_index.embeddings.openai import OpenAIEmbedding, OpenAIEmbeddingMode
from llama_index.vector_stores.faiss import FaissVectorStore


def create_embedding_model():
    """Create an OpenAI/AzureOpenAI embedding model."""

    embed_model = OpenAIEmbedding(
        model="text-embedding-3-large",
        mode=OpenAIEmbeddingMode.SIMILARITY_MODE,
        embed_batch_size=200,
    )
    return embed_model


class Retriever:
    def __init__(
        self, docs: List[str], dim: int, save_pardir: Optional[str] = None
    ) -> None:
        """Create a text retriever based on OpenAI retrievers.

        Args:
            docs: retrieval corpus. I.e., list of documents
            dim: dimention of the embedding vector for the given model
            save_pardir: Read/Write index from this directory. If None, create the retrieval index everytime.
        """
        print(f"Corpus size:", len(docs))
        embed_model = create_embedding_model()
        assert dim == 3072 # since we are hard coding the model
        Settings.embed_model = embed_model

        docs = list(sorted(docs))

        hasher = Hasher()
        hasher.update(docs)
        hasher.update(dim)
        hash = hasher.hexdigest()

        save_dir = None
        if save_pardir is not None:
            save_pardir = Path(save_pardir, hash)
            save_dir = save_pardir.joinpath("index_cache")

        if (
            save_dir is not None
            and save_dir.exists()
            and len(list(save_dir.iterdir())) != 0
        ):
            print(f"Loading cached index from {save_dir.as_posix()}")
            vector_store = FaissVectorStore.from_persist_dir(save_dir.as_posix())
            storage_context = StorageContext.from_defaults(
                vector_store=vector_store, persist_dir=save_dir.as_posix()
            )
            vector_index = load_index_from_storage(storage_context=storage_context)

            index = ObjectIndex.from_objects_and_index(docs, index=vector_index)
            retriever = index.as_retriever()
        else:
            print("Creating new retrieval index")
            faiss_index = faiss.IndexFlatL2(dim)

            vector_store = FaissVectorStore(faiss_index=faiss_index)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            index = ObjectIndex.from_objects(
                docs,
                index_cls=VectorStoreIndex,
                storage_context=storage_context,
                show_progress=True,
            )
            if save_dir is not None:
                index.index.storage_context.persist(save_dir.as_posix())
            retriever = index.as_retriever()

            # save the docs just for reference
            doc_dump_path = save_pardir.joinpath("misc/doc_dump.json")
            doc_dump_path.parent.mkdir(exist_ok=True, parents=True)
            with open(doc_dump_path, "w") as f:
                json.dump(docs, f, indent=2)

        self._retriever = retriever

    def retrieve(self, query: str, top_k: int = 5) -> List[str]:
        """Retrieve the similar documents for the given query.

        Args:
            query: target search query
            top_k: number of documents to retrieve

        Returns:
            the list of retrieved documents
        """
        old_topk = self._retriever._retriever.similarity_top_k
        self._retriever._retriever.similarity_top_k = top_k

        results = self._retriever.retrieve(query)

        self._retriever._retriever.similarity_top_k = old_topk
        return results


if __name__ == "__main__":
    obj = Retriever(["one", "two", "three"], 3072)
    res = obj.retrieve("first", 1)
    print(res)
