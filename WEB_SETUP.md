# Web Frontend Setup - Bank Statement Processor

## Architecture Overview

Phase 5 implementation includes:

### Backend (FastAPI)
- **Location**: `src/api/`
- **Framework**: FastAPI with async support
- **Features**:
  - JWT authentication system
  - Chunked file upload (50MB max)
  - Asynchronous job processing
  - Real-time WebSocket progress updates
  - RESTful API endpoints
  - Automatic file cleanup

### Frontend (React + TypeScript)
- **Location**: `frontend/`
- **Framework**: React 18 with TypeScript
- **Features**:
  - Drag-and-drop file upload
  - Real-time progress tracking
  - Responsive results table
  - Professional UI with animations
  - Error boundaries and handling

### Shared Library
- **Location**: `src/lib/`
- **Purpose**: Core processing logic shared between CLI and web API
- **Contents**: Parsers, extractors, exporters moved from original structure

## Quick Start

### 1. Start Backend Server
```bash
./scripts/start-api.sh
```
- Starts FastAPI server on http://localhost:8000
- Auto-installs dependencies if needed
- Sets up virtual environment

### 2. Start Frontend (in separate terminal)
```bash
./scripts/start-frontend.sh
```
- Starts React dev server on http://localhost:3000
- Auto-installs npm dependencies if needed
- Proxies API requests to backend

### 3. Access Application
- Open http://localhost:3000 in browser
- Demo authentication token generated automatically
- Upload PDF bank statements and process

## ✅ Status: COMPLETED & TESTED
- All React compilation errors fixed
- CSS modules successfully implemented
- TypeScript errors resolved
- Production build tested and working
- No styled-jsx dependencies required

## API Endpoints

### Authentication
- `GET /demo-token` - Get demo JWT token (development only)

### File Processing
- `POST /upload` - Upload PDF file (returns job_id)
- `POST /process/{job_id}` - Start processing uploaded file
- `GET /status/{job_id}` - Check job status and progress
- `GET /results/{job_id}` - Get detailed results with transactions
- `GET /download/{job_id}` - Download processed CSV file
- `WebSocket /ws/progress/{job_id}` - Real-time progress updates

### Cleanup
- `DELETE /jobs/{job_id}` - Clean up job data and files

## File Structure

```
├── src/
│   ├── api/                 # FastAPI backend
│   │   ├── main.py         # FastAPI application
│   │   ├── models.py       # Pydantic models
│   │   ├── auth.py         # JWT authentication
│   │   └── jobs.py         # Job management
│   └── lib/                # Shared processing library
│       ├── api.py          # Clean interface for core functionality
│       ├── parsers/        # Bank statement parsers
│       ├── extractors/     # Data extraction utilities
│       ├── exporters/      # CSV export functionality
│       ├── core/           # Core exceptions and utilities
│       └── validators/     # Data validation
├── frontend/
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── hooks/          # Custom React hooks
│   │   ├── services/       # API service layer
│   │   ├── types/          # TypeScript type definitions
│   │   └── App.tsx         # Main application component
│   ├── package.json        # Frontend dependencies
│   └── tsconfig.json       # TypeScript configuration
└── scripts/
    ├── start-api.sh        # Backend startup script
    └── start-frontend.sh   # Frontend startup script
```

## Key Features

### 1. File Upload
- Drag-and-drop interface
- PDF validation (type, size)
- Upload progress indication
- 50MB maximum file size

### 2. Real-time Processing
- WebSocket connection for live updates
- Progress percentage and status messages
- Automatic reconnection on disconnect
- Error handling and recovery

### 3. Results Display
- Paginated transaction table
- Sortable columns (date, amount, type, etc.)
- Formatted currency display (INR)
- Transaction type badges
- Responsive mobile design

### 4. CSV Export
- One-click download
- Clean filename generation
- Secure token-based download
- Automatic cleanup after processing

### 5. Error Handling
- Global error boundaries
- Network error recovery
- User-friendly error messages
- Graceful degradation

## Security Features

### Authentication
- JWT token-based authentication
- Demo token for development
- Token expiration handling
- Automatic token refresh

### File Security
- PDF-only upload restriction
- File size validation
- Temporary file cleanup
- Secure file serving

### API Security
- CORS configuration for frontend
- Request validation with Pydantic
- Error message sanitization
- No sensitive data in logs

## Performance Optimizations

### Backend
- Async/await throughout
- Thread pool for CPU-intensive tasks
- Efficient job queue management
- Automatic resource cleanup

### Frontend
- React.StrictMode for development
- Efficient re-renders with proper state management
- Optimized bundle size
- Progressive loading

## Development Notes

### Code Quality
- All files under 200 lines as requested
- Comprehensive TypeScript types
- Error boundaries and handling
- Clean separation of concerns

### Extensibility
- Plugin-ready parser architecture
- Modular component structure
- Clean API interfaces
- Configurable endpoints

## Production Considerations

### Environment Variables
```bash
JWT_SECRET_KEY=your-production-secret-key
API_BASE_URL=https://your-api-domain.com
REACT_APP_API_URL=https://your-api-domain.com
```

### Database Integration
- Replace in-memory job storage with Redis/PostgreSQL
- Add user management and authentication
- Implement persistent job history

### Deployment
- Use production WSGI server (gunicorn/uvicorn)
- Build React app for production (`npm run build`)
- Configure reverse proxy (nginx)
- Set up SSL certificates

## Browser Support
- Modern browsers with WebSocket support
- Chrome 80+, Firefox 76+, Safari 13+, Edge 80+
- Progressive enhancement for older browsers

## Testing
- Backend: pytest with coverage
- Frontend: React Testing Library
- E2E: Can be added with Playwright/Cypress

This implementation provides a complete web-based solution for bank statement processing with a professional UI and robust backend architecture.