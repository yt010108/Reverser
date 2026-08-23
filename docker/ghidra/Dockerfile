ARG CORE_IMAGE=local/hermes-ctf-reverse-core:0.1
FROM eclipse-temurin:21-jdk-jammy AS java

FROM ${CORE_IMAGE}
ARG GHIDRA_VERSION=12.1.3
ARG GHIDRA_DATE=20260817
USER root
COPY --from=java /opt/java/openjdk /opt/java/openjdk
ENV JAVA_HOME=/opt/java/openjdk
ENV PATH="/opt/java/openjdk/bin:${PATH}"
RUN curl -fsSL "https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_${GHIDRA_VERSION}_build/ghidra_${GHIDRA_VERSION}_PUBLIC_${GHIDRA_DATE}.zip" -o /tmp/ghidra.zip \
 && echo "93a5d11a9ad510622acaaf908c556a7b9b764d338e78a7567f3689bf5081fd54  /tmp/ghidra.zip" | sha256sum -c - \
 && unzip -q /tmp/ghidra.zip -d /opt \
 && mv "/opt/ghidra_${GHIDRA_VERSION}_PUBLIC" /opt/ghidra \
 && ln -s /opt/ghidra/support/analyzeHeadless /usr/local/bin/ghidra-headless \
 && rm /tmp/ghidra.zip
COPY ExportDecompile.java /opt/ghidra_scripts/ExportDecompile.java
ENV GHIDRA_HOME=/opt/ghidra
USER analyst
CMD ["bash"]
