# base image
# FROM node:14.17.0-alpine as build-stage
FROM artifacts.developer.gov.bc.ca/docker-remote/node:14.17.0-alpine as build-stage

# set working directory
WORKDIR /web

ARG NODE_ENV
ARG GENERATE_SOURCEMAP
ARG REACT_APP_KEYCLOAK_CLIENT
ARG REACT_APP_KEYCLOAK_URL_REALM
ARG REACT_APP_KEYCLOAK_URL
ARG FOI_DOCREVIEWER_BASE_API_URL
ARG JFROG_USERNAME
ARG JFROG_PASSWORD


ENV NODE_ENV ${NODE_ENV}
ENV GENERATE_SOURCEMAP false
ENV REACT_APP_KEYCLOAK_CLIENT ${REACT_APP_KEYCLOAK_CLIENT}
ENV REACT_APP_KEYCLOAK_URL_REALM ${REACT_APP_KEYCLOAK_URL_REALM}
ENV REACT_APP_KEYCLOAK_URL ${REACT_APP_KEYCLOAK_URL}
ENV FOI_DOCREVIEWER_BASE_API_URL ${FOI_DOCREVIEWER_BASE_API_URL}

# add `/app/node_modules/.bin` to $PATH
ENV PATH /web/node_modules/.bin:$PATH

RUN apk update && apk upgrade && \
    apk add --no-cache bash git openssh

# install and cache app dependencies

# package-lock.json commented out due to issues with node-canvas on alpine (musl issue)
COPY package-lock.json /web/package-lock.json
COPY package.json /web/package.json


RUN auth="$JFROG_USERNAME:$JFROG_PASSWORD" && authbase64=$(echo -n $auth | base64) && printf "registry=https://artifacts.developer.gov.bc.ca/artifactory/api/npm/npm-remote/\n_auth = $authbase64\nemail = nicholas.kan@gov.bc.ca\nalways-auth = true" >> .npmrc
RUN npm install --unsafe-perm
# delete config file for security
RUN rm -f .npmrc
#RUN npm install react-scripts@3.0.1 -g --silent
COPY . /web
RUN npm run build

FROM artifacts.developer.gov.bc.ca/docker-remote/nginx:1.17 as production-stage
RUN mkdir /app
COPY --from=build-stage /web/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 8080:8080
CMD ["nginx", "-g", "daemon off;"]
