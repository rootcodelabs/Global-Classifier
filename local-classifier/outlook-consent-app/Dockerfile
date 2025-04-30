# Stage 1: Build the Next.js app
ARG node_version=node:lts
ARG nginx_version=nginx:1.21.3-alpine

FROM $node_version as image
WORKDIR /usr/src/app
COPY ./package*.json ./

FROM image AS build
RUN npm install --legacy-peer-deps --mode=development
COPY . .
RUN npm run build
VOLUME /usr/buerokratt-classifier

# Stage 2: Serve the app with Nginx
FROM $nginx_version
COPY ./nginx/http-nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /usr/src/app/.next /usr/share/nginx/html
EXPOSE 3003
CMD ["nginx", "-g", "daemon off;"]


