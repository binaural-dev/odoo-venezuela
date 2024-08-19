FROM ubuntu:jammy
# ENV LANG C.UTF-8
ENV LANG C.UTF-8

# USER root
USER root

# Install debian packages
RUN set -x ; \
    apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends apt-transport-https build-essential ca-certificates curl ffmpeg file flake8 fonts-freefont-ttf fonts-noto-cjk gawk gnupg gsfonts libldap2-dev libjpeg9-dev libsasl2-dev libxslt1-dev lsb-release npm ocrmypdf sed sudo unzip xfonts-75dpi zip zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Install debian packages
RUN set -x ; \
    apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 python3-dbfread python3-dev python3-gevent python3-pip python3-setuptools python3-wheel python3-markdown python3-mock python3-phonenumbers python3-websocket python3-google-auth libpq-dev \
               python3-asn1crypto python3-jwt publicsuffix python3-xmlsec python3-aiosmtpd \
    && rm -rf /var/lib/apt/lists/*

# Install wkhtml
RUN curl -sSL https://nightly.odoo.com/deb/jammy/wkhtmltox_0.12.5-2.jammy_amd64.deb -o /tmp/wkhtml.deb \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get -y install --no-install-recommends --fix-missing -qq /tmp/wkhtml.deb \
    && rm -rf /var/lib/apt/lists/* \
    && rm /tmp/wkhtml.deb

# Docker 16: Migrated layer
RUN curl -sSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - \
    && echo "deb http://apt.postgresql.org/pub/repos/apt/ `lsb_release -s -c`-pgdg main" > /etc/apt/sources.list.d/pgclient.list \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/*

# Docker 16: Migrated layer
RUN npm install -g rtlcss@3.4.0 es-check@6.0.0 eslint@8.1.0

# Docker 16: Migrated layer
ADD https://raw.githubusercontent.com/brendangregg/FlameGraph/master/flamegraph.pl /usr/local/bin/flamegraph.pl
RUN chmod +rx /usr/local/bin/flamegraph.pl

# Install Odoo
ARG ODOO_VERSION
ARG ODOO_RELEASE
RUN curl -o odoo.deb -sSL http://nightly.odoo.com/16.0/nightly/deb/odoo_16.0.${ODOO_RELEASE}_all.deb \    
    && apt-get update \
    && apt-get -y install --no-install-recommends ./odoo.deb \
    && rm -rf /var/lib/apt/lists/* odoo.deb

# Copy entrypoint script and Odoo configuration file
COPY ./entrypoint.sh /
COPY ./config/odoo.conf /etc/odoo/
COPY ./requirements.txt /etc/odoo/

RUN apt-get update && apt-get install git -y && pip install -r /etc/odoo/requirements.txt

# Set permissions and Mount /var/lib/odoo to allow restoring filestore and /mnt/extra-addons for users addons
RUN chown odoo /etc/odoo/odoo.conf \
    && mkdir -p /mnt/extra-addons \
    && chown -R odoo /mnt/extra-addons

# Directories integra and custom for project
RUN mkdir -p /mnt/integra-addons \
    && chown -R odoo /mnt/integra-addons

RUN mkdir -p /mnt/custom-addons \
    && chown -R odoo /mnt/custom-addons

VOLUME ["/var/lib/odoo", "/mnt/extra-addons", "/mnt/integra-addons", "/mnt/custom-addons"]

# Expose Odoo services
EXPOSE 8069 8071 8072

# Set the default config file
ENV ODOO_RC /etc/odoo/odoo.conf

COPY wait-for-psql.py /usr/local/bin/wait-for-psql.py

# Set default user when running the container
USER odoo

ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
