# Use the official Node.js image as a base
FROM node:22-alpine as build

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
ENV NODE_ENV=development
RUN export GIT_HASH=$(git rev-parse HEAD) && yarn run build --mode development


# Use the official Nginx image as a base
FROM nginx:alpine

# Copy built Vue.js application from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy Nginx configuration file
COPY nginx.conf /etc/nginx/nginx.conf

# Expose port 8080
EXPOSE 80

# Start Nginx when the container starts
CMD ["nginx", "-g", "daemon off;"]
