# Optional online build path. Actual validation uses the same image with offline inputs.
ARG BASE_IMAGE=ghcr.io/home-assistant/home-assistant@sha256:23f4dfbb69ce76315dbc4de7915504f1c2dcecd7ca2648113a493a385972e133
FROM ${BASE_IMAGE}
# Build inputs are prepared and verified by tools/prepare_build_inputs.py, never copied from a live HA config.
COPY inputs /build/inputs
COPY scripts /build/scripts
ENTRYPOINT ["/bin/sh", "/build/scripts/build-wheel.sh"]
