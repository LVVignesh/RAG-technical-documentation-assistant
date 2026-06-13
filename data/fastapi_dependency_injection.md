# FastAPI Dependency Injection

FastAPI has a very powerful and intuitive **Dependency Injection** system. It allows you to declare dependencies that your path operations need to run.

## What is Dependency Injection?

Dependency Injection means, in programming, that there is a way for your code to declare things that it requires (depends on) to work. The framework then takes care of providing those dependencies to your code.

This is very useful when you need to:
* Shared logic (the same code logic again and again).
* Share database connections.
* Enforce security, authentication, role-based access control, etc.
* Minimize code duplication.

## First Steps Example

Let's look at a simple dependency that extracts query parameters `q` and `skip`/`limit` pagination parameters:

```python
from typing import Union
from fastapi import Depends, FastAPI

app = FastAPI()

async def common_parameters(q: Union[str, None] = None, skip: int = 0, limit: int = 100):
    return {"q": q, "skip": skip, "limit": limit}

@app.get("/items/")
async def read_items(commons: dict = Depends(common_parameters)):
    return commons

@app.get("/users/")
async def read_users(commons: dict = Depends(common_parameters)):
    return commons
```

Here:
* `Depends(common_parameters)` tells FastAPI that the endpoint depends on the `common_parameters` function.
* FastAPI will call `common_parameters` with the request parameters, extract its return value, and pass it to the parameter `commons` in our path operation function.
* Using `Depends` avoids duplicating query parameters across multiple path operations.

## Dependency Cache / Share

If you declare a dependency in multiple places (e.g., in a sub-dependency and a main dependency), FastAPI will default to caching the dependency result within a single request. This means it only runs the dependency once per request, unless you specify `use_cache=False`.
