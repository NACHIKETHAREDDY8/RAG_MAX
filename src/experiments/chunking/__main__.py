"""Compare chunking strategies: python -m src.experiments.chunking [--offline]."""

import argparse
import sys
from dataclasses import replace
from pathlib import Path

import config
from src.embeddings.cache import CachedEmbeddingProvider
from src.experiments.chunking.runner import ExperimentConfig, run_experiment

DEFAULT_CONFIG = Path("experiments/chunking/config.json")
CACHE_PATH = Path("experiments/chunking/.cache/embeddings.npz")
OFFLINE_DIMENSION = 512


def main(argv: list[str] | None = None) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="use free hashed bag-of-words embeddings instead of OpenAI (no API calls; "
        "results are written under <name>-offline and say nothing about meaning)",
    )
    parser.add_argument(
        "--only", help="comma-separated strategy labels to run (default: all in the config)"
    )
    args = parser.parse_args(argv)

    experiment = ExperimentConfig.from_file(args.config)
    if args.only:
        wanted = set(args.only.split(","))
        experiment = replace(
            experiment,
            strategies=[spec for spec in experiment.strategies if spec.label in wanted],
        )

    if args.offline:
        from src.experiments.chunking.offline import HashingEmbeddingProvider

        experiment = replace(
            experiment, name=f"{experiment.name}-offline", embedding_model="hashing-bag-of-words"
        )
        provider, dimension = HashingEmbeddingProvider(OFFLINE_DIMENSION), OFFLINE_DIMENSION
    else:
        from src.embeddings.provider import OpenAIEmbeddingProvider

        provider = CachedEmbeddingProvider(
            OpenAIEmbeddingProvider(api_key=config.OPENAI_API_KEY, model=experiment.embedding_model),
            namespace=experiment.embedding_model,
            path=CACHE_PATH,
        )
        dimension = config.EMBEDDING_DIMENSION

    run_experiment(experiment, provider, dimension)

    if isinstance(provider, CachedEmbeddingProvider):
        print(f"Embeddings: {provider.misses} new, {provider.hits} from cache")


if __name__ == "__main__":
    main()
