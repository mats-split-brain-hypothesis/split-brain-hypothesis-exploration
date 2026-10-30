# custdedupe

Flags customer records that are probably the same person entered twice ("Jon Smith" / "John Smith",
"José Núñez" / "Jose Nunez"). The nightly CRM import calls `find_duplicates()` on each region's export and
sends the pairs to the support team for review.

```python
from custdedupe import find_duplicates
find_duplicates(["John Smith", "Jon Smith", "Priya Patel"], max_distance=1)
# [('John Smith', 'Jon Smith')]
```

Names are normalised first (case, accents, whitespace), then compared by Levenshtein distance.

## Tests

```
python -m unittest discover -s tests -t .
```

`tests/test_performance.py` runs a 5,000-customer export, about the size of one region's nightly batch.
