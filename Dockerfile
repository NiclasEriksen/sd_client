FROM nvidia/cuda:11.0.3-base-ubuntu20.04


ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    SD_API_URL="https://ai.posterity.no" \
    SD_TEST_MODE=0 \
    SD_CPU_MODE=0 \
    DEBIAN_FRONTEND=nonintercative \
    TZ=Europe/Oslo

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 git software-properties-common gcc && \
    add-apt-repository -y ppa:deadsnakes/ppa
RUN apt-get update && apt-get install -y python3.10 python3-distutils python3-pip python3-apt


ARG install_path=/usr/local/share/sd_client
RUN mkdir $install_path

WORKDIR $install_path

COPY requirements.txt $install_path
COPY run_client.py $install_path/run_client.py
ADD client $install_path/client
ADD logs $install_path/logs
RUN --mount=type=cache,target=/root/.cache/pip pip3 install -r requirements.txt
COPY . $install_path

CMD ["python3.10", "run_client.py"]