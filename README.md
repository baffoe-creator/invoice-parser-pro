# Invoice Parser Pro

Transform paper invoices into structured, actionable data with enterprise-grade precision.

## 📋 Overview

Invoice Parser Pro is a production-ready document processing platform that extracts structured financial data from PDF invoices. Built on FastAPI with a **stateless, zero-persistence architecture**, it delivers reliable invoice parsing without the operational overhead of traditional database-backed systems.

Finance teams can process individual invoices or batch operations with equal efficiency, exporting results to Excel for seamless integration with existing accounting workflows and ERP systems.

Live Demo: https://invoice-parser-proo.onrender.com/

**Privacy-First Design**: Your invoice data is processed in-memory and immediately discarded. No database, no persistent storage, no data retention concerns.


## ✨ Core Value Proposition

**Accelerated Processing**: Reduce manual data entry from hours to seconds while maintaining accuracy.

**Operational Simplicity**: Zero database configuration or maintenance required—deploy and start processing immediately.

**Privacy Assurance**: Stateless architecture ensures sensitive financial data is never persisted. Process, export, done.

**Enterprise Reliability**: Robust error handling and validation ensure consistent results across diverse invoice formats.

**Immediate Integration**: Excel export format works directly with existing financial systems and reporting tools.

**Cost Efficiency**: No database hosting fees, no backup storage costs, no scaling bottlenecks.

## 🎯 Key Features

### Intelligent Document Processing

- Extract vendor details, invoice numbers, dates, and financial amounts with precision
- Parse complex line items with quantity, pricing, and description data
- Handle diverse invoice layouts, discount calculations, and international currency formats
- Automatic detection of subtotals, taxes, shipping, and total amounts

### Flexible Processing Workflows

- **Single-file processing** for immediate needs
- **Bulk operations** for monthly reconciliation and batch imports
- **Drag-and-drop interface** with real-time validation and progress tracking
- **Session-based organization** with automatic cleanup after expiration

### Excel Integration

- Structured data exports compatible with accounting systems
- In-browser data preview and analysis
- Comprehensive field mapping (14+ data points per invoice)
- Download on-demand without server-side persistence

### Receivables Management

- Visual payment pipeline tracking (sent, viewed, due, overdue)
- Collections health scoring and risk assessment
- 30-day cash flow forecasting calendar
- Client reliability indicators and outstanding balance monitoring

## 🏗️ Architecture

### Technical Stack

- **Backend**: FastAPI with async processing capabilities
- **Data Handling**: Pandas for Excel generation and data manipulation
- **PDF Processing**: pdfplumber for reliable text extraction
- **Authentication**: Secure HTTP-only cookie-based sessions
- **Frontend**: Vanilla JavaScript with responsive design

### Design Principles

**Stateless Operation**: Session-based processing eliminates database dependencies and persistent storage risks

**Zero Persistence**: Invoice data exists only during processing (seconds), then vanishes completely

**Horizontal Scalability**: Deploy additional instances without database coordination or connection pooling

**Graceful Degradation**: Robust fallback mechanisms maintain service availability under various conditions

**Security by Design**: Can't leak data that isn't stored, can't breach records that don't exist

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- No database installation required

### Installation

```bash
git clone https://github.com/yourusername/invoice-parser-pro.git
cd invoice-parser-pro
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration

```bash
# Generate secure session key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Create .env file
cat > .env << EOF
SECRET_KEY=your-generated-key-here
FRONTEND_URL=https://your-domain.com
SESSION_MAX_AGE=7200
SECURE_COOKIES=true
EOF
```

### Run Application

```bash
python main.py
```

Access the application at `http://localhost:8000`

## 📖 Usage

### Processing Invoices

1. Upload PDF invoices via drag-and-drop interface
2. Parse with single click—no account creation required
3. Review extracted data in structured format
4. Export to Excel for accounting system integration

### Tracking & Analytics

1. Monitor payment status through visual pipeline
2. Track collections health and cash flow projections
3. Update invoice status as payments progress
4. Export comprehensive tracking reports

### Session Management

- Sessions automatically created on first request (anonymous)
- 2-hour expiration with auto-renewal on activity
- All session data purged after expiration
- No signup, no tracking, no identity verification

## 🔐 Security & Compliance

### Security Features

- **HTTP-only cookies** for session management (XSS protection)
- **HMAC-signed sessions** prevent tampering
- **File type validation** and size limits
- **CORS configuration** for controlled cross-origin access
- **No persistent storage** of sensitive financial data

### Compliance Benefits

- **GDPR Friendly**: No personal data collection or retention
- **SOC 2 Simplified**: No sensitive data persistence = fewer audit controls
- **Right to Erasure**: Already compliant—nothing to erase
- **Data Minimization**: Process only what's needed, discard everything else

### What We Don't Store

- Invoice PDFs (processed in-memory only)
- Vendor information
- Financial amounts
- Line item details
- User accounts or PII
- Processing history beyond current session

## 🛠️ API Reference

### Authentication

```
POST /api/auth/anonymous-session    # Create anonymous session
POST /api/auth/logout               # Clear session cookie
```

### Invoice Processing

```
POST /api/invoices/parse            # Single file upload
POST /api/invoices/bulk             # Batch processing
```

### Excel Export

```
GET  /api/export/xlsx               # Export metadata
GET  /api/export/download-xlsx      # Download Excel file
GET  /api/invoices/xlsx/data        # Retrieve data as JSON
GET  /api/invoices/xlsx/stats       # Processing statistics
```

### Invoice Tracking

```
GET  /api/invoices/tracking/dashboard        # Full dashboard data
POST /api/invoices/tracking/update-status    # Update invoice status
```

### Health Monitoring

```
GET  /                              # API info and feature status
GET  /health                        # Service health check
```

## 🔧 Configuration Reference

### Environment Variables

```bash
# Required
SECRET_KEY=<cryptographically-secure-random-key>

# Optional
SESSION_MAX_AGE=7200              # Session timeout in seconds (default: 2 hours)
FRONTEND_URL=https://your-app.com # CORS configuration
SECURE_COOKIES=true               # HTTPS-only cookies (production)
COOKIE_DOMAIN=.your-domain.com    # Cookie scope
```

### Deployment Options

**Render / Railway / Fly.io**
- No database addon required
- Set `FRONTEND_URL` environment variable
- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

**Docker**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

 
## 🐛 Troubleshooting

### Common Issues

**PDF Processing Fails**
- Ensure documents are text-based PDFs (not image scans)
- Verify PDF is not password-protected or encrypted
- Check file size is reasonable (<10MB recommended)

**Session Timeouts**
- Adjust `SESSION_MAX_AGE` for longer processing windows
- Sessions auto-renew on activity
- Clear browser cookies to reset session

**Export Errors**
- Verify write permissions in `data/` directory (auto-created)
- Ensure sufficient disk space for temporary files
- Files auto-cleanup after session expiration

### Performance Optimization

- For high-volume processing, increase `SESSION_MAX_AGE`
- Monitor memory usage during bulk operations (Pandas loads Excel in RAM)
- Consider horizontal scaling for enterprise workloads
- Use CDN for frontend assets in production

## 📊 Data Schema

### Excel Export Fields

| Field                 | Type    | Description                        |
|-----------------------|---------|------------------------------------|
| `vendor`              | string  | Supplier or vendor name            |
| `invoice_number`      | string  | Unique invoice identifier          |
| `invoice_date`        | date    | Invoice issuance date              |
| `due_date`            | date    | Payment due date                   |
| `subtotal`            | decimal | Pre-tax/discount total             |
| `tax_amount`          | decimal | Calculated tax charges             |
| `discount_amount`     | decimal | Applied discount value             |
| `discount_percentage` | decimal | Discount rate percentage           |
| `shipping_amount`     | decimal | Delivery/shipping charges          |
| `total_amount`        | decimal | Final invoice total                |
| `currency`            | string  | Currency code (USD, EUR, etc.)     |
| `line_item_*`         | mixed   | Itemized products/services         |
| `parsed_timestamp`    | datetime| Processing timestamp               |
| `file_name`           | string  | Original PDF filename              |

## 🤝 Contributing

We welcome contributions that enhance processing accuracy, expand format support, or improve user experience.

### Development Setup

```bash
# Clone and setup
git clone https://github.com/yourusername/invoice-parser-pro.git
cd invoice-parser-pro
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest

# Start development server
uvicorn main:app --reload
```

### Contribution Guidelines

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

 
*Invoice Parser Pro - Because your time is valuable, and your data is nobody's business but yours.*

---

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details.

 
---

**Status**: Production Ready | **Version**: 1.0.0 | **Last Updated**: November 2025
