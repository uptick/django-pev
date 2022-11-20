# Usage

```
import django_pev

with django_pev.explain() as e:
    # do stuff

pev_response = e.slowest.visualize()
pev_response.delete()
```
