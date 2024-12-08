FROM python:3.14.0a2

# copy all resource files and create a dedicated runtime data directory
RUN mkdir -p /inpred/data
COPY resources /inpred/resources
COPY SADET.py /inpred
# initialize the necessary gpg directories
RUN echo "GPG init" | gpg -c --passphrase "init" --batch --cipher-algo aes256 -o /inpred/resources/data.init.gpg
RUN rm /inpred/resources/data.init.gpg
