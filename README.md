# CRM Ticket Sorting API

A FastAPI service that classifies customer CRM tickets by **type**, **severity**, and **department**, and generates concise agent summaries. Uses an LLM (OpenRouter `openai/gpt-oss-120b`) with an automatic rule-based fallback.

---

## Features

- **LLM-powered classification** via OpenRouter (`openai/gpt-oss-120b`)
- **Rule-based fallback** — works without any API key
- **Safety validation** — agent summaries never ask for PIN, OTP, password, or card numbers
- **Pydantic models** — strict request/response validation with enums
- **Dockerized** — single-command deployment
- **CI/CD** — GitHub Actions workflow for automated EC2 deployment

---

## API Endpoints

### `GET /health`

Returns service health status.

**Response:**
```json
{
  "status": "ok",
  "service": "crm-ticket-sorting-api",
  "version": "1.0.0"
}
```

### `POST /sort-ticket`

Classify and structure a CRM ticket.

**Request Body:**
```json
{
  "ticket_id": "T-001",
  "channel": "app",
  "locale": "en",
  "message": "I sent 5000 taka to a wrong number this morning, please help me get it back"
}
```

| Field     | Type   | Required | Notes                                                    |
| --------- | ------ | -------- | -------------------------------------------------------- |
| ticket_id | string | Yes      | Echoed back in response                                  |
| channel   | string | No       | One of: `app`, `sms`, `call_center`, `merchant_portal`   |
| locale    | string | No       | One of: `bn`, `en`, `mixed`                              |
| message   | string | Yes      | Free-text customer complaint                             |

**Response:**
```json
{
  "ticket_id": "T-001",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Customer reports sending 5000 BDT to a wrong number and requests recovery.",
  "human_review_required": true,
  "confidence": 0.85
}
```

| Field                 | Type    | Description                                          |
| --------------------- | ------- | ---------------------------------------------------- |
| ticket_id             | string  | Matches the request value                            |
| case_type             | enum    | `wrong_transfer`, `payment_failed`, `refund_request`, `phishing_or_social_engineering`, `other` |
| severity              | enum    | `low`, `medium`, `high`, `critical`                  |
| department            | enum    | `customer_support`, `dispute_resolution`, `payments_ops`, `fraud_risk` |
| agent_summary         | string  | Neutral one- or two-sentence summary                 |
| human_review_required | boolean | `true` for phishing or critical cases                |
| confidence            | number  | Float between `0.0` and `1.0`                        |

---

## Environment Variables

| Variable             | Required | Default              | Description                          |
| -------------------- | -------- | -------------------- | ------------------------------------ |
| `OPENROUTER_API_KEY` | No*      | _(empty)_            | OpenRouter API key for LLM calls     |
| `OPENROUTER_MODEL`   | No       | `openai/gpt-oss-120b`| Model to use on OpenRouter           |
| `PORT`               | No       | `8000`               | Application port                     |

\* Without an API key the service still works using the rule-based fallback.

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

---

## Local Setup

### Prerequisites

- Python 3.12+
- pip

### Install & Run

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your OPENROUTER_API_KEY

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.

Interactive docs: `http://localhost:8000/docs`

### Test with curl

```bash
# Health check
curl http://localhost:8000/health

# Classify a ticket
curl -X POST http://localhost:8000/sort-ticket \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "T-001",
    "channel": "app",
    "locale": "en",
    "message": "I sent 3000 to wrong number"
  }'
```

---

## Docker

### Build & Run

```bash
docker build -t crm-ticket-sorting-api .

docker run -d \
  --name crm-ticket-api \
  -p 8000:8000 \
  -e OPENROUTER_API_KEY=your-key-here \
  crm-ticket-sorting-api
```

### Verify

```bash
curl http://localhost:8000/health
```

---

## Deployment (EC2 via GitHub Actions)

The project includes a GitHub Actions workflow (`.github/workflows/deploy.yml`) with **two separate jobs**:

1. **Build** — builds the Docker image on GitHub runners and pushes it to **GHCR** (`ghcr.io`) as a **public** package.
2. **Deploy** — SSHs into the EC2 instance and pulls the public image from GHCR (**no registry credentials needed** on the server).

### Prerequisites on EC2

1. **Docker** installed and running
2. **SSH access** configured
3. **No GHCR credentials needed** — the image is public

### Required GitHub Secrets

Set these in your repository under **Settings → Secrets and variables → Actions**:

| Secret               | Description                                          |
| -------------------- | ---------------------------------------------------- |
| `EC2_HOST`           | EC2 instance public IP or hostname                   |
| `EC2_USERNAME`       | SSH username (e.g., `ubuntu`, `ec2-user`)            |
| `EC2_SSH_KEY`        | Private SSH key (PEM format) for the EC2 instance    |
| `OPENROUTER_API_KEY` | OpenRouter API key passed to the container at runtime|

> **Note:** The build job uses the built-in `GITHUB_TOKEN` to push to GHCR — no extra PAT is needed. After the first push, go to your GitHub **Package settings** and set the package visibility to **Public** so EC2 can pull without authentication.

### Manual Deployment

If you prefer to deploy manually:

```bash
# SSH into your EC2 instance
ssh -i your-key.pem ubuntu@your-ec2-ip

# Pull the public image from GHCR (no login required)
docker pull ghcr.io/your-org/sust-preli-mock-2026:latest

# Run the container
docker run -d \
  --name crm-ticket-api \
  --restart unless-stopped \
  -p 80:8000 \
  -e OPENROUTER_API_KEY=your-key-here \
  ghcr.io/your-org/sust-preli-mock-2026:latest
```

---

## Architecture

```
┌────────────┐     POST /sort-ticket     ┌─────────────────┐
│   Client   │ ──────────────────────▶   │   FastAPI App    │
└────────────┘                           │                  │
                                         │  ┌────────────┐  │
                                         │  │ LLM Service│──┼──▶ OpenRouter API
                                         │  └─────┬──────┘  │
                                         │        │ fail?    │
                                         │  ┌─────▼──────┐  │
                                         │  │ Rule-Based  │  │
                                         │  │  Fallback   │  │
                                         │  └─────┬──────┘  │
                                         │        │         │
                                         │  ┌─────▼──────┐  │
                                         │  │  Safety     │  │
                                         │  │  Validator  │  │
                                         │  └────────────┘  │
                                         └─────────────────┘
```

---

## Project Structure

```
.
├── app/
│   ├── __init__.py          # Package init
│   ├── main.py              # FastAPI application & endpoints
│   ├── models.py            # Pydantic models & enums
│   ├── config.py            # Settings from environment
│   ├── llm_classifier.py    # OpenRouter LLM classification
│   ├── rule_based.py        # Keyword-based fallback classifier
│   └── safety.py            # Agent summary safety validation
├── .env.example             # Environment variable template
├── .gitignore
├── .github/
│   └── workflows/
│       └── deploy.yml       # CI/CD for EC2 deployment
├── Dockerfile               # Container build
├── PROBLEM.md               # Challenge specification
├── README.md                # This file
└── requirements.txt         # Python dependencies
```

---

## LLM Used

**Model:** `openai/gpt-oss-120b` via [OpenRouter](https://openrouter.ai)

The LLM is used to classify tickets with higher accuracy and generate natural-language agent summaries. When the LLM is unavailable (no API key, rate limit, timeout), the service automatically falls back to a rule-based keyword classifier.

---

## License

MIT
