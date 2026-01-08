# Invoice Parser Pro

Transform paper invoices into structured, actionable data with enterprise-grade precision.

## Overview
Invoice Parser Pro is a production-ready document processing platform that extracts structured financial data from PDF invoices. Built on FastAPI with a stateless, zero-persistence architecture, it delivers reliable invoice parsing without the operational overhead of traditional database-backed systems.

Finance teams can process individual invoices or batch operations with equal efficiency, exporting results to Excel for seamless integration with existing accounting workflows and ERP systems.

Live Demo:[https://invoice-parser-pro-o.onrender.com/]

Privacy-First Design: Invoice data is processed in-memory and discarded immediately. No database, no persistent storage, no data retention concerns.

## Core Value Proposition
- Accelerated Processing: Reduce manual data entry from hours to seconds while maintaining accuracy.
- Operational Simplicity: Zero database configuration or maintenance required—deploy and start processing immediately.
- Privacy Assurance: Stateless architecture ensures sensitive financial data is never persisted.
- Enterprise Reliability: Robust error handling and validation ensure consistent results across diverse invoice formats.
- Immediate Integration: Excel export format works directly with existing financial systems and reporting tools.
- Cost Efficiency: No database hosting fees, no backup storage costs, no scaling bottlenecks.

## Key Features
### Intelligent Document Processing
- Extract vendor details, invoice numbers, dates, and financial amounts with precision.
- Parse complex line items with quantity, pricing, and description data.
- Handle diverse invoice layouts, discounts, and international currency formats.
- Automatic detection of subtotals, taxes, shipping, and total amounts.

### Processing Endpoints & Workflows
- POST `/api/v2/invoices/parse` — upload and parse a single invoice.
- POST `/api/v2/invoices/bulk` — batch processing for monthly reconciliation and imports.
- PATCH `/api/v2/invoices/{invoice_id}/fields/{field}` — apply manual corrections.
- POST `/api/v2/invoices/{invoice_id}/webhook` — enqueue webhook deliveries for downstream systems.
- POST `/api/v2/invoices/{invoice_id}/approve` — approve and export an invoice (returns Excel or presigned URL).

These API endpoints are designed for easy integration into existing pipelines and automation scripts.

### Background Processing & Queueing
- RQ-based worker architecture with Redis as the queue backend for webhook delivery and export tasks.
- Retry, backoff and visibility on failed deliveries are included.
- Workers are designed to run either as local processes during development or as containerized services in production.

### Excel Export & Data Handling
- In-memory Excel generation using Pandas and openpyxl with streaming download support.
- Detailed Excel schema covering vendor, invoice metadata, line items and timestamps.
- Option to export to S3 via presigned URLs for large exports or archival workflows.

### Stateless Session Handling
- Anonymous, HTTP-only cookie sessions with configurable timeout and automatic cleanup.
- Session data is kept in memory and removed after expiry, avoiding database dependencies.
- Designed for horizontal scaling: add instances without database coordination.

### Integration & Developer Experience
- Local Redis support via Docker (`redis:7`) for simple dev setup.
- Docker Compose configuration available for orchestrating app + worker + Redis.
- WSL + Docker guidance for Windows developers and Remote - WSL workflow in VS Code.
- Commands and example scripts included in the Quick Start section below.

## Architecture
### Technical Stack
- Backend: FastAPI (async)  
- Data Handling: Pandas (Excel generation)  
- PDF Processing: pdfplumber (text extraction)  
- Queue: Redis + RQ (background jobs)  
- Authentication: HTTP-only cookie-based anonymous sessions (HMAC signed)  
- Frontend: Vanilla JavaScript (responsive)

### Design Principles
- Stateless Operation: Session-based processing avoids persistent storage risks.  
- Zero Persistence: Invoice data exists only for the duration of processing and is discarded afterwards.  
- Horizontal Scalability: Add instances without DB coordination.  
- Graceful Degradation: Fallbacks to maintain availability under load.  
- Security by Design: Reduces attack surface by not persisting sensitive data.

## Quick Start (local development)
### Prerequisites
- Python 3.8+ (3.12 recommended)  
- Docker Desktop (WSL2 integration for Windows) or a Redis instance  
- Git  
- (Optional) VS Code with Remote - WSL for Windows development

### Setup (Recommended: WSL / Linux)
1. Clone the repository:
   ```
   git clone https://github.com/yourusername/invoice-parser-pro.git
   cd invoice-parser-pro
   ```

2. (Optional for Windows) copy the project into the WSL filesystem for best performance:
   ```
   mkdir -p ~/projects
   cp -r /mnt/c/Users/<your-windows-user>/invoice-parser-pro ~/projects/
   cd ~/projects/invoice-parser-pro
   ```

3. Create and activate a virtual environment:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   ```

4. Install dependencies:
   ```
   pip install --upgrade pip
   pip install -r requirements.txt
   # Ensure the needed extras for local dev
   pip install redis rq requests pandas openpyxl python-dotenv uvicorn fastapi
   ```

5. Start Redis (Docker):
   ```
   docker run -d --name invoice-redis -p 6379:6379 redis:7
   docker exec -it invoice-redis redis-cli PING   # expect: PONG
   ```

6. Create a `.env` file in the project root:
   ```
   REDIS_URL=redis://localhost:6379/0
   SECRET_KEY=your-generated-key
   ENABLE_S3=false
   ```

7. Start the application (terminal #1):
   ```
   python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

8. Start an RQ worker (terminal #2):
   ```
   source .venv/bin/activate
   rq worker webhooks --url redis://localhost:6379/0
   ```

9. Test a parse (terminal #3):
   ```
   curl -F "file=@/path/to/test.pdf" http://localhost:8000/api/v2/invoices/parse
   ```

### Docker Compose (optional)
If you prefer an all-container dev environment, a `docker-compose.yml` is supported in the repository to orchestrate app, worker and Redis. Start with:
```
docker compose up --build
```
This runs the app, worker, and Redis in containers and is suitable for reproducible local testing and staging.

## Usage
### Processing Invoices
- Upload PDF invoices via the web interface or the `/api/v2/invoices/parse` endpoint.  
- Review parsed data and apply manual patches via the PATCH endpoint.  
- Enqueue webhook deliveries for downstream systems.  
- Approve invoices for Excel export or download.

### Tracking & Analytics
- Visual pipeline for invoice status (sent / viewed / due / overdue).  
- Collections health scoring and 30-day cash flow forecasting.  
- Exportable tracking reports for accounting and collections teams.

### Session Management
- Anonymous sessions created on first request.  
- Default expiration: 2 hours (configurable via `SESSION_MAX_AGE`).  
- Session data is purged after expiration; no signup is required.

## Security & Compliance
### Security Features
- HTTP-only cookies for session management.  
- HMAC-signed sessions to prevent tampering.  
- File type validation and size limits.  
- CORS configuration for controlled cross-origin access.  
- No persistent storage of invoice data by default.

### Compliance Benefits
- GDPR-friendly: minimized processing and no data retention.  
- Reduced audit surface: no persistent sensitive data stored.  
- Right to Erasure: nothing to erase in persistent storage.

## API Reference (overview)
### Authentication
- POST `/api/auth/anonymous-session` — create anonymous session  
- POST `/api/auth/logout` — clear session cookie

### Invoice Processing
- POST `/api/v2/invoices/parse` — single file upload  
- POST `/api/v2/invoices/bulk` — batch processing

### Excel Export
- GET `/api/export/xlsx` — export metadata  
- GET `/api/export/download-xlsx` — download Excel file  
- GET `/api/invoices/xlsx/data` — retrieve data as JSON  
- GET `/api/invoices/xlsx/stats` — processing statistics

### Invoice Tracking
- GET `/api/invoices/tracking/dashboard` — dashboard data  
- POST `/api/invoices/tracking/update-status` — update invoice status

### Health Monitoring
- GET `/` — API info and feature status  
- GET `/health` — service health check

## Configuration Reference
### Environment Variables
Required:
- `SECRET_KEY` — cryptographically secure random key

Optional:
- `SESSION_MAX_AGE` — seconds (default: 7200)  
- `FRONTEND_URL` — CORS origin  
- `SECURE_COOKIES` — true/false  
- `REDIS_URL` — Redis connection string  
- `COOKIE_DOMAIN` — cookie scope

### Deployment
- Deploy to Render, Railway, Fly.io, or any container host.  
- No database addon required.  
- Set `FRONTEND_URL` and `REDIS_URL` in environment.  
- Start command example:
  ```
  uvicorn main:app --host 0.0.0.0 --port $PORT
  ```

### Docker
Example Dockerfile pattern:
```
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Troubleshooting
### Common Issues
- PDF processing fails: ensure documents are text-based (not scanned images). Use OCR before parsing if needed.  
- Session timeouts: increase `SESSION_MAX_AGE`.  
- Export errors: verify write permissions for temporary files and available disk space.

### Performance
- For high-volume processing, horizontally scale instances and monitor memory (Pandas uses RAM).  
- Use hosted Redis when running multiple instances in production.  
- Serve static assets via CDN in production.

## Data Schema
Excel Export Fields (examples)
- vendor (string) — supplier or vendor name  
- invoice_number (string)  
- invoice_date (date)  
- due_date (date)  
- subtotal (decimal)  
- tax_amount (decimal)  
- discount_amount (decimal)  
- shipping_amount (decimal)  
- total_amount (decimal)  
- currency (string)  
- line_item_* (mixed)  
- parsed_timestamp (datetime)  
- file_name (string)

## Contributing
We welcome contributions that improve parsing accuracy, add format support, or enhance usability.

### Development Setup
```
git clone https://github.com/yourusername/invoice-parser-pro.git
cd invoice-parser-pro
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pytest
uvicorn main:app --reload
```

### Contribution Workflow
- Fork the repository  
- Create a feature branch: `git checkout -b feature/amazing-feature`  
- Commit changes: `git commit -m "Add amazing feature"`  
- Push and open a Pull Request

## License
MIT License - See LICENSE file for details.

