FROM node:22-alpine AS build
WORKDIR /app
ARG VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
ARG VITE_API_KEY=
ARG VITE_DEFAULT_EMPLOYEE_ID=1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_API_KEY=$VITE_API_KEY
ENV VITE_DEFAULT_EMPLOYEE_ID=$VITE_DEFAULT_EMPLOYEE_ID
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
