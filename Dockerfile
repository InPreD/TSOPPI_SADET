FROM python:3.14.0a2-slim
# install dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gnupg=2.2.40-1.1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean
# copy all resource files and create a dedicated runtime data directory
RUN mkdir -p /inpred/data
COPY resources /inpred/resources
COPY SADET.py /inpred
# initialize the necessary gpg directories
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN echo "GPG init" | gpg -c --passphrase "init" --batch --cipher-algo aes256 -o /inpred/resources/data.init.gpg
RUN rm /inpred/resources/data.init.gpg
# Add SADET.py to PATH
ENV PATH=$PATH:/inpred