# FastAPI Query Parameters and Validation

When you declare function parameters that are not part of the path parameters, FastAPI automatically interprets them as "query" parameters.

## Basic Query Parameters

```python
from fastapi import FastAPI

app = FastAPI()

fake_items_db = [{"item_name": "Foo"}, {"item_name": "Bar"}, {"item_name": "Baz"}]

@app.get("/items/")
def read_item(skip: int = 0, limit: int = 10):
    return fake_items_db[skip : skip + limit]
```

In the example above:
* `skip` and `limit` are query parameters. Since they have default values (`0` and `10`), they are optional.
* If you go to `http://127.0.0.1:8000/items/`, they default to `skip=0` and `limit=10`.
* If you go to `http://127.0.0.1:8000/items/?skip=1&limit=1`, the values will be `skip=1` and `limit=1`.

## Query Parameter Validation with Query

FastAPI allows you to add validation and metadata to query parameters using the `Query` class from `fastapi`.

```python
from typing import Union
from fastapi import FastAPI, Query

app = FastAPI()

@app.get("/items/")
def read_items(q: Union[str, None] = Query(default=None, min_length=3, max_length=50, pattern="^fixedquery$")):
    results = {"items": [{"item_id": "Foo"}, {"item_id": "Bar"}]}
    if q:
        results.update({"q": q})
    return results
```

Here:
* `min_length=3` and `max_length=50` validates that the query parameter `q` (if provided) is between 3 and 50 characters long.
* `pattern="^fixedquery$"` adds a regular expression check to enforce a specific format.
* If the validation fails, FastAPI returns a `422 Unprocessable Entity` response automatically.
