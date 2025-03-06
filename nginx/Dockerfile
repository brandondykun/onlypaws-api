FROM nginx:1.25-alpine

RUN rm /etc/nginx/conf.d/default.conf

USER root

RUN mkdir -p /vol/web/static
RUN mkdir -p /vol/web/media
RUN chmod -R 755 /vol/web

# Only copy the template file
COPY ./templates/nginx.conf.template /etc/nginx/templates/default.conf.template
