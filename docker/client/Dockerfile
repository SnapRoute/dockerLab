FROM snaproute/labs:device_base

ADD context/ /local/
WORKDIR /local/

RUN cp -Rf /local/etc/* /etc

ENTRYPOINT ["/local/docker_startup.sh"]
CMD /bin/bash
