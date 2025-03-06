FROM nginx:1.25-alpine

RUN rm /etc/nginx/conf.d/default.conf

USER root

RUN mkdir -p /vol/web/static
RUN mkdir -p /vol/web/media
RUN chmod -R 755 /vol/web

# Copy the template with the correct name
COPY ./templates/nginx.conf.template /etc/nginx/templates/nginx.conf.template

# Add environment variable for template processing
ENV NGINX_ENVSUBST_TEMPLATE_DIR=/etc/nginx/templates
ENV NGINX_ENVSUBST_OUTPUT_DIR=/etc/nginx/conf.d
