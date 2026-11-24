ARG CANDIDATE=reviewer-zippingservice:py313
FROM ${CANDIDATE}
USER root
COPY requirements-test.lock /tmp/requirements-test.lock
RUN python -m pip install --no-cache-dir --no-deps --only-binary :all: --require-hashes -r /tmp/requirements-test.lock \
    && python -m pip check
USER app_user
