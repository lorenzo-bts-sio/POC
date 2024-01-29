FROM alpine:latest

RUN apk update && apk add openssh && ssh-keygen -A  &&  apk add python3 py3-pip && pip3 install watchdog prometheus_client --break-system-packages
COPY sshd_config /etc/ssh/sshd_config
COPY exporter.py /exporter.py
COPY entrypoint.sh /entrypoint.sh
RUN mkdir -p /sftp/data && chmod +x /entrypoint.sh && chmod +x /exporter.py

EXPOSE 22 8000

CMD ["/entrypoint.sh"]
