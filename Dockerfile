FROM matrixdotorg/synapse:latest

USER root

# Modul ins Image kopieren
COPY discordify /opt/discordify

# Modul installieren
RUN pip install /opt/discordify

USER 991
