FROM python:3.14.4-slim-bookworm@sha256:fc74d22ffd0d5ac395a4b7bdda75a4539758862c49ebf3005647084631e63789
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.txt
COPY vision ./vision
ARG BUILD_ARCH
LABEL io.hass.name="Vision" io.hass.description="Read-only Home Assistant observability" \
      io.hass.version="0.3.0-dev.1" io.hass.type="addon" io.hass.arch="${BUILD_ARCH}"
CMD ["python", "-m", "vision"]
