# Home Box image: HA Core + Tuya Local (not cloud Tuya) + Python deps.
# Runtime must not reach PyPI, wheels.home-assistant.io, or device-vendor clouds.
ARG HA_VERSION=stable
FROM ghcr.io/home-assistant/home-assistant:${HA_VERSION}

COPY requirements.txt /tmp/home-box-requirements.txt
RUN uv pip install --system --no-cache -r /tmp/home-box-requirements.txt \
  && rm -f /tmp/home-box-requirements.txt

# Canonical custom components (Tuya Local only — never Core cloud "tuya").
COPY custom_components /usr/share/home-box/custom_components
COPY rootfs/ /
RUN chmod +x /etc/cont-init.d/99-home-box-tuya-local
