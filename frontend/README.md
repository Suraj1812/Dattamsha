# Dattamsha Frontend

Responsive React dashboard for the Dattamsha HR Intelligence backend.

## Local Development

```bash
cp .env.example .env
npm install
npm run dev
```

Default URL: `http://127.0.0.1:5173`

## Environment

- `VITE_API_BASE_URL` (required)
- `VITE_API_KEY` (optional, needed if backend enforces auth)
- `VITE_DEFAULT_EMPLOYEE_ID` (optional)

## Scripts

- `npm run dev`
- `npm run lint`
- `npm run test`
- `npm run build`
- `npm run preview`

## Production Container

```bash
docker build -t dattamsha-frontend .
docker run -p 8080:80 dattamsha-frontend
```

Health check endpoint: `GET /healthz`
