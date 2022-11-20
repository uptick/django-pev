# Usage

```
import django_pev

with django_pev.explain() as e:
    # do stuff

print(e.format_results())
e.analyze_slowest()
e.visualize_slowest()
```
