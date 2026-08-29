# Home Box image: HA Core plus Python deps so the client site never
# reaches PyPI, wheels.home-assistant.io, or device-vendor clouds.
ARG HA_VERSION=stable
FROM ghcr.io/home-assistant/home-assistant:${HA_VERSION}

COPY requirements.txt /tmp/home-box-requirements.txt
RUN uv pip install --system --no-cache -r /tmp/home-box-requirements.txt \
  && rm -f /tmp/home-box-requirements.txt
