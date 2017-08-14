FROM snaproute/labs:device_base

RUN apt-get -y update && \
    apt-get -y install \
      tacacs+ \
      rsyslog \
      ntp \
      dnsmasq \
      snmp snmpd snmptt \
    && \
    apt-get clean all

ADD context/ /local/
WORKDIR /local/

RUN cp -Rf /local/etc/* /etc && \
    mkdir -p /local/log/rsyslog && \
    chmod -R 777 /local/log/rsyslog

ENTRYPOINT ["/local/docker_startup.sh"]
CMD /bin/bash
