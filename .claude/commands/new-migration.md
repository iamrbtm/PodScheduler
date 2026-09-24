Create a new Alembic database migration after changing models.

Steps:
1. Make your model changes in `app/models/`
2. Run: `docker compose exec web uv run flask db migrate -m "short description"`
3. Review the generated file in `migrations/versions/` — Alembic auto-detection is imperfect:
   - Column **renames** will appear as drop+add (data loss!). Change to `op.alter_column()` or `op.execute("ALTER TABLE ... RENAME COLUMN ...")`
   - Table **renames** will appear as drop+add. Change to `op.rename_table()`
   - Enum changes may need manual SQL
4. Apply with: `docker compose exec web uv run flask db upgrade`
5. To roll back: `docker compose exec web uv run flask db downgrade`

If writing the migration manually (preferred for renames), use this template:

```python
def upgrade():
    # Example: rename a column
    op.execute('ALTER TABLE tablename RENAME COLUMN old_name TO new_name')
    # Example: add a column with a default
    op.add_column('tablename', sa.Column('new_col', sa.String(100), nullable=True))

def downgrade():
    op.drop_column('tablename', 'new_col')
    op.execute('ALTER TABLE tablename RENAME COLUMN new_name TO old_name')
```
