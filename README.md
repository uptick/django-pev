# DJDT-PEV2 (Django Debug Toolbar - Postgres explain visualizer 2)

[![PyPI version](https://badge.fury.io/py/django-pev.svg)](https://pypi.org/project/django-pev/)
[![versions](https://img.shields.io/pypi/pyversions/django-pev.svg)](https://pypi.org/project/django-pev/)
[![Lint](https://github.com/uptick/django-pev/actions/workflows/ci.yml/badge.svg)](https://github.com/uptick/djdt-pev2/actions/workflows/ci.yml)

This tool captures sql queries within the context and provides an easy interface to generate and utilize a postgresql explain visualizer (PEV) by [dalibo](https://explain.dalibo.com/).

# Usage

```python
import django_pev

with django_pev.explain(
    # By default the text of the query is not uploaded for security reasons
    upload_query=True,
    title="Analyzing slow User join"
) as e:
    # Every SQL query is captured
    list(User.objects.filter(some__long__join=1).all())

# Rerun the slowest query with `EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON)`
# And upload the results to https://explain.dalibo.com
pev_response = e.slowest.visualize()
print(pev_response.url)


# Delete the plan hosted on https://explain.dalibo.com
pev_response.delete()
```

# Disclaimer

Credit goes to Pierre Giraud (@pgiraud) for PEV2 and Alex Tatiyants (@AlexTatiyants) for the original pev tool.

IN NO EVENT SHALL DALIBO BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS, ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION, EVEN IF DALIBO HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

DALIBO SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE. THE SOFTWARE PROVIDED HEREUNDER IS ON AN "AS IS" BASIS, AND DALIBO HAS NO OBLIGATIONS TO PROVIDE MAINTENANCE, SUPPORT, UPDATES, ENHANCEMENTS, OR MODIFICATIONS.
