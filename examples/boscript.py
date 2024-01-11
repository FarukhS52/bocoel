import datasets
import fire
from ax.modelbridge import Models
from ax.modelbridge.generation_strategy import GenerationStep
from botorch.acquisition import qMaxValueEntropy
from rich import print
from tqdm import tqdm

from bocoel import (
    AcquisitionFunc,
    AxServiceOptimizer,
    BigBenchMultipleChoice,
    ComposedCorpus,
    DatasetsStorage,
    Distance,
    HnswlibIndex,
    HuggingfaceLM,
    SBertEmbedder,
    WhiteningIndex,
)


def main(
    *,
    ds_path: str = "bigbench",
    ds_name: str = "abstract_narrative_understanding",
    ds_split: str = "default",
    inputs: str = "inputs",
    multiple_choice_targets: str = "multiple_choice_targets",
    multiple_choice_scores: str = "multiple_choice_scores",
    sbert_model: str = "all-mpnet-base-v2",
    llm_model: str = "distilgpt2",
    batch_size: int = 16,
    max_len: int = 512,
    device: str = "cpu",
    sobol_steps: int = 20,
    index_threads: int = 8,
    optimizer_steps: int = 30,
    reduced_dim: int = 16,
) -> None:
    # The corpus part
    dataset_dict = datasets.load_dataset(path=ds_path, name=ds_name)
    dataset = dataset_dict[ds_split]

    dataset_storage = DatasetsStorage(dataset)
    embedder = SBertEmbedder(model_name=sbert_model, device=device)
    corpus = ComposedCorpus.index_storage(
        storage=dataset_storage,
        embedder=embedder,
        key=inputs,
        index_backend=WhiteningIndex,
        distance=Distance.INNER_PRODUCT,
        remains=reduced_dim,
        whitening_backend=HnswlibIndex,
        threads=index_threads,
    )

    # ------------------------
    # The model part

    lm = HuggingfaceLM(
        model_path=llm_model, device=device, batch_size=batch_size, max_len=max_len
    )
    evaluator = BigBenchMultipleChoice(
        inputs=inputs,
        multiple_choice_targets=multiple_choice_targets,
        multiple_choice_scores=multiple_choice_scores,
    )

    # ------------------------
    # The optimizer part.
    steps = [
        GenerationStep(Models.SOBOL, num_trials=sobol_steps),
        # GenerationStep(Models.GPMES, num_trials=-1),
        GenerationStep(
            Models.BOTORCH_MODULAR,
            num_trials=-1,
            model_kwargs={
                "torch_device": device,
                "botorch_acqf_class": qMaxValueEntropy,
            },
        ),
    ]

    optim = AxServiceOptimizer.evaluate_corpus(
        corpus=corpus,
        lm=lm,
        evaluator=evaluator,
        sobol_steps=sobol_steps,
        device=device,
        acqf=AcquisitionFunc.MAX_VALUE_ENTROPY,
    )

    for i in tqdm(range(optimizer_steps)):
        state = optim.step()
        print(f"iteration {i}:", state)


if __name__ == "__main__":
    fire.Fire(main)