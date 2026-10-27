# Member shop backend (SellAuth + VaultCord)

## Where the API key goes
Never in the code. Put it in Vercel: Project -> Settings -> Environment Variables
-> name `VAULTCORD_API_KEY`, value = your (new) VaultCord API key. Redeploy afterwards.
For local testing copy `.env.example` to `.env` and export the variables.

## Deploy
1. Create a free Postgres database (Neon or Supabase) and copy its connection URL into `DATABASE_URL`.
2. Upload the files from this zip (main.py must be in the top level of the repository, not in a subfolder) to GitHub and import it as a new Vercel project.
3. Add all variables from `.env.example` in Vercel.
4. In Vercel -> Settings -> Functions, set the max duration to at least 60 seconds.

## Test
Create a code (50 members, standard offer):
curl -X POST https://YOUR-URL/admin/create -H "X-Admin-Token: YOUR_ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"tier":"standard","amount":50}'
Open the returned link, redeem it with your test server, add the bot, start the delivery.

## Still open
`parse_order()` in main.py (SellAuth webhook payload). Until then create codes with /admin/create.
