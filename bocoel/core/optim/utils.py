from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from bocoel.core.optim.interfaces import State
from bocoel.corpora import Corpus, Index, SearchResult
from bocoel.models import Evaluator
from bocoel.models import utils as model_utils


class RemainingSteps:
    def __init__(self, count: int) -> None:
        self._count = count

    @property
    def count(self) -> int:
        return self._count

    def step(self) -> None:
        self._count -= 1

    @property
    def done(self) -> bool:
        # This would never be true if renaming steps if < 0 at first.
        return self._count == 0


def check_bounds(corpus: Corpus) -> None:
    bounds = corpus.index.bounds

    if bounds.ndim != 2 or bounds.shape[1] != 2:
        raise ValueError("The bound is not valid")

    lower, upper = bounds.T
    if np.any(lower > upper):
        raise ValueError("lower > upper at some points")


# TODO: Result is a singleton since k = 1. Support k != 1 in the future.
def evaluate_index(
    *, query: NDArray, index: Index, evaluate_fn: Callable[[SearchResult], float]
) -> State:
    result = index.search(query, k=1)
    evaluation = evaluate_fn(result)
    return State(result=result, evaluation=evaluation)


def evaluate_corpus_fn(
    *, corpus: Corpus, evaluator: Evaluator
) -> Callable[[SearchResult], float]:
    def evaluate_fn(result: SearchResult) -> float:
        # Result is a singleton. Only evaluate one query.
        return model_utils.evaluate_on_corpus(
            evaluator=evaluator, corpus=corpus, indices=[result.indices.item()]
        )[0]

    return evaluate_fn