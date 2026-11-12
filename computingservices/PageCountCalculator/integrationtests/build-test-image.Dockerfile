ARG CANDIDATE=reviewer-pagecountcalculator:py313
FROM ${CANDIDATE}
USER root
COPY requirements-test.txt /tmp/requirements-test.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements-test.txt
USER app_user
