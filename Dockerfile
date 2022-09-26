FROM nvidia/cuda:11.0.3-base-ubuntu20.04

RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 git nvidia-smi python3 python3-setuptools

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    SD_API_URL="https://ai.posterity.no" \
    SD_TEST_MODE=0 \
    SD_CPU_MODE=0

ARG install_path=/usr/local/share/sd_client
RUN mkdir $install_path
# RUN mkdir /root/.cache/huggingface
#VOLUME sd_client
#VOLUME models

#/root/.cache/huggingface

WORKDIR $install_path

COPY requirements.txt $install_path
COPY run_client.py $install_path/run_client.py
ADD client $install_path/client
ADD logs $install_path/logs
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt
COPY . $install_path

CMD ["python3", "run_client.py"]