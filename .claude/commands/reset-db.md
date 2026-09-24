Fully reset the database and re-run migrations + seed from scratch.

**Warning: this destroys all data.** Only use during development.

```bash
# Stop stack and wipe the postgres volume
docker compose down -v

# Rebuild and start (migrations + seed run automatically via entrypoint.sh)
docker compose up --build -d

# Watch startup logs
docker compose logs -f web
```

After reset, the only user is:
- Email: `admin@example.com` (or whatever ADMIN_EMAIL is in .env)
- Password: `changeme123` (or whatever ADMIN_PASSWORD is in .env)

The seed creates these roles automatically: `admin`, `producer`, `host`, `viewer`.

## If you only want to re-run the seed without wiping data

```bash
docker compose exec web uv run flask seed
```

The seed is idempotent — safe to re-run. It creates roles/admin if missing and updates existing role permissions to match the current `PERMISSIONS` dict.
