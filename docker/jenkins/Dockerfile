FROM mirror.gcr.io/library/python:3.12-slim AS python_runtime
FROM mirror.gcr.io/library/node:20-slim AS node_runtime

FROM mirror.gcr.io/jenkins/jenkins:lts-jdk21

USER root
COPY --from=python_runtime /usr/local /usr/local
COPY --from=node_runtime /usr/local /usr/local

USER jenkins
RUN jenkins-plugin-cli --plugins \
    workflow-aggregator \
    git \
    credentials-binding \
    junit \
    timestamper \
    ws-cleanup
