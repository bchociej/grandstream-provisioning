FROM alpine:3.23
RUN apk add --no-cache nginx python3 openssl ca-certificates \
    && mkdir -p /srv/provision /run/nginx
COPY app/provision.py /app/provision.py
COPY container/nginx.conf /etc/nginx/nginx.conf
COPY container/entrypoint.sh /entrypoint.sh
EXPOSE 8080
ENTRYPOINT ["/entrypoint.sh"]
CMD ["serve"]
