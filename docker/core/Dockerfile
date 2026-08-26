FROM python:3.12-slim-bookworm AS python-builder
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libffi-dev libssl-dev \
 && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/reverser-venv
COPY requirements.txt /tmp/requirements.txt
RUN /opt/reverser-venv/bin/pip install --no-cache-dir --upgrade pip==26.0.1 \
 && /opt/reverser-venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

FROM python:3.12-slim-bookworm
ARG UPX_VERSION=5.2.0
ARG RADARE2_VERSION=6.2.0
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      bash binutils ca-certificates coreutils curl elfutils file jq libmagic1 \
      patchelf p7zip-full procps unzip xxd xz-utils \
 && rm -rf /var/lib/apt/lists/*
COPY --from=python-builder /opt/reverser-venv /opt/reverser-venv
RUN curl -fsSL "https://github.com/radareorg/radare2/releases/download/${RADARE2_VERSION}/radare2_${RADARE2_VERSION}_amd64.deb" -o /tmp/radare2.deb \
 && echo "eb82324e83315887fbee6f5d8632c982c593e056a87180f1bec5ccb06c463aeb  /tmp/radare2.deb" | sha256sum -c - \
 && dpkg -i /tmp/radare2.deb \
 && rm /tmp/radare2.deb \
 && curl -fsSL "https://github.com/upx/upx/releases/download/v${UPX_VERSION}/upx-${UPX_VERSION}-amd64_linux.tar.xz" -o /tmp/upx.tar.xz \
 && echo "3db5d3294707439db97866feab8d75d800f028f48481a40547411824da4288a1  /tmp/upx.tar.xz" | sha256sum -c - \
 && tar -xJf /tmp/upx.tar.xz -C /tmp \
 && install -m 0755 "/tmp/upx-${UPX_VERSION}-amd64_linux/upx" /usr/local/bin/upx \
 && rm -rf /tmp/upx*
COPY triage.py /usr/local/bin/reverser-triage
RUN chmod 0755 /usr/local/bin/reverser-triage \
 && groupadd --gid 10001 analyst \
 && useradd --uid 10001 --gid 10001 --create-home --shell /bin/bash analyst
ENV PATH="/opt/reverser-venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TERM=xterm-256color
USER analyst
WORKDIR /challenge/work
CMD ["bash"]
