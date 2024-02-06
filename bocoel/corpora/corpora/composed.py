import dataclasses as dcls
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from numpy.typing import NDArray
from typing_extensions import Self

from bocoel.corpora.corpora.interfaces import Corpus
from bocoel.corpora.embedders import Embedder
from bocoel.corpora.indices import Index, StatefulIndex
from bocoel.corpora.storages import Storage


@dcls.dataclass(frozen=True)
class ComposedCorpus(Corpus):
    """
    Simply a collection of components.
    """

    index: StatefulIndex
    storage: Storage

    @classmethod
    def index_storage(
        cls,
        storage: Storage,
        embedder: Embedder,
        keys: Sequence[str],
        index_backend: type[Index],
        concat: Callable[[Iterable[Any]], str] = " [SEP] ".join,
        **index_kwargs: Any,
    ) -> Self:
        """
        Creates a corpus from the given storage, embedder, key and index class.

        Parameters
        ----------

        storage: Storage
            Storage is used to store the questions / answers / etc.
            Can be viewed as a dataframe of texts.

        embedder: Embedder
            Embedder is used to embed the texts into vectors.
            It should provide the number of dims for the index to look into.

        *keys: str
            The keys to the column to search over.

        concat: Callable[..., Any] | None = None
            Function to concatenate the columns.

        index_backend: type[Index]
            The index class to use.
            Creates an index from the embeddings generated by the embedder.

        **index_kwargs: Any
            Additional keyword arguments to pass to the index class.
        """

        def transform(mapping: Mapping[str, Sequence[Any]]) -> Sequence[str]:
            data = [mapping[k] for k in keys]
            return [concat(datum) for datum in zip(*data)]

        return cls.index_mapped(
            storage=storage,
            embedder=embedder,
            transform=transform,
            index_backend=index_backend,
            **index_kwargs,
        )

    @classmethod
    def index_mapped(
        cls,
        storage: Storage,
        embedder: Embedder,
        transform: Callable[[Mapping[str, Sequence[Any]]], Sequence[str]],
        index_backend: type[Index],
        **index_kwargs: Any,
    ) -> Self:
        """
        Creates a corpus from the given storage, embedder, key and index class,
        where storage entries would be mapped to strings,
        using the specified batched transform function.
        """

        embeddings = embedder.encode_storage(storage, transform=transform)
        return cls.index_embeddings(
            embeddings=embeddings,
            storage=storage,
            index_backend=index_backend,
            **index_kwargs,
        )

    @classmethod
    def index_embeddings(
        cls,
        storage: Storage,
        embeddings: NDArray,
        index_backend: type[Index],
        **index_kwargs: Any,
    ) -> Self:
        """
        Create the corpus with the given embeddings.
        This can be used to save time by encoding once and caching embeddings.
        """

        index = index_backend(embeddings, **index_kwargs)
        return cls(index=StatefulIndex(index), storage=storage)
