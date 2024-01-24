from collections.abc import Mapping, Sequence
from numbers import Number
from typing import Any

import structlog
from numpy.typing import NDArray

from bocoel.common import StrEnum
from bocoel.models.adaptors import utils
from bocoel.models.lms import LanguageModel
from bocoel.models.scores import MultiChoiceAccuracy, OneHotChoiceAccuracy, Score

from .interfaces import BigBenchAdaptor

LOGGER = structlog.get_logger()


class BigBenchChoiceType(StrEnum):
    SUM_OF_SCORES = "SUM_OF_SCORES"
    LIST_OF_ANSWERS = "LIST_OF_ANSWERS"

    @property
    def score(self) -> Score:
        match self:
            case BigBenchChoiceType.SUM_OF_SCORES:
                return OneHotChoiceAccuracy()
            case BigBenchChoiceType.LIST_OF_ANSWERS:
                return MultiChoiceAccuracy()


class BigBenchMultipleChoice(BigBenchAdaptor):
    def __init__(
        self,
        inputs: str = "inputs",
        multiple_choice_targets: str = "multiple_choice_targets",
        multiple_choice_scores: str = "multiple_choice_scores",
        choice_type: str | BigBenchChoiceType = BigBenchChoiceType.SUM_OF_SCORES,
    ) -> None:
        self._inputs = inputs
        self._multiple_choice_targets = multiple_choice_targets
        self._multiple_choice_scores = multiple_choice_scores

        self._score_fn = BigBenchChoiceType.lookup(choice_type).score

    def evaluate(
        self, data: Mapping[str, Any], lm: LanguageModel
    ) -> Sequence[float] | NDArray:
        # Get data.
        inputs = data[self._inputs]
        multiple_choice_targets = data[self._multiple_choice_targets]
        multiple_choice_scores = data[self._multiple_choice_scores]

        LOGGER.debug(
            "Evaluating",
            inputs=inputs,
            multiple_choice_targets=multiple_choice_targets,
            multiple_choice_scores=multiple_choice_scores,
        )

        # Check data.
        if not all(isinstance(ipt, str) for ipt in inputs):
            raise ValueError("Inputs must be strings.")

        if not all(utils.list_of(mct, str) for mct in multiple_choice_targets):
            raise ValueError("Multiple choice targets must be sequences.")

        if not all(utils.list_of(mcs, Number) for mcs in multiple_choice_scores):
            raise ValueError("Multiple choice scores must be floats.")

        return self._evaluate_batch(
            inputs=inputs,
            multiple_choice_targets=multiple_choice_targets,
            multiple_choice_scores=multiple_choice_scores,
            lm=lm,
        )

    def _evaluate_batch(
        self,
        inputs: Sequence[str],
        multiple_choice_targets: Sequence[Sequence[str]],
        multiple_choice_scores: Sequence[Sequence[float]],
        lm: LanguageModel,
    ) -> Sequence[float] | NDArray:
        prompts = [
            self.numeric_choices(question=q, choices=c)
            for q, c in zip(inputs, multiple_choice_targets)
        ]

        # Get the maximum number of choices.
        # Usually every question should have the same number of choices (5).
        max_choices = max(len(mcs) for mcs in multiple_choice_scores)
        min_choices = min(len(mcs) for mcs in multiple_choice_scores)

        if max_choices == 0:
            raise ValueError(
                "Multiple choice scores must not be empty. "
                f"Got {multiple_choice_scores}"
            )

        if max_choices != min_choices:
            raise ValueError(
                "Batched multiple choice scores only supports the same number of choices. "
                f"Got number of choices from {min_choices} to {max_choices}."
            )

        tokens = [str(i) for i in range(1, max_choices + 1)]
        encoded_tokens = lm.encode_tokens(tokens)

        # Logits has the shape [batch_size, vocab_size]
        # because lm.logits has the shape [batch_size, seq_len, vocab_size]
        logits = lm.logits(prompts)[:, -1, :]

        # Selected has shape [batch_size, num_choices].
        selected = logits[:, encoded_tokens]

        # Chosen has shape [batch_size].
        # Although choices start from 1, chosen is the index of the choice.
        chosen = selected.argmax(axis=-1)

        LOGGER.debug("Generated prompts", chosen=chosen)

        return [
            self._score_fn(target=g, references=s)
            for g, s in zip(chosen, multiple_choice_scores)
        ]

    @staticmethod
    def numeric_choices(question: str, choices: Sequence[str]) -> str:
        """
        Convert a multiple choice question into a numeric choice question.
        Returns a tuple of generated prompt and list of valid choices.
        """

        return (
            f"{question}\nSelect from one of the following (answer in number):\n"
            + "\n".join(f"{i}) {choice}" for i, choice in enumerate(choices, 1))
        )