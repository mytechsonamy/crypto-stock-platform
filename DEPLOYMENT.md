# Deployment Guide

This guide covers deploying the Crypto-Stock Platform to production environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Configuration](#environment-configuration)
- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [SSL/TLS Setup](#ssltls-setup)
- [Secrets Management](#secrets-management)
- [Scaling Strategies](#scaling-strategies)
- [Monitoring Setup](#monitoring-setup)
- [Backup Configuration](#backup-configuration)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

**Minimum (Development):**
- 4 CPU cores
- 8 GB RAM
- 50 GB SSD storage
- Docker 24.0+
- Docker Compose 2.20+

**Recommended (Production):**
- 8+ CPU cores
- 16+ GB RAM
- 200+ GB SSD storage
- Kubernetes 1.27+
- Load balancer
- CDN for frontend

### Software Requirements

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- PostgreSQL 16 (via Docker)
- Redis 7 (via Docker)

### External Services

- Binance API account (for crypto data)
- Alpaca API account (for US stock data)
- Yahoo Finance (no account needed)
- SMTP server (for email alerts)
- Cloud storage (AWS S3 or Google Cloud Storage for backups)

## Environment Configuration

### Environment Variables

Create `.env` file with the following variables:

```env
# ============================================
# Database Configuration
# ============================================
DB_HOST=timescaledb
DB_PORT=5432
DB_NAME=crypto_stock
DB_USER=admin
DB_PASSWORD=<STRONG_PASSWORD>

# ============================================
# Redis Configuration
# ============================================
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=<STRONG_PASSWORD>

# ============================================
# Exchange API Keys
# ============================================
# Binance
BINANCE_API_KEY=<YOUR_BINANCE_API_KEY>
BINANCE_API_SECRET=<YOUR_BINANCE_API_SECRET>

# Alpaca
ALPACA_API_KEY=<YOUR_ALPACA_API_KEY>
ALPACA_SECRET_KEY=<YOUR_ALPACA_SECRET_KEY>
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Use https://api.alpaca.markets for live

# Yahoo Finance (no keys needed)

# ============================================
# Authentication
# ============================================
JWT_SECRET=<RANDOM_256_BIT_SECRET>
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60

# ============================================
# API Configuration
# ============================================
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com

# ============================================
# Rate Limiting
# ============================================
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60

# ============================================
# Monitoring
# ============================================
PROMETHEUS_PORT=9090
GRAFANA_PORT=3001
GRAFANA_ADMIN_PASSWORD=<STRONG_PASSWORD>

# ============================================
# Logging
# ============================================
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_ROTATION=daily
LOG_RETENTION_DAYS=30

# ============================================
# Backup Configuration
# ============================================
BACKUP_ENABLED=true
BACKUP_SCHEDULE=0 2 * * *  # Daily at 2 AM
BACKUP_RETENTION_DAYS=7
BACKUP_RETENTION_WEEKS=4
BACKUP_RETENTION_MONTHS=6

# Cloud Storage (Optional)
AWS_ACCESS_KEY_ID=<YOUR_AWS_KEY>
AWS_SECRET_ACCESS_KEY=<YOUR_AWS_SECRET>
AWS_S3_BUCKET=crypto-stock-backups
AWS_REGION=us-east-1

# Or Google Cloud Storage
GCS_PROJECT_ID=<YOUR_PROJECT_ID>
GCS_BUCKET=crypto-stock-backups
GCS_CREDENTIALS_PATH=/path/to/credentials.json

# ============================================
# Email Alerts (Optional)
# ============================================
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=<YOUR_EMAIL>
SMTP_PASSWORD=<YOUR_APP_PASSWORD>
SMTP_FROM=alerts@yourdomain.com

# ============================================
# Slack Alerts (Optional)
# ============================================
SLACK_WEBHOOK_URL=<YOUR_SLACK_WEBHOOK>

# ============================================
# Environment
# ============================================
ENVIRONMENT=production  # development, staging, production
```

### Environment-Specific Configurations

#### Development
```env
ENVIRONMENT=development
LOG_LEVEL=DEBUG
API_WORKERS=1
BACKUP_ENABLED=false
```

#### Staging
```env
ENVIRONMENT=staging
LOG_LEVEL=INFO
API_WORKERS=2
BACKUP_ENABLED=true
BACKUP_RETENTION_DAYS=3
```

#### Production
```env
ENVIRONMENT=production
LOG_LEVEL=WARNING
API_WORKERS=4
BACKUP_ENABLED=true
BACKUP_RETENTION_DAYS=7
```

## Docker Deployment

### Production Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    container_name: crypto-stock-timescaledb
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - timescaledb_data:/var/lib/postgresql/data
      - ./storage/migrations:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: crypto-stock-redis
    command: redis-server /usr/local/etc/redis/redis.conf
    volumes:
      - redis_data:/data
      - ./config/redis.conf:/usr/local/etc/redis/redis.conf
    ports:
      - "6379:6379"
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 1G
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  collector:
    build:
      context: .
      dockerfile: docker/Dockerfile.collector
    container_name: crypto-stock-collector
    env_file: .env
    depends_on:
      timescaledb:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M

  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    container_name: crypto-stock-api
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      timescaledb:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        - VITE_API_URL=https://api.yourdomain.com
        - VITE_WS_URL=wss://api.yourdomain.com
    container_name: crypto-stock-frontend
    ports:
      - "3000:80"
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M

  prometheus:
    image: prom/prometheus:latest
    container_name: crypto-stock-prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=30d'
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 2G

  grafana:
    image: grafana/grafana:latest
    container_name: crypto-stock-grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
      - GF_SERVER_ROOT_URL=https://grafana.yourdomain.com
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
    ports:
      - "3001:3000"
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G

  backup:
    build:
      context: .
      dockerfile: docker/Dockerfile.backup
    container_name: crypto-stock-backup
    env_file: .env
    volumes:
      - ./backups:/backups
      - ./scripts:/scripts
    depends_on:
      - timescaledb
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M

volumes:
  timescaledb_data:
  redis_data:
  prometheus_data:
  grafana_data:

networks:
  default:
    name: crypto-stock-network
```

### Deployment Steps

1. **Prepare Environment:**
```bash
# Clone repository
git clone <repository-url>
cd crypto-stock-platform

# Create .env file
cp .env.example .env
nano .env  # Edit with production values
```

2. **Build Images:**
```bash
docker-compose -f docker-compose.prod.yml build
```

3. **Start Services:**
```bash
docker-compose -f docker-compose.prod.yml up -d
```

4. **Verify Deployment:**
```bash
# Check service status
docker-compose -f docker-compose.prod.yml ps

# Run smoke test
./scripts/smoke_test.sh

# Check logs
docker-compose -f docker-compose.prod.yml logs -f
```

5. **Initialize Database:**
```bash
# Migrations run automatically on first start
# Verify tables exist
docker-compose -f docker-compose.prod.yml exec timescaledb \
  psql -U admin -d crypto_stock -c "\dt"
```

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (1.27+)
- kubectl configured
- Helm 3.0+
- Ingress controller (nginx)
- Cert-manager for SSL

### Kubernetes Manifests

Create `k8s/` directory with the following files:

#### namespace.yaml
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: crypto-stock
```

#### configmap.yaml
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: crypto-stock-config
  namespace: crypto-stock
data:
  DB_HOST: "timescaledb"
  DB_PORT: "5432"
  DB_NAME: "crypto_stock"
  REDIS_HOST: "redis"
  REDIS_PORT: "6379"
  API_HOST: "0.0.0.0"
  API_PORT: "8000"
  LOG_LEVEL: "INFO"
  ENVIRONMENT: "production"
```

#### secrets.yaml
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: crypto-stock-secrets
  namespace: crypto-stock
type: Opaque
stringData:
  DB_PASSWORD: "<BASE64_ENCODED>"
  BINANCE_API_KEY: "<BASE64_ENCODED>"
  BINANCE_API_SECRET: "<BASE64_ENCODED>"
  JWT_SECRET: "<BASE64_ENCODED>"
```

#### timescaledb-deployment.yaml
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: timescaledb
  namespace: crypto-stock
spec:
  serviceName: timescaledb
  replicas: 1
  selector:
    matchLabels:
      app: timescaledb
  template:
    metadata:
      labels:
        app: timescaledb
    spec:
      containers:
      - name: timescaledb
        image: timescale/timescaledb:latest-pg16
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          valueFrom:
            configMapKeyRef:
              name: crypto-stock-config
              key: DB_NAME
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: crypto-stock-secrets
              key: DB_PASSWORD
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 100Gi
```

#### api-deployment.yaml
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: crypto-stock
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
      - name: api
        image: crypto-stock-api:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: crypto-stock-config
        - secretRef:
            name: crypto-stock-secrets
        resources:
          requests:
            memory: "1Gi"
            cpu: "1"
          limits:
            memory: "2Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: api
  namespace: crypto-stock
spec:
  selector:
    app: api
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
```

#### ingress.yaml
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: crypto-stock-ingress
  namespace: crypto-stock
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.yourdomain.com
    - app.yourdomain.com
    secretName: crypto-stock-tls
  rules:
  - host: api.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api
            port:
              number: 8000
  - host: app.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port:
              number: 80
```

### Deploy to Kubernetes

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Create secrets (use sealed-secrets in production)
kubectl apply -f k8s/secrets.yaml

# Create config
kubectl apply -f k8s/configmap.yaml

# Deploy database
kubectl apply -f k8s/timescaledb-deployment.yaml

# Deploy application
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/collector-deployment.yaml
kubectl apply -f k8s/frontend-deployment.yaml

# Deploy ingress
kubectl apply -f k8s/ingress.yaml

# Check status
kubectl get pods -n crypto-stock
kubectl get svc -n crypto-stock
kubectl get ingress -n crypto-stock
```

## SSL/TLS Setup

### Let's Encrypt with Cert-Manager

1. **Install Cert-Manager:**
```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
```

2. **Create ClusterIssuer:**
```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@yourdomain.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
```

3. **Apply:**
```bash
kubectl apply -f letsencrypt-issuer.yaml
```

### Manual SSL Certificate

For Docker Compose deployment:

```bash
# Generate self-signed certificate (development)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/key.pem \
  -out nginx/ssl/cert.pem

# Or use Let's Encrypt with certbot
certbot certonly --standalone -d yourdomain.com
```

## Secrets Management

### Docker Secrets

```bash
# Create secrets
echo "my_db_password" | docker secret create db_password -
echo "my_jwt_secret" | docker secret create jwt_secret -

# Use in docker-compose.yml
services:
  api:
    secrets:
      - db_password
      - jwt_secret

secrets:
  db_password:
    external: true
  jwt_secret:
    external: true
```

### Kubernetes Secrets

```bash
# Create from literal
kubectl create secret generic crypto-stock-secrets \
  --from-literal=DB_PASSWORD=mypassword \
  --from-literal=JWT_SECRET=mysecret \
  -n crypto-stock

# Or use sealed-secrets
kubeseal --format=yaml < secrets.yaml > sealed-secrets.yaml
kubectl apply -f sealed-secrets.yaml
```

### HashiCorp Vault (Recommended for Production)

```bash
# Install Vault
helm repo add hashicorp https://helm.releases.hashicorp.com
helm install vault hashicorp/vault

# Store secrets
vault kv put secret/crypto-stock \
  db_password=mypassword \
  jwt_secret=mysecret

# Use Vault agent injector in pods
```

## Scaling Strategies

### Horizontal Scaling

**Collectors:**
```bash
# Docker Compose
docker-compose -f docker-compose.prod.yml up -d --scale collector=5

# Kubernetes
kubectl scale deployment collector --replicas=5 -n crypto-stock
```

**API Servers:**
```bash
# Docker Compose
docker-compose -f docker-compose.prod.yml up -d --scale api=3

# Kubernetes
kubectl scale deployment api --replicas=3 -n crypto-stock
```

### Vertical Scaling

**Increase Resources:**
```yaml
# docker-compose.prod.yml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
```

### Auto-Scaling (Kubernetes)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
  namespace: crypto-stock
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Monitoring Setup

See [MONITORING.md](MONITORING.md) for detailed monitoring setup.

## Backup Configuration

See [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md) for backup and recovery procedures.

## Troubleshooting

### Common Issues

**1. Database Connection Errors**
```bash
# Check database status
docker-compose ps timescaledb
kubectl get pods -n crypto-stock | grep timescaledb

# Check logs
docker-compose logs timescaledb
kubectl logs -n crypto-stock timescaledb-0

# Test connection
docker-compose exec timescaledb psql -U admin -d crypto_stock
```

**2. High Memory Usage**
```bash
# Check resource usage
docker stats
kubectl top pods -n crypto-stock

# Increase limits in docker-compose.prod.yml or k8s manifests
```

**3. Slow API Response**
```bash
# Check API logs
docker-compose logs api
kubectl logs -n crypto-stock -l app=api

# Check database performance
# Check Redis cache hit rate
# Scale API servers
```

**4. WebSocket Disconnections**
```bash
# Check network connectivity
# Check load balancer timeout settings
# Increase WebSocket timeout
# Check client reconnection logic
```

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# System health
curl http://localhost:8000/api/v1/health

# Prometheus metrics
curl http://localhost:9090/metrics

# Database
docker-compose exec timescaledb pg_isready
```

### Logs

```bash
# View all logs
docker-compose logs -f

# View specific service
docker-compose logs -f api

# Kubernetes
kubectl logs -f -n crypto-stock -l app=api
```

## Production Checklist

- [ ] Set strong passwords for all services
- [ ] Configure SSL/TLS certificates
- [ ] Set up firewall rules
- [ ] Configure backup storage (S3/GCS)
- [ ] Set up monitoring alerts
- [ ] Test disaster recovery procedures
- [ ] Configure log rotation
- [ ] Set resource limits
- [ ] Enable security headers
- [ ] Configure rate limits
- [ ] Set up CDN for frontend
- [ ] Configure DNS records
- [ ] Test load balancing
- [ ] Set up CI/CD pipeline
- [ ] Document runbooks
- [ ] Train operations team

## Support

For deployment issues:
- Check [Troubleshooting](#troubleshooting) section
- Review logs
- Check [GitHub Issues](https://github.com/yourrepo/issues)
- Contact support: support@yourdomain.com
