FROM nginx:1.27.3-alpine

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d 

USER root

RUN mkdir -p /vol/web/static
RUN mkdir -p /vol/web/media
RUN chmod -R 755 /vol/web
