# FastAPI Routing and Path Parameters

Routing in FastAPI is handled using path operations. A path operation is a combination of a URL path and an HTTP method (like GET, POST, PUT, DELETE).

## Path Operations

You define a path operation using a decorator from the `FastAPI` instance. For example:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/items/{item_id}")
def read_item(item_id: int):
    return {"item_id": item_id}
```

In this example:
* The path is `/items/{item_id}`.
* The path parameter `item_id` is passed as an argument to the function `read_item`.
* The type of the parameter is declared as `int`. FastAPI uses standard Python type hints to perform automatic validation.

## Data Validation

If you go to the browser and open `http://127.0.0.1:8000/items/3`, you will get a response:
`{"item_id": 3}`

If you open `http://127.0.0.1:8000/items/foo`, you will get a validation error since `foo` is not an integer:

```json
{
  "detail": [
    {
      "loc": ["path", "item_id"],
      "msg": "value is not a valid integer",
      "type": "type_error.integer"
    }
  ]
}
```

## Path Order Matters

When creating path operations, you can have static paths and dynamic paths. The order of declaration matters because path operations are evaluated in order.

```python
@app.get("/users/me")
def read_user_me():
    return {"user_id": "the current user"}

@app.get("/users/{user_id}")
def read_user(user_id: str):
    return {"user_id": user_id}
```

If `/users/me` was declared after `/users/{user_id}`, then the request to `/users/me` would match `/users/{user_id}` and treat `"me"` as the `user_id`.
