FROM python:3.10-slim
LABEL authors="tobias.lindenbauer"

WORKDIR /usr/code/
COPY repository_scraper_requirements_linux.txt .

# Install git and prune unneeded packages
RUN apt-get update && apt-get install -y git \
    && rm -rf /var/lib/apt/lists/*

# Install project dependencies including YSON and YTclient
RUN pip install --no-cache-dir -r repository_scraper_requirements_linux.txt
