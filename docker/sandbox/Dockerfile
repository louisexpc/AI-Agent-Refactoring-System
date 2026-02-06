# syntax=docker/dockerfile:1.7
FROM debian:bookworm-slim

ARG DEBIAN_FRONTEND=noninteractive

# ---- Version pins (override at build time if needed) ----
# Node: for React/TS + legacy Node projects
ARG NODE_VERSION=20.11.1
# Go: for Gin backend
ARG GO_VERSION=1.22.10
# Ruby: for legacy Rails MVC project
ARG RUBY_VERSION=3.3.4
# Rust: for Project 1 refactor
ARG RUST_TOOLCHAIN=stable

# ---- User ----
ARG USER=sandbox
ARG UID=1000
ARG GID=1000

# ---- Workspace ----
ENV WORKDIR=/workspace \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# ---- Rust locations (system-wide) ----
ENV RUSTUP_HOME=/opt/rustup \
    CARGO_HOME=/opt/cargo

# ---- Base OS packages (union of P1/P2/P3) ----
# Includes:
# - C/C++ build toolchain for C baseline & native deps
# - Ruby build deps (for ruby-build compiling Ruby + native gems)
# - Java 17 for Gradle/Kotlin (Gradle requires JVM 17+) :contentReference[oaicite:0]{index=0}
# - Postgres client (psql) for Kotlin+Postgres integration tests / debugging
# - SQLite present as lightweight default for Rails if needed
# - mysql client included (client-only) for Rails compatibility if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
      bash ca-certificates curl git \
      build-essential make cmake pkg-config file unzip xz-utils \
      libc6-dev \
      python3 python3-venv python3-pip \
      # Ruby build deps
      libssl-dev zlib1g-dev libreadline-dev libyaml-dev libffi-dev libgdbm-dev libncurses5-dev libjemalloc-dev \
      # DB clients / headers (clients are for runtime tools; -dev headers are for gems needing compilation)
      sqlite3 libsqlite3-dev \
      libpq-dev postgresql-client \
      default-mysql-client \
      tzdata \
    && rm -rf /var/lib/apt/lists/*

# ---- Install Node.js (tarball) + Corepack ----
RUN curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" -o /tmp/node.tar.xz \
    && tar -C /usr/local --strip-components=1 -xJf /tmp/node.tar.xz \
    && rm -f /tmp/node.tar.xz
# Corepack must be explicitly enabled to take effect :contentReference[oaicite:1]{index=1}
RUN corepack enable

# ---- Install Go ----
RUN curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" -o /tmp/go.tgz \
    && rm -rf /usr/local/go \
    && tar -C /usr/local -xzf /tmp/go.tgz \
    && rm -f /tmp/go.tgz

# ---- Install Ruby via ruby-build ----
# ruby-build keeps Ruby pinned and reproducible without relying on distro Ruby packages
RUN git clone --depth 1 https://github.com/rbenv/ruby-build.git /tmp/ruby-build \
    && /tmp/ruby-build/install.sh \
    && ruby-build "${RUBY_VERSION}" /opt/ruby \
    && rm -rf /tmp/ruby-build
RUN /opt/ruby/bin/gem update --system && /opt/ruby/bin/gem install bundler

# ---- Install Rust via rustup ----
# rustup non-interactive install (recommended approach) :contentReference[oaicite:2]{index=2}
RUN curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain ${RUST_TOOLCHAIN} \
    && chmod -R a+rX ${RUSTUP_HOME} ${CARGO_HOME}

# ---- Java 17 ----
# openjdk-17-jdk installed via apt; ensure JAVA_HOME is set for Gradle/Kotlin toolchains
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# ---- PATH ordering (avoid conflicts) ----
# Priority: cargo/rustc -> ruby -> go -> node -> system
ENV PATH=/opt/cargo/bin:/opt/ruby/bin:/usr/local/go/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin \
    GOPATH=/home/${USER}/go \
    CARGO_TERM_COLOR=always \
    BUNDLE_JOBS=4 \
    BUNDLE_RETRY=3 \
    npm_config_fund=false \
    npm_config_audit=false

# ---- Non-root user & workspace ----
RUN groupadd -g ${GID} ${USER} \
    && useradd -m -u ${UID} -g ${GID} -s /bin/bash ${USER} \
    && mkdir -p ${WORKDIR} \
    && chown -R ${USER}:${USER} ${WORKDIR} ${RUSTUP_HOME} ${CARGO_HOME}

WORKDIR ${WORKDIR}
USER ${USER}

CMD ["/bin/bash"]
