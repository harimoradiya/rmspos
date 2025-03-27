# Database Migrations

This directory contains database migrations for the Restaurant Management System.

## Running Migrations

To run migrations:

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Run all pending migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1
```

## Migration History

Initial migrations:
- User management (users table)
- Restaurant management (restaurants table)