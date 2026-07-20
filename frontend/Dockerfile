# MerakiMind AIOps Platform — Frontend Multi-Stage Dockerfile

# Stage 1: Build React App with Vite
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files and install dependencies
COPY package*.json ./
RUN npm ci

# Copy frontend source code and build production bundle
COPY . .
RUN npm run build

# Stage 2: Serve Production Bundle with Nginx
FROM nginx:alpine

# Copy built static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Custom Nginx configuration for React SPA routing & backend API proxy
COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
    listen 80;
    server_name localhost;

    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API calls to backend container
    location /api/ {
        proxy_pass http://backend:8765/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
