FROM python:3.10.6-slim-bullseye as base

ENV NVARCH x86_64

ENV NVIDIA_REQUIRE_CUDA="cuda>=11.7 brand=tesla,driver>=450,driver<451 brand=tesla,driver>=470,driver<471 brand=unknown,driver>=470,driver<471 brand=nvidia,driver>=470,driver<471 brand=nvidiartx,driver>=470,driver<471 brand=quadrortx,driver>=470,driver<471 brand=unknown,driver>=510,driver<511 brand=nvidia,driver>=510,driver<511 brand=nvidiartx,driver>=510,driver<511 brand=quadrortx,driver>=510,driver<511"
ENV NV_CUDA_CUDART_VERSION=11.7.99-1
ENV NV_CUDA_COMPAT_PACKAGE=cuda-compat-11-7
ENV DEBIAN_FRONTEND=nonintercative

LABEL maintainer="NVIDIA CORPORATION <cudatools@nvidia.com>"

RUN apt-get update && apt-get install -y --no-install-recommends \
    gnupg2 curl ca-certificates && \
    curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/${NVARCH}/3bf863cc.pub | apt-key add - && \
    echo "deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/${NVARCH} /" > /etc/apt/sources.list.d/cuda.list && \
    apt-get purge --autoremove -y curl \
    && rm -rf /var/lib/apt/lists/*

ENV CUDA_VERSION 11.7.1

# For libraries in the cuda-compat-* package: https://docs.nvidia.com/cuda/eula/index.html#attachment-a
RUN apt-get update && apt-get install -y --no-install-recommends \
    cuda-cudart-11-7=${NV_CUDA_CUDART_VERSION} \
    ${NV_CUDA_COMPAT_PACKAGE} \
    && ln -s cuda-11.7 /usr/local/cuda && \
    rm -rf /var/lib/apt/lists/*

# Required for nvidia-docker v1
RUN echo "/usr/local/nvidia/lib" >> /etc/ld.so.conf.d/nvidia.conf \
    && echo "/usr/local/nvidia/lib64" >> /etc/ld.so.conf.d/nvidia.conf

ENV PATH /usr/local/nvidia/bin:/usr/local/cuda/bin:${PATH}
ENV LD_LIBRARY_PATH /usr/local/nvidia/lib:/usr/local/nvidia/lib64


# nvidia-container-runtime
#ENV NVIDIA_VISIBLE_DEVICES all
ENV NVIDIA_DRIVER_CAPABILITIES compute,utility


RUN apt-get update && apt-get install -y --no-install-recommends \
    gnupg2 curl ca-certificates && \
    curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/${NVARCH}/3bf863cc.pub | apt-key add - && \
    echo "deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/${NVARCH} /" > /etc/apt/sources.list.d/cuda.list && \
    apt-get purge --autoremove -y curl \
    && rm -rf /var/lib/apt/lists/*


ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    TZ=Europe/Oslo

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 gcc


ARG install_path=/usr/local/share/sd_client
RUN mkdir $install_path
# RUN mkdir $install_path/imaginAIry

ADD requirements.txt $install_path/requirements.txt
#ADD imaginAIry/requirements-dev.txt $install_path/imaginAIry/requirements-dev.txt
#RUN --mount=type=cache,target=/root/.cache/pip python3 -m pip install -r $install_path/requirements.txt --extra-index-url "https://download.pytorch.org/whl/cu113"
RUN --mount=type=cache,target=/root/.cache/pip python3 -m pip install -r $install_path/requirements.txt

#ADD "https://api.github.com/repos/NiclasEriksen/imaginAIry/commits?per_page=1" latest_commit
#ADD imaginAIry $install_path/imaginAIry
ADD logs $install_path/logs
ADD "https://api.github.com/repos/NiclasEriksen/sd_client/commits?per_page=1" latest_commit
ADD client $install_path/client
ADD run_client.py $install_path/run_client.py

#WORKDIR $install_path/imaginAIry
#RUN python3 setup.py install
WORKDIR $install_path


CMD ["python3", "run_client.py"]