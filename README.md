# Django Postgres Explain Visualizer (Django-PEV)

[![PyPI version](https://badge.fury.io/py/django-pev.svg)](https://pypi.org/project/django-pev/)
[![versions](https://img.shields.io/pypi/pyversions/django-pev.svg)](https://pypi.org/project/django-pev/)
[![Lint](https://github.com/uptick/django-pev/actions/workflows/ci.yaml/badge.svg)](https://github.com/uptick/django-pev/actions/workflows/ci.yaml)

This tool captures sql queries and uploads the query plan to postgresql explain visualizer (PEV) by [dalibo](https://explain.dalibo.com/). This is especially helpful for debugging slow queries.

# Usage

Wrap some code with the explain context manager. All sql queries are captured
alongside a stacktrace (to locate where it was called). The slowest query is accessible via `.slowest`.

```python
import django_pev

with django_pev.explain(
    title="Analyzing slow User join"
) as e:
    # Every SQL query is captured
    list(User.objects.filter(some__long__join=1).all())

# Rerun the slowest query with `EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON)`
pev_response = e.slowest.visualize(
    # By default the text of the query is not uploaded for security reasons
    upload_query=True,
)
print(pev_response.url)

# View the visualization
e.slowest.visualize_in_browser()


# Delete the plan hosted on https://explain.dalibo.com
pev_response.delete()
```

**Debugging a slow endpoint**

```python
import django_pev

from django.test import Client as TestClient

client = TestClient()

with django_pev.explain() as e:
    url = "/some_slow_url"
    response = client.get(url)

print(e.slowest.visualize())

```

# Disclaimer

Credit goes to Pierre Giraud (@pgiraud) for PEV2 and Alex Tatiyants (@AlexTatiyants) for the original pev tool.

IN NO EVENT SHALL DALIBO BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS, ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION, EVEN IF DALIBO HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

DALIBO SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE. THE SOFTWARE PROVIDED HEREUNDER IS ON AN "AS IS" BASIS, AND DALIBO HAS NO OBLIGATIONS TO PROVIDE MAINTENANCE, SUPPORT, UPDATES, ENHANCEMENTS, OR MODIFICATIONS.
