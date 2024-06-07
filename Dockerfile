FROM python:3.11
RUN apt update && apt upgrade -y && apt install -y dos2unix youtube-dl libavformat-dev libavcodec-dev libavutil-dev git espeak
#RUN git clone https://github.com/anthwlock/untrunc.git
#WORKDIR /untrunc
#RUN ls -al
#RUN make
#RUN cp -v untrunc /usr/local/bin
#WORKDIR /
#RUN rm -rvf untrunc
RUN mkdir -pv /opt/fazowicz
COPY fazowicz.py /opt/fazowicz/fazowicz.py
COPY oauth.py /opt/fazowicz/oauth.py
COPY requirements.txt /requirements.txt
COPY token /opt/fazowicz/token
COPY images /opt/fazowicz/images
COPY substitutes /opt/fazowicz/substitutes
COPY image_data.json /opt/fazowicz/image_data.json
COPY niedziela.jpg /opt/fazowicz/niedziela.jpg
COPY reference.mp4 /opt/fazowicz/reference.mp4
COPY erekcja.mp4 /opt/fazowicz/erekcja.mp4
COPY randsynth_noalpha.png /opt/fazowicz/randsynth_noalpha.png
COPY maxszwef.png /opt/fazowicz/maxszwef.png
COPY google_credentials.json /opt/fazowicz/google_credentials.json
COPY amqp.json /opt/fazowicz/amqp.json
RUN pip3 install -r /requirements.txt
RUN rm -v /requirements.txt
RUN useradd -d /opt/fazowicz -s /sbin/nologin --system fazowicz
RUN dos2unix /opt/fazowicz/fazowicz.py
RUN dos2unix /opt/fazowicz/oauth.py
RUN chown -R fazowicz:fazowicz /opt/fazowicz
RUN chmod -R 440 /opt/fazowicz/*
RUN chmod -R 550 /opt/fazowicz
RUN chmod 500 /opt/fazowicz/fazowicz.py

WORKDIR /opt/fazowicz
USER fazowicz
ENTRYPOINT [ "./fazowicz.py" ]