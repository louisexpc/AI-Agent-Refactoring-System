# syntax=docker/dockerfile:1
# Sandbox base image (MVP). One clean container per iteration.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive         TZ=Etc/UTC

RUN apt-get update && apt-get install -y --no-install-recommends         ca-certificates         curl         git         bash         coreutils         build-essential         python3.12         python3.12-venv         python3-pip         && rm -rf /var/lib/apt/lists/*

# Node.js 22
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash -         && apt-get update && apt-get install -y --no-install-recommends nodejs         && rm -rf /var/lib/apt/lists/*

# Go (Ubuntu 24.04 apt - typically 1.22)
RUN apt-get update && apt-get install -y --no-install-recommends golang-go         && rm -rf /var/lib/apt/lists/*

# Java + Maven
RUN apt-get update && apt-get install -y --no-install-recommends         openjdk-21-jdk         maven         && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd -m -u 10001 -s /bin/bash sandbox
USER sandbox

WORKDIR /work
CMD ["bash"]
