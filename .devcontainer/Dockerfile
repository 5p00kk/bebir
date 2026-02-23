FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    cmake \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user with uid 1000 to match the typical host user,
# so files created inside the container are editable on the host and in VS Code.
RUN groupadd --gid 1000 vscode \
    && useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home vscode

USER vscode
ENV HOME=/home/vscode
ENV TERM=xterm-256color
ENV PATH="/home/vscode/.local/bin:$PATH"

RUN curl -fsSL https://claude.ai/install.sh | bash

RUN echo 'export PATH="$HOME/.local/bin:$PATH"' >> /home/vscode/.bashrc \
    && echo 'export PS1="\[\e[1;32m\]bebir\[\e[0m\]:\[\e[1;34m\]\w\[\e[0m\]$ "' >> /home/vscode/.bashrc \
    && echo 'alias ls="ls --color=auto"' >> /home/vscode/.bashrc \
    && echo 'alias grep="grep --color=auto"' >> /home/vscode/.bashrc
