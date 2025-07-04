# Use the official Node.js image as a base
FROM node:22-alpine AS build_frontend

# Install Git - we need it because of FE version hash
RUN apk update && apk add --no-cache git

# Set the working directory in the container
WORKDIR /app

# Copy package*.json
COPY package*.json /app/

# Install dependencies
RUN yarn

# Copy the rest of the application code
COPY . ./

# Build the Vue.js application
ENV NODE_ENV=USI
RUN export GIT_HASH=$(git rev-parse HEAD) && yarn run build:lcp --mode production && mv dist lcp
RUN export GIT_HASH=$(git rev-parse HEAD) && yarn run build:lcphome --mode production && mv dist lcphome
RUN export GIT_HASH=$(git rev-parse HEAD) && yarn run build:catchphrase --mode production && mv dist catchphrase
RUN export GIT_HASH=$(git rev-parse HEAD) && yarn run build:soundscript --mode production && mv dist soundscript
RUN export GIT_HASH=$(git rev-parse HEAD) && yarn run build:videoscope --mode production && mv dist videoscope


# Use the official Nginx image as a base
FROM nginx:alpine

# Copy built Vue.js application from build stage
COPY --from=build_frontend /app/lcp /usr/share/nginx/html/lcp
COPY --from=build_frontend /app/lcphome /usr/share/nginx/html/lcphome
COPY --from=build_frontend /app/catchphrase /usr/share/nginx/html/catchphrase
COPY --from=build_frontend /app/soundscript /usr/share/nginx/html/soundscript
COPY --from=build_frontend /app/videoscope /usr/share/nginx/html/videoscope

# Copy Nginx configuration file
COPY nginx.conf /etc/nginx/nginx.conf

# Expose port 8080
EXPOSE 80 8000 8001 8002 8003

# Start Nginx when the container starts
CMD ["nginx", "-g", "daemon off;"]
