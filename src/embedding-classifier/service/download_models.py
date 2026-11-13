"""
Download the pinned weights of the given model keys into the Hugging Face
cache. The Dockerfile runs this, so the service never downloads at run time.

    python -m service.download_models multilingual-e5-large-instruct
"""

import sys

from embedding_classifier.encoder import Encoder, get_model


def main(keys: list[str]) -> None:
    for key in keys:
        for part in key.split(","):
            if part.strip():
                Encoder(get_model(part.strip()))


if __name__ == "__main__":
    main(sys.argv[1:])
