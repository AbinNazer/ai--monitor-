FROM python:3.12-slim

WORKDIR /app

# docker CLI (talks to host daemon via mounted socket) + kubectl
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates procps \
    && curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.3.1.tgz | tar xz --strip-components=1 -C /usr/local/bin docker/docker \
    && curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
    && rm kubectl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "main.py"]
