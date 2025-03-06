FROM nginx:1.25-alpine

RUN rm /etc/nginx/conf.d/default.conf

USER root

RUN mkdir -p /vol/web/static
RUN mkdir -p /vol/web/media
RUN chmod -R 755 /vol/web

# Copy the template and entrypoint script
COPY ./templates/nginx.conf.template /etc/nginx/templates/
COPY ./docker-entrypoint.sh /docker-entrypoint.sh

# Make the entrypoint script executable
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
