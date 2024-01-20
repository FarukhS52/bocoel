import dataclasses as dcls
from typing import Any

from numpy.typing import NDArray
from typing_extensions import Self

from bocoel.corpora.corpora.interfaces import Corpus
from bocoel.corpora.embedders import Embedder
from bocoel.corpora.indices import Index
from bocoel.corpora.storages import Storage


@dcls.dataclass(frozen=True)
class ComposedCorpus(Corpus):
    """
    Simply a collection of components.
    """

    index: Index
    storage: Storage

    @classmethod
    def index_storage(
        cls,
        storage: Storage,
        embedder: Embedder,
        key: str,
        index_backend: type[Index],
        **index_kwargs: Any,
    ) -> Self:
        """
        Creates a corpus from the given storage, embedder, key and index class.

        Parameters
        ----------

        `storage: Storage`
        Storage is used to store the questions / answers / etc.
        Can be viewed as a dataframe of texts.

        `embedder: Embedder`
        Embedder is used to embed the texts into vectors.
        It should provide the number of dims for the index to look into.

        `key: str`
        The key to the column to search over.

        `index_backend: type[Index]`
        The index class to use.
        Creates an index from the embeddings generated by the embedder.

        `**index_kwargs: Any`
        Additional keyword arguments to pass to the index class.
        """

        embeddings = embedder.encode(storage.get(key))
        return cls.index_embeddings(
            embeddings=embeddings, storage=storage, **index_kwargs
        )

    @classmethod
    def index_embeddings(
        cls,
        storage: Storage,
        embeddings: NDArray,
        index_backend: type[Index],
        **index_kwargs: Any,
    ) -> Self:
        index = index_backend.from_embeddings(embeddings, **index_kwargs)
        return cls(index=index, storage=storage)
