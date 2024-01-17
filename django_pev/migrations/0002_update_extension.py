# Generated by Django 4.2.9 on 2024-01-17 03:19
import logging

from django.db import OperationalError, connection, migrations


def create_extension(apps, schema_editor):
    try:
        with connection.cursor() as cursor:
            cursor.execute("select extversion from pg_extension where extname = 'pg_stat_statements'")
            version = float(cursor.fetchone()[0])
            if version < 1.9:
                cursor.execute("alter extension pg_stat_statements update to '1.9'")
                cursor.execute("alter extension pg_stat_statements update to '1.10'")
    except OperationalError:
        logging.error("Could not update extension `pg_stat_statements`.")


class Migration(migrations.Migration):
    dependencies = [
        ("django_pev", "0001_enable_extensions"),
    ]

    operations = []