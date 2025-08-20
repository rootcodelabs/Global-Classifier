# DOCKERFILE for Triton Python Inference Server including Python environment setup

FROM nvcr.io/nvidia/tritonserver:25.06-py3

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt