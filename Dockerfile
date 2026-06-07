FROM alpine:3.21

# 检测架构并安装对应版本的 mihomo
ARG TARGETARCH
ENV MIHOMO_VER=v1.19.27

RUN set -ex; \
    case "${TARGETARCH}" in \
      arm64)   ARCH=arm64  ;; \
      amd64)   ARCH=amd64  ;; \
      arm/v7)  ARCH=armv7l ;; \
      arm/v6)  ARCH=armv6  ;; \
      *)       echo "Unsupported arch: ${TARGETARCH}"; exit 1 ;; \
    esac; \
    MIHOMO_URL="https://github.com/MetaCubeX/mihomo/releases/download/${MIHOMO_VER}/mihomo-linux-${ARCH}-${MIHOMO_VER}.gz"; \
    echo "Downloading mihomo for ${ARCH}: ${MIHOMO_URL}"; \
    wget -q -O /tmp/mihomo.gz "$MIHOMO_URL" || { echo "Download failed"; exit 1; }; \
    gunzip /tmp/mihomo.gz; \
    install -m 755 /tmp/mihomo /usr/local/bin/mihomo; \
    rm -f /tmp/mihomo.gz

RUN apk add --no-cache \
      curl \
      python3 \
      py3-pip \
      py3-yaml \
      ca-certificates \
      tzdata \
      dcron \
      bash; \
    pip3 install --no-cache-dir requests --break-system-packages 2>/dev/null || true; \
    ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime

WORKDIR /etc/mihomo

# 配置文件
COPY config.example.yaml /etc/mihomo/config.yaml.template
COPY update-sub.sh /etc/mihomo/update-sub.sh
COPY entrypoint.sh /entrypoint.sh
COPY dashboard/ /etc/mihomo/dashboard/

RUN chmod +x /etc/mihomo/update-sub.sh /entrypoint.sh

# 暴露端口: 7890(代理) 9090(API+面板)
EXPOSE 7890 9090

ENTRYPOINT ["/entrypoint.sh"]
