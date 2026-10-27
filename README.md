
# Member Shop

FastAPI-based member shop with a Neon PostgreSQL database, redeem codes, and an admin panel for generating codes.

## Features

- Redeem codes through the website
- Admin panel at `/admin`
- Generate between 1 and 500 redeem codes at a time
- Select the package (`standard` or `valid`)
- Choose the number of members per code
- Store codes and order status in Neon PostgreSQL
- Generate individual redemption links
- VaultCord API integration for buying and delivering orders

## Requirements

- Python 3.11+
- A Neon PostgreSQL database
- A Vercel project configured to run FastAPI
- A VaultCord API key

## Installation

Install the dependencies:

```bash
pip install -r requirements.txt
```

The `requirements.txt` file should contain:

```text
fastapi
httpx
python-multipart
psycopg[binary]
```

## Environment Variables

Configure these variables in Vercel under:

**Project → Settings → Environment Variables**

| Variable | Description |
|---|---|
| `DATABASE_URL` | Neon PostgreSQL connection string |
| `ADMIN_TOKEN` | Secret token protecting the admin API |
| `VAULTCORD_API_KEY` | VaultCord API key |
| `BASE_URL` | Website URL, e.g. `https://membershop.vercel.app` |
| `BRAND_NAME` | Optional shop name |
| `SUPPORT_URL` | Optional support link |
| `SELLAUTH_WEBHOOK_SECRET` | Optional webhook secret |

Never commit real API keys, database passwords, or admin tokens to GitHub.

## Admin Panel

Open:

`https://membershop.vercel.app/admin`

Enter the `ADMIN_TOKEN` and choose:

- Number of codes: 1–500
- Package: Standard or Valid
- Members per code

Click **Generate keys** to create and store the codes in Neon. Copy and save the generated codes and redemption links securely.

## Redemption

Each generated code has an individual link:

`https://membershop.vercel.app/o/CODE`

Customers can enter the code, their Discord server invite link, and their email address.

The application then attempts to purchase the selected package through VaultCord. After the bot is added to the Discord server, the customer can start delivery.

## Database

The application creates an `orders` table automatically when the application starts.

The table stores:

- Redeem code
- Package and member quantity
- Redemption status
- Customer email
- Invite link
- VaultCord order details
- Creation timestamp

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Main redemption page |
| `GET` | `/faq` | Frequently asked questions |
| `GET` | `/o/{code}` | Individual order page |
| `POST` | `/redeem` | Redeem a code |
| `POST` | `/pull` | Start delivery |
| `GET` | `/admin` | Admin key generator |
| `POST` | `/admin/generate` | Generate multiple codes |
| `POST` | `/admin/create` | Create a single code |
| `GET` | `/admin/orders` | List recent orders |
| `POST` | `/webhook/sellauth` | SellAuth webhook endpoint |

Admin API requests must include the header:

`X-Admin-Token: YOUR_ADMIN_TOKEN`

## Deployment

1. Push the project to the GitHub repository connected to Vercel.
2. Configure the environment variables.
3. Ensure the project has the correct FastAPI entry point and Vercel configuration.
4. Deploy the project.
5. Open `/admin` and test code generation.

## Important Notes

- The admin token must remain secret.
- Database credentials must never be exposed to browser JavaScript.
- Generated codes are stored in the database.
- A code should only be redeemed once.
- The SellAuth `parse_order()` function currently requires implementation based on the actual webhook payload.
- Verify the VaultCord API endpoint paths and payload format against the current VaultCord API documentation.
- Test the application in a staging environment before using it with real orders.
