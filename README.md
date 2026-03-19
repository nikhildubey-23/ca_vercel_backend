# TaxPilot Pro - Vercel Backend

## Tech Stack
- **FastAPI** - Modern Python web framework (Vercel compatible)
- **JWT** - Token authentication
- **In-memory storage** - For demo (data resets on cold start)

## Deploy Steps

### 1. Push to GitHub
```bash
cd taxpilot-pro/vercel_backend
git add .
git commit -m "FastAPI backend"
git push
```

### 2. Deploy on Vercel
1. Go to [vercel.com](https://vercel.com)
2. Add New Project → Import GitHub repo
3. Framework: **Other**
4. Click Deploy

### 3. Add Environment Variables
| Variable | Value |
|----------|-------|
| `JWT_SECRET` | Any secure random string |
| `GROQ_API_KEY` | Your Groq API key |
| `GROQ_MODEL` | llama-3.1-70b-versatile |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/auth/register` | User registration |
| POST | `/api/auth/login` | User login |
| GET | `/api/auth/profile` | Get user profile |
| GET | `/api/folders` | List folders |
| POST | `/api/folders` | Create folder |
| GET | `/api/documents` | List documents |
| POST | `/api/documents/upload` | Upload document |
| DELETE | `/api/documents/:id` | Delete document |
| POST | `/api/tax/calculate` | Calculate tax |
| GET | `/api/tax/slabs` | Get tax slabs |
| POST | `/api/chatbot/query` | Chat with AI |

## Admin Panel
- **URL**: `https://your-app.vercel.app/admin`
- **Login**: `admin@taxpilot.com` / `admin123`

## Note
Data is stored in-memory. For production, integrate PostgreSQL or another database.
