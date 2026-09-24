Start the PodScheduler Docker stack.

Run: `docker compose up --build -d`

Then tail the web logs with: `docker compose logs -f web`

The app will be available at http://localhost:5000 once the web container prints "Booting worker". The entrypoint runs migrations and seed before starting gunicorn, so the first boot takes ~10 seconds.

If the web container crashes on startup, check `docker compose logs web` — common causes:
1. Database not ready yet (healthcheck should prevent this, but retry if needed)
2. Migration error — check the migration file in migrations/versions/
3. entrypoint.sh missing execute bit — fix with `git update-index --chmod=+x entrypoint.sh` then rebuild
