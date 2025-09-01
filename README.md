# FreeRADIUS + MikroTik API Service (Dockerized)

A **production-ready, self-contained RADIUS service** for ISPs that integrates **FreeRADIUS** with **MikroTik RouterOS**. It handles **PPPoE authentication, accounting, session control, IP pool assignment, and package enforcement**, all inside a **Docker-based deployment**.

---

## 🚀 Features

### FreeRADIUS Core
- PPPoE authentication (PAP / CHAP / MSCHAP)
- Accounting (start, interim, stop) with session tracking
- IP pool assignment via **Framed-IP-Address** or **Framed-Pool**
- Bandwidth enforcement via **Mikrotik-Rate-Limit**

### MikroTik API Service
- REST/GraphQL API to manage users, packages, and sessions
- Supports **resellers** and **package overrides**
- Disconnect users or change rate limits dynamically

### Optimizations for Production Use
- **Partitioned accounting tables** for scale
- **Ghost session cleanup** and reconciliation
- **CoA/PoD** (Change of Authorization / Packet of Disconnect) support for MikroTik disconnects

### Docker Deployment
- `freeradius` – Authentication & accounting
- `api-service` – FastAPI-based MikroTik integration
- `db` – MySQL with partitioning
- `redis` – Online sessions cache

---

## 🏃 Quick Start

1. **Clone and setup:**
   ```bash
   cd radius-service
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Deploy with Docker Compose:**
   ```bash
   docker compose up -d
   ```

4. **Check service status:**
   ```bash
   docker compose ps
   curl http://localhost:8000/health
   ```

---

## 📸 Screenshots

### API Dashboard
![API Dashboard](screenshots/api-dashboard-1.png)
*FastAPI management interface showing user management and service status*

### Swagger Documentation  
![Swagger Docs](screenshots/api-dashboard-2.png)
*Interactive API documentation at http://localhost:8000/docs*

### Online Sessions View
![Online Sessions](screenshots/api-dashboard-3.png)
*Real-time view of active RADIUS sessions*



---

## 🌐 Services

- **API Service**: http://localhost:8000 (FastAPI management interface)
- **RADIUS Server**: 
  - Authentication: UDP 1812
  - Accounting: UDP 1813  
  - CoA/Disconnect: UDP 3799
- **MySQL Database**: localhost:3306

---

## 📖 API Overview

The API service is built with **FastAPI** and exposes both **REST** and **GraphQL** interfaces.

### Example Endpoints
- `POST /user` → Create PPPoE user
- `GET /user/{username}` → Fetch user details
- `POST /disconnect/{username}` → Disconnect via CoA
- `GET /online` → List online sessions
- `POST /package` → Create or update bandwidth packages

Authentication example:
```bash
curl -H "Authorization: Bearer <API_KEY>" http://localhost:8000/online
```

---

## 📋 API Documentation

Once deployed, visit http://localhost:8000/docs for interactive API documentation.

### Authentication

All API endpoints require Bearer token authentication:
```bash
curl -H "Authorization: Bearer your-secret-bearer-token-here" \
     http://localhost:8000/
```

### Key Endpoints

- `POST /user` - Create PPPoE user
- `DELETE /user/{username}` - Delete user  
- `GET /online` - List online sessions
- `POST /package` - Create service package
- `GET /acct/{username}/10/0` - User accounting records
- `POST /disconnect/{username}` - Disconnect user session
- `POST /coa/{username}` - Change of Authorization

---

## ⚙️ Configuration

### Environment Variables

Set in `.env` file:
- `API_KEY` - Bearer token for API authentication
- `DB_HOST`, `DB_USER`, `DB_PASS` - MySQL connection
- `POSTGRES_PASSWORD` - MySQL root password
- `REDIS_URL` - Redis connection string
- `MIKROTIK_API_HOST`, `MIKROTIK_API_USER`, `MIKROTIK_API_PASS` - MikroTik RouterOS API

### FreeRADIUS Clients

Edit `freeradius/clients.conf` to add your NAS devices:
```
client pppoe-server {
    ipaddr = 192.168.1.1
    secret = verysecretpassword
    nas_type = mikrotik
    coa_server = yes
}
```

### MikroTik Configuration

Configure your MikroTik router for RADIUS authentication:
```
/radius
add service=ppp address=<radius-server-ip> secret=verysecretpassword
/ppp profile
set *0 use-compression=no use-encryption=no use-mpls=no use-upnp=no \
    local-address=192.168.100.1 remote-address=dhcp-pool \
    change-tcp-mss=yes use-radius=yes
```

---

## 🧪 Testing

### Create a test user:
```bash
curl -X POST "http://localhost:8000/user" \
  -H "Authorization: Bearer your-secret-bearer-token-here" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "passwd": "testpass",
    "expdate": "2025-12-31",
    "package": "basic_package",
    "ip_address": "192.168.100.10",
    "rate_limit": "10M/10M"
  }'
```

### Test RADIUS authentication:
```bash
echo "User-Name=testuser,User-Password=testpass" | \
radclient localhost:1812 auth testing123
```

### Test CoA/Disconnect:
```bash
curl -X POST "http://localhost:8000/disconnect/testuser" \
  -H "Authorization: Bearer your-secret-bearer-token-here"
```

---

## 🔧 Troubleshooting

### View logs:
```bash
docker compose logs -f api-service
docker compose logs -f freeradius-server
docker compose logs -f radius-db
docker compose logs -f redis
```

### Database access:
```bash
docker exec -it radius-db psql -U radius -d radius
```

### Redis monitoring:
```bash
docker exec -it redis redis-cli monitor
```

### Restart services:
```bash
docker compose restart
```

### Debug RADIUS packets:
```bash
docker exec -it freeradius-server radiusd -X
```

---

## 🏭 Production Notes

### Security
- Change default passwords and API keys
- Use strong secrets for RADIUS clients
- Implement firewall rules for RADIUS ports
- Enable SSL/TLS for API endpoints

### Performance
- Monitor database partition performance
- Configure Redis memory limits
- Set appropriate connection pools
- Enable database query logging for optimization

### Monitoring
- Monitor service health endpoints
- Set up alerts for failed authentications
- Track accounting record processing
- Monitor ghost session cleanup

### Backup & Recovery
- Regular MySQL backups with partitioning consideration
- Redis persistence configuration
- FreeRADIUS configuration backup
- API service configuration backup

---

## 📊 Database Schema

The service uses partitioned tables for optimal performance:
- `radacct_YYYYMM` - Monthly partitioned accounting records
- `radpostauth_YYYYMM` - Monthly partitioned authentication logs
- `nas` - Network Access Server definitions
- `radcheck` - User authentication attributes
- `radreply` - User reply attributes
- `radgroupcheck` - Group check attributes
- `radgroupreply` - Group reply attributes

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.