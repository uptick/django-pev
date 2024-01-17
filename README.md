# Django Postgres Explain Visualizer (Django-PEV)

[![PyPI version](https://badge.fury.io/py/django-pev.svg)](https://pypi.org/project/django-pev/)
[![versions](https://img.shields.io/pypi/pyversions/django-pev.svg)](https://pypi.org/project/django-pev/)
[![Lint](https://github.com/uptick/django-pev/actions/workflows/ci.yaml/badge.svg)](https://github.com/uptick/django-pev/actions/workflows/ci.yaml)

This tool captures sql queries and uploads the query plan to postgresql explain visualizer (PEV) by [dalibo](https://explain.dalibo.com/). This is especially helpful for debugging slow queries.

This tool also exports a graphical UI similar to [pghero](https://github.com/ankane/pghero) but is embedded within your django app.

# Installation

1. `pip install django-pev`

2. Add to your urls

```
# urls.py
from django.urls import include, path

urlpatterns = [
    # ....

    path('django-pev/', include(('django_pev.urls', 'django_pev'), namespace='django_pev')),
]
```

3. Add to your installed apps
```
# settings.py

INSTALLED_APPS = [
    # ...
    "django_pev"
]
```

# Usage

Wrap some code with the explain context manager. All sql queries are captured
alongside a stacktrace (to locate where it was called). The slowest query is accessible via `.slowest`.

```python
import django_pev
from django.contrib.auth.models import User

with django_pev.explain() as e:
    # Every SQL query is captured
    list(User.objects.filter(email='test@test.com').all())

# Rerun the slowest query with `EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON)`
pev_response = e.slowest.visualize(
    # By default the text of the query is not uploaded for security reasons
    upload_query=True,
    # Set to false if the query is slow and you want only an explain
    analyze=True,
    # Give a helpful title for the uploaded query plan
    title="Measuring email filter",
)
print(pev_response.url)

# View the postgres explain visualization
e.slowest.visualize_in_browser()

# View the stack trace of the slowest query
print(e.slowest.stacktrace)

# Delete the plan hosted on https://explain.dalibo.com
pev_response.delete()
```

**How to debug a slow endpoint in production**

If you have access to `python manage.py shell` on the production server;
you can run the following code snippet to get an explain plan uploaded. In general this technique is all types of profiling.

```python
import django_pev

from django.contrib.auth.models import User
from django.test import Client as TestClient

client = TestClient()
# Authentication
client.force_login(User.objects.get(id=1))
url = "/some_slow_url"

with django_pev.explain() as e:
    response = client.get(url)

print(e.slowest.visualize(title=f"Fetching {url}"))

```

# TODO
- [ ] Add migration to ensure pg_stats_statement_info is correct
- [ ] Do not crash when its not available
- [ ] Add explain tab
= [ ] Add index suggester

# Disclaimer

Credit goes to Pierre Giraud (@pgiraud) for PEV2 and Alex Tatiyants (@AlexTatiyants) for the original pev tool.

IN NO EVENT SHALL DALIBO BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS, ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION, EVEN IF DALIBO HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

DALIBO SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE. THE SOFTWARE PROVIDED HEREUNDER IS ON AN "AS IS" BASIS, AND DALIBO HAS NO OBLIGATIONS TO PROVIDE MAINTENANCE, SUPPORT, UPDATES, ENHANCEMENTS, OR MODIFICATIONS.
