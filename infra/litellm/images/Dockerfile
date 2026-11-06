# Both bases are immutable official images; build_images.py supplies the pin.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG RUNTIME_USER=0
USER 0
ADD --chmod=0644 --checksum=sha256:9655943313a94722b7774661c21049070f6bbb0a1516bf02f7c8d5d9201514cd https://files.pythonhosted.org/packages/44/3c/d717024885424591d5376220b5e836c2d5293ce2011523c9de23ff7bf068/pip-25.3-py3-none-any.whl /tmp/security/pip-25.3-py3-none-any.whl
ADD --chmod=0644 --checksum=sha256:301241438c57936ef93f4243a94f2559022268bfcf9b375a9a72eb0f8db8358e https://files.pythonhosted.org/packages/e0/1b/5e74289a1878e666bb4b65fe5805a04cafcac2aa5f519ef1ead67ef91c56/filelock-4.2.4-py3-none-any.whl /tmp/security/filelock-4.2.4-py3-none-any.whl
COPY --chmod=0644 widen_filelock.py /tmp/security/widen_filelock.py
# Backport upstream #49137 before installing the fixed wheel. Pip is used from
# its wheel and never installed in the runtime. Installation has no network.
RUN python /tmp/security/widen_filelock.py \
    && PYTHONPATH=/tmp/security/pip-25.3-py3-none-any.whl python -m pip install --no-index --no-deps --force-reinstall /tmp/security/filelock-4.2.4-py3-none-any.whl \
    && python -c 'import filelock; assert filelock.__version__ == "4.2.4"' \
    && rm -rf /tmp/security
USER ${RUNTIME_USER}
