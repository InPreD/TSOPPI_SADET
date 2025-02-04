# make hadolint available
FROM hadolint/hadolint:latest-debian AS hadolint
# build on top of python devcontainer
FROM mcr.microsoft.com/devcontainers/python:0-3.11
# copy the latest hadolint
COPY --from=hadolint /bin/hadolint /bin/hadolint
# install dependencies
RUN apt-get update && \
    export DEBIAN_FRONTEND=noninteractive && \
    apt-get -y install --no-install-recommends --allow-downgrades \
        fish=3.1.2-3+deb11u1 \
        silversearcher-ag=2.2.0+git20200805-1+b1 \
        vim=2:8.2.2434-3+deb11u1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
