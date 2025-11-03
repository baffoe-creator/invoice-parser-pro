# 📄 Invoice Parser Pro

> *Transform the chaos of paper invoices into structured, actionable intelligence.*

## 📋 Overview

Invoice Parser Pro is an enterprise-grade document intelligence platform that liberates finance teams from the tedium of manual data entry. By leveraging advanced PDF parsing algorithms, this production-ready FastAPI application extracts critical financial data from invoices with precision, enabling organizations to redirect valuable human capital toward strategic initiatives rather than repetitive transcription tasks.

Whether processing a single vendor invoice or orchestrating bulk imports from multiple suppliers, Invoice Parser Pro delivers structured Excel exports that integrate seamlessly into existing financial workflows—transforming hours of manual work into seconds of automated processing.

## ✨ Core Value Proposition

**Time Reclamation**: What typically consumes hours of manual entry and verification now executes in mere seconds, allowing finance professionals to focus on analysis and decision-making rather than data transcription.

**Accuracy Assurance**: Eliminate the human error inherent in manual data entry. Each invoice is parsed with algorithmic consistency, ensuring reliable data for downstream financial operations.

**Workflow Integration**: Export to Excel format provides immediate compatibility with existing accounting systems, ERP platforms, and financial reporting tools—no complex integrations required.

**Scalability**: Process individual invoices during ad-hoc needs or batch-process hundreds during month-end reconciliation. The architecture scales gracefully with your operational demands.

**Real-Time Intelligence**: The integrated Invoice Tracking Dashboard transforms static invoice data into dynamic receivables management, providing visibility into payment pipelines, cash flow forecasts, and collections health metrics.

## 🎯 Key Features

### Intelligent Document Parsing
- **Multi-Field Extraction**: Automatically identifies and extracts vendor information, invoice numbers, dates, line items, subtotals, taxes, discounts, and total amounts
- **Line Item Recognition**: Parses complex invoice tables with multiple products, quantities, and pricing structures
- **Currency Detection**: Identifies and captures currency information for international invoice processing

### Flexible Processing Modes
- **Single File Upload**: Perfect for immediate, one-off invoice processing needs
- **Bulk Processing**: Upload and parse multiple PDFs simultaneously, ideal for batch reconciliation operations
- **Drag-and-Drop Interface**: Intuitive user experience eliminates friction in the upload process

### Excel Export & Analysis
- **Structured Data Export**: All parsed invoices automatically compile into well-formatted Excel spreadsheets
- **Data Viewer**: In-browser Excel data visualization provides immediate insights without downloading
- **Session Management**: Organized file management with unique session identifiers for tracking and auditing

### Invoice Tracking Dashboard
- **Payment Status Pipeline**: Visual kanban-style pipeline tracking invoices through sent, viewed, due, and overdue stages
- **Collections Health Metrics**: Real-time scoring of receivables health with color-coded alerts
- **Cash Flow Calendar**: 30-day forecast showing expected payment dates and amounts
- **Client Reliability Indicators**: Track payment behaviors and identify high-risk accounts
- **Outstanding Balance Monitoring**: Aggregate view of total receivables across all statuses

### Production-Ready Architecture
- **RESTful API**: Clean, documented endpoints built with FastAPI for high performance
- **Authentication System**: Secure token-based authentication protecting sensitive financial data
- **CORS Support**: Configured for secure cross-origin requests in modern web architectures
- **SQLAlchemy Integration**: Robust database abstraction layer for data persistence
- **Error Handling**: Comprehensive exception management with detailed logging

## 🚀 Getting Started

### Prerequisites

```bash
Python 3.8+
pip (Python package manager)
```

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/invoice-parser-pro.git
cd invoice-parser-pro
```

2. **Create and activate virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Initialize the database**
```bash
python -m src.infrastructure.repositories.sqlalchemy_repo
```

### Running the Application

**Start the backend server:**
```bash
python main.py
```

The API will be available at `http://localhost:8000`

**Access the frontend:**
Open `http://localhost:8000` in your browser or serve the HTML file through your preferred web server.

## 📖 Usage Guide

### Single Invoice Processing

1. Navigate to the **Single File** tab
2. Click the upload area or drag-and-drop your PDF invoice
3. Click **Parse Invoice** to initiate processing
4. Review extracted data in the results panel
5. Download the Excel export for integration into your workflow

### Bulk Invoice Processing

1. Switch to the **Bulk Upload** tab
2. Select multiple PDF files (Ctrl/Cmd + Click for multiple selection)
3. Review the file list to confirm your selection
4. Click **Parse All Invoices** to process the batch
5. Monitor the progress and review the success/failure summary

### Excel Data Analysis

1. Navigate to the **Excel Viewer** tab
2. Click **Refresh Data** to load the latest parsed invoices
3. Analyze statistics including total invoices, data fields, and file information
4. Browse the complete dataset in the interactive table
5. Download the Excel file for external analysis

### Invoice Tracking & Receivables Management

1. Open the **Invoice Tracking** tab
2. Review the Collections Health score and outstanding balance
3. Monitor the Payment Status Pipeline to identify bottlenecks
4. Examine the Cash Flow Calendar for upcoming payment expectations
5. Update invoice statuses as payments progress
6. Export tracking reports for management presentations

## 🏗️ Architecture

### Backend Stack
- **FastAPI**: High-performance async web framework
- **SQLAlchemy**: ORM for database operations
- **Pandas**: Data manipulation and Excel generation
- **PyPDF2/pdfplumber**: PDF content extraction
- **Python-dotenv**: Environment configuration management

### Frontend Stack
- **Vanilla JavaScript**: Lightweight, dependency-free client-side logic
- **HTML5 & CSS3**: Modern, responsive user interface
- **Fetch API**: Asynchronous HTTP communication

### Project Structure
```
invoice-parser-pro/
├── main.py                          # Application entry point
├── src/
│   ├── api/
│   │   ├── endpoints/              # API route handlers
│   │   └── dependencies.py         # Dependency injection
│   ├── domain/                     # Business logic layer
│   ├── infrastructure/
│   │   └── repositories/           # Data persistence
│   └── xlsx_exporter.py            # Excel export functionality
├── data/                           # Processed invoice storage
├── frontend/                       # Web interface assets
└── requirements.txt                # Python dependencies
```

## 🔐 Security Considerations

- **Authentication Required**: All parsing endpoints require valid JWT tokens
- **File Validation**: Only PDF files are accepted, preventing malicious uploads
- **CORS Configuration**: Restricted to specified origins for enhanced security
- **Environment Variables**: Sensitive configuration isolated from codebase
- **Input Sanitization**: All user inputs are validated before processing

## 🛠️ API Endpoints

### Authentication
```
POST /api/auth/demo-login
```

### Invoice Processing
```
POST /api/invoices/parse           # Single file upload
POST /api/invoices/bulk             # Multiple file upload
```

### Excel Export
```
GET  /api/export/xlsx               # Export metadata
GET  /api/export/download-xlsx      # Download Excel file
GET  /api/invoices/xlsx/data        # Retrieve Excel data (JSON)
GET  /api/invoices/xlsx/stats       # Get export statistics
```

### Invoice Tracking
```
GET  /api/invoices/tracking/dashboard        # Full dashboard data
POST /api/invoices/tracking/update-status    # Update invoice status
GET  /api/invoices/tracking/health-metrics   # Collections health data
```

### Health & Diagnostics
```
GET  /health                        # Service health check
GET  /api/debug/routes              # List all routes (dev)
GET  /api/debug/files               # List data directory files (dev)
```

## 🎨 User Interface Features

- **Animated Background**: Engaging, modern aesthetic with subtle motion design
- **Drag-and-Drop Upload**: Intuitive file selection with visual feedback
- **Progress Indicators**: Real-time feedback during processing operations
- **Responsive Design**: Seamless experience across desktop and tablet devices
- **Status Visualization**: Color-coded indicators for quick status recognition
- **Interactive Tables**: Sortable, scrollable data tables for large datasets
- **Tab Navigation**: Organized feature access through clean tab interface

## 📊 Data Export Format

The Excel exports contain the following fields:

| Field | Description |
|-------|-------------|
| **vendor** | Supplier or vendor name |
| **invoice_number** | Unique invoice identifier |
| **invoice_date** | Date of invoice issuance |
| **subtotal** | Pre-tax total amount |
| **tax_amount** | Calculated tax charges |
| **discount_amount** | Applied discount value |
| **discount_percentage** | Discount rate percentage |
| **shipping_amount** | Delivery/shipping charges |
| **total_amount** | Final invoice total |
| **currency** | Currency code (USD, EUR, etc.) |
| **line_items** | Detailed product/service breakdown |

## 🔧 Configuration

Key configuration options in `.env`:

```env
DATABASE_URL=sqlite:///./invoices.db
API_HOST=0.0.0.0
API_PORT=8000
JWT_SECRET_KEY=your-secret-key-here
LOG_LEVEL=info
```

## 🐛 Troubleshooting

**Authentication Failures**
- Ensure the demo login endpoint is accessible
- Verify CORS settings match your frontend origin
- Check that tokens are properly stored and transmitted

**File Processing Errors**
- Confirm PDFs are not password-protected or encrypted
- Validate PDF structure is machine-readable (not scanned images)
- Check server logs for detailed error messages

**Excel Export Issues**
- Verify the `data/` directory exists and is writable
- Ensure sufficient disk space for export generation
- Check file permissions on the data directory

 
## 🤝 Contributing

Contributions are welcomed and appreciated. Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

 ## 🙏 Acknowledgments

- FastAPI community for exceptional documentation and framework design
- The open-source Python ecosystem for robust parsing libraries
- Finance professionals whose feedback shaped the feature roadmap

 
---

**Built with ❤️ for finance teams everywhere**

*Invoice Parser Pro - Because your time is worth more than data entry.*
