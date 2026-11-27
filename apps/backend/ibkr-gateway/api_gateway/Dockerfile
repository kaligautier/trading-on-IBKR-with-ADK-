FROM eclipse-temurin:21-noble

WORKDIR /app

# Install deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    unzip curl gnupg ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Chromium via Playwright (works on ARM64 and x86_64, no snap)
RUN npx --yes playwright install --with-deps chromium

# Download and unzip client portal gateway
RUN mkdir api_gateway && cd api_gateway && \
    curl -O https://download2.interactivebrokers.com/portal/clientportal.gw.zip && \
    unzip clientportal.gw.zip && rm clientportal.gw.zip

RUN mkdir -p api_gateway/root

COPY conf.yaml api_gateway/root/conf.yaml
COPY run_gateway.sh /app/run_gateway.sh
COPY healthcheck.sh /usr/local/bin/healthcheck.sh
COPY tickler.sh /app/tickler.sh

# Install auto-login server (puppeteer-core, we provide our own Chromium)
COPY auto_login /app/auto_login
RUN cd /app/auto_login && npm install --production

# Write a helper script that finds Playwright's Chromium and exports the path
RUN CHROMIUM_BIN=$(find /root/.cache/ms-playwright -type f -name "chrome" 2>/dev/null | head -1) && \
    echo "#!/bin/bash" > /app/set_chromium.sh && \
    echo "export CHROMIUM_PATH=$CHROMIUM_BIN" >> /app/set_chromium.sh && \
    chmod +x /app/set_chromium.sh && \
    echo "Chromium found at: $CHROMIUM_BIN"

RUN chmod +x /app/run_gateway.sh /usr/local/bin/healthcheck.sh /app/tickler.sh

EXPOSE 5055 5056

ENTRYPOINT ["/app/run_gateway.sh"]
