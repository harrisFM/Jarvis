FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY pyproject.toml README.md ./
COPY jarvis ./jarvis
COPY agent ./agent
RUN pip install --no-cache-dir .
EXPOSE 8080
VOLUME ["/app/data"]
CMD ["jarvis", "serve"]
