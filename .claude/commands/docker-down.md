Stop the PodScheduler Docker stack.

Run: `docker compose down`

To also wipe the database volume (full reset): `docker compose down -v`

Warning: `down -v` deletes all PostgreSQL data. Only use it when you want a clean slate — for example, to test migrations from scratch.
