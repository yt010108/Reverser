ARG CORE_IMAGE=local/reverser-core:0.1
FROM ${CORE_IMAGE}
USER root
RUN python -m venv /opt/angr-venv \
 && /opt/angr-venv/bin/pip install --no-cache-dir --upgrade pip==26.0.1 \
 && /opt/angr-venv/bin/pip install --no-cache-dir angr==9.2.213 unicorn==2.1.2 \
 && chown -R root:root /opt/angr-venv
ENV PATH="/opt/angr-venv/bin:/opt/reverser-venv/bin:${PATH}"
USER analyst
CMD ["bash"]
