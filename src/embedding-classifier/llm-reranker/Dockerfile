# The second-opinion model server (docs/ARCHITECTURE.md):
# llama.cpp's llama-server on CPU with a pinned GGUF baked in, so production
# never downloads a model at run time
FROM ghcr.io/ggml-org/llama.cpp:server-b11681

# Gemma 4 E4B, Q4_K_M, text only. Another GGUF (Gemma 4 E2B, for example) is a
# build argument change; both values must change together.
ARG MODEL_URL=https://huggingface.co/bartowski/google_gemma-4-E4B-it-GGUF/resolve/029e94146666900b08caf49a3b47b413dfa8ec66/google_gemma-4-E4B-it-Q4_K_M.gguf
ARG MODEL_SHA256=d35a3aa7a6d47de237fd488bb6f7f3efd62908d828f85a63da0ee93acdbefe9f

RUN mkdir -p /models \
    && curl -fsSL --retry 3 -o /models/model.gguf "${MODEL_URL}" \
    && echo "${MODEL_SHA256}  /models/model.gguf" | sha256sum -c - \
    && chmod 0444 /models/model.gguf \
    && useradd --uid 10001 --no-create-home llm

# Two slots of 6,144 tokens: one per classifier service (SECOND_OPINION_SLOT,
# production 0 and testing 1), each holding its build's catalogue, the prompt's
# fixed opening of about 2,400 tokens for 37 agencies. The prompt cache is on
# (the default), so a call reads only the message and its options: about 50
# tokens, 3.3 s typical on a 4-core laptop, against 10-13 s when every call
# carried its own examples. Gemma's sliding-window layers keep the cached
# opening only with a full-size cache. The extra host-memory prompt cache is
# off, so memory stays within the container's limit (3.7 GB measured with both
# slots filled). No thinking: the answer is one forced letter.
# Set LLAMA_ARG_THREADS to the CPU limit in compose.
ENV LLAMA_ARG_MODEL=/models/model.gguf \
    LLAMA_ARG_CTX_SIZE=12288 \
    LLAMA_ARG_N_PARALLEL=2 \
    LLAMA_ARG_SWA_FULL=1 \
    LLAMA_ARG_CACHE_RAM=0 \
    LLAMA_ARG_REASONING=off \
    LLAMA_ARG_HOST=0.0.0.0 \
    LLAMA_ARG_PORT=8080

USER llm
EXPOSE 8080
