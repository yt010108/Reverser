ARG CORE_IMAGE=local/reverser-core:0.1
FROM ${CORE_IMAGE}
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      g++ gcc gcc-multilib gdb gdbserver libc6-dev libc6-dev-i386 libc6-i386 \
      ltrace make strace \
 && rm -rf /var/lib/apt/lists/* \
 && /opt/reverser-venv/bin/pip install --no-cache-dir frida-tools==14.10.4
USER analyst
CMD ["bash"]
