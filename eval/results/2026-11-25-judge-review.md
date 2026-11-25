# Revisión humana del juez

9 casos. En cada tabla, la columna `¿De acuerdo? (sí/no)` es tuya: escribe `sí` si la afirmación está bien juzgada (apoyada o no por el contexto) y `no` si el juez se equivocó; la nota es opcional. Los fragmentos muestran un extracto de ~1500 caracteres (`[...]`); el texto completo que vio el juez está en el bloque plegable de cada fragmento largo.

## g01 — ¿Cómo protejo un endpoint con OAuth2 en FastAPI y obtengo el usuario actual? Muéstrame la sección exacta.

Ruta esperada: `answer` · obtenida: `answer`

> **Nota para revisar g01:** la búsqueda trajo primera la página correcta (`tutorial/security/get-current-user/`), pero la respuesta cita otra (`tutorial/security/simple-oauth2/#update-the-dependencies`). Por eso falla el acierto de fuente (D40). Aquí juzgas solo si cada afirmación está apoyada por el contexto que vio el juez, no si eligió la mejor fuente.

### Respuesta del modelo

Para proteger un endpoint con OAuth2 en FastAPI y obtener el usuario actual, puedes usar dependencias que validen el token y obtengan el usuario autenticado. En la sección "Simple OAuth2 with Password and Bearer > Update the dependencies" se muestra un ejemplo completo donde se define una dependencia `get_current_user` que decodifica el token y obtiene el usuario, y otra dependencia `get_current_active_user` que verifica que el usuario esté activo. Luego, en el endpoint, se usa `Depends(get_current_active_user)` para protegerlo y obtener el usuario actual. Aquí un extracto clave:

```python
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    user = fake_decode_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@app.get("/users/me")
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return current_user
```

Esto protege el endpoint `/users/me` para que solo usuarios autenticados y activos puedan acceder y obtener su información.

Puedes ver el ejemplo completo en: https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/#update-the-dependencies

**Citas:**

- Simple OAuth2 with Password and Bearer > Update the dependencies · https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/#update-the-dependencies

### Afirmaciones del juez

| # | Afirmación | Juez | ¿De acuerdo? (sí/no) | Nota |
|---|---|---|---|---|
| 1 | Para proteger un endpoint con OAuth2 en FastAPI y obtener el usuario actual, puedes usar dependencias que validen el token y obtengan el usuario autenticado. | apoyada | | |
| 2 | En la sección "Simple OAuth2 with Password and Bearer > Update the dependencies" se muestra un ejemplo completo donde se define una dependencia `get_current_user` que decodifica el token y obtiene el usuario, y otra dependencia `get_current_active_user` que verifica que el usuario esté activo. | apoyada | | |
| 3 | Luego, en el endpoint, se usa `Depends(get_current_active_user)` para protegerlo y obtener el usuario actual. | apoyada | | |
| 4 | El código `async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]): ...` está en el contexto en la sección mencionada. | apoyada | | |
| 5 | El código `async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)],): ...` está en el contexto en la sección mencionada. | apoyada | | |
| 6 | El endpoint protegido `/users/me` con `Depends(get_current_active_user)` está en el contexto en la sección mencionada. | apoyada | | |
| 7 | Esto protege el endpoint `/users/me` para que solo usuarios autenticados y activos puedan acceder y obtener su información. | apoyada | | |
| 8 | Puedes ver el ejemplo completo en: https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/#update-the-dependencies | apoyada | | |

### Contexto que vio el modelo

**[1] Get Current User** · sección completa (get_section) · https://fastapi.tiangolo.com/tutorial/security/get-current-user/

````text
# Get Current User

In the previous chapter the security system (which is based on the dependency injection system) was giving the *path operation function* a `token` as a `str`:

```python
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.security import OAuth2PasswordBearer

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@app.get("/items/")
async def read_items(token: Annotated[str, Depends(oauth2_scheme)]):  # highlight
    return {"token": token}
```

But that is still not that useful.

Let's make it give us the current user.
````

<details>
<summary>Texto completo</summary>

````text
# Get Current User

In the previous chapter the security system (which is based on the dependency injection system) was giving the *path operation function* a `token` as a `str`:

```python
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.security import OAuth2PasswordBearer

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@app.get("/items/")
async def read_items(token: Annotated[str, Depends(oauth2_scheme)]):  # highlight
    return {"token": token}
```

But that is still not that useful.

Let's make it give us the current user.
````

</details>

**[2] Security Tools > OAuth2 Authentication** · fragmento · https://fastapi.tiangolo.com/reference/security/#oauth2-authentication

````text
## OAuth2 Authentication

::: fastapi.security.OAuth2

::: fastapi.security.OAuth2AuthorizationCodeBearer

::: fastapi.security.OAuth2PasswordBearer
````

<details>
<summary>Texto completo</summary>

````text
## OAuth2 Authentication

::: fastapi.security.OAuth2

::: fastapi.security.OAuth2AuthorizationCodeBearer

::: fastapi.security.OAuth2PasswordBearer
````

</details>

**[3] Simple OAuth2 with Password and Bearer > Update the dependencies** · fragmento · https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/#update-the-dependencies

````text
## Update the dependencies { #update-the-dependencies }

Now we are going to update our dependencies.

We want to get the `current_user` *only* if this user is active.

So, we create an additional dependency `get_current_active_user` that in turn uses `get_current_user` as a dependency.

Both of these dependencies will just return an HTTP error if the user doesn't exist, or is inactive.

So, in our endpoint, we will only get a user if the user exists, was correctly authenticated, and is active:

```python
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": "fakehashedsecret",
        "disabled": False,
    },
    "alice": {
        "username": "alice",
        "full_name": "Alice Wonderson",
        "email": "alice@example.com",
        "hashed_password": "fakehashedsecret2",
        "disabled": True,
    },
}

app = FastAPI()


def fake_hash_password(password: str):
    return "fakehashed" + password


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


def get_user(db, username: [...]
````

<details>
<summary>Texto completo</summary>

````text
## Update the dependencies { #update-the-dependencies }

Now we are going to update our dependencies.

We want to get the `current_user` *only* if this user is active.

So, we create an additional dependency `get_current_active_user` that in turn uses `get_current_user` as a dependency.

Both of these dependencies will just return an HTTP error if the user doesn't exist, or is inactive.

So, in our endpoint, we will only get a user if the user exists, was correctly authenticated, and is active:

```python
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": "fakehashedsecret",
        "disabled": False,
    },
    "alice": {
        "username": "alice",
        "full_name": "Alice Wonderson",
        "email": "alice@example.com",
        "hashed_password": "fakehashedsecret2",
        "disabled": True,
    },
}

app = FastAPI()


def fake_hash_password(password: str):
    return "fakehashed" + password


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


def fake_decode_token(token):
    # This doesn't provide any security at all
    # Check the next version
    user = get_user(fake_users_db, token)
    return user


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):  # highlight
    user = fake_decode_token(token)  # highlight
    if not user:  # highlight
        raise HTTPException(  # highlight
            status_code=status.HTTP_401_UNAUTHORIZED,  # highlight
            detail="Not authenticated",  # highlight
            headers={"WWW-Authenticate": "Bearer"},  # highlight
        )  # highlight
    return user  # highlight


async def get_current_active_user(  # highlight
    current_user: Annotated[User, Depends(get_current_user)],  # highlight
):  # highlight
    if current_user.disabled:  # highlight
        raise HTTPException(status_code=400, detail="Inactive user")  # highlight
    return current_user  # highlight


@app.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user_dict = fake_users_db.get(form_data.username)
    if not user_dict:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    user = UserInDB(**user_dict)
    hashed_password = fake_hash_password(form_data.password)
    if not hashed_password == user.hashed_password:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    return {"access_token": user.username, "token_type": "bearer"}


@app.get("/users/me")
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return current_user  # highlight
```

/// note

The additional header `WWW-Authenticate` with value `Bearer` we are returning here is also part of the spec.
````

</details>

**[4] Security - First Steps** · fragmento · https://fastapi.tiangolo.com/tutorial/security/first-steps/

````text
# Security - First Steps { #security-first-steps }

Let's imagine that you have your **backend** API in some domain.

And you have a **frontend** in another domain or in a different path of the same domain (or in a mobile application).

And you want to have a way for the frontend to authenticate with the backend, using a **username** and **password**.

We can use **OAuth2** to build that with **FastAPI**.

But let's save you the time of reading the full long specification just to find those little pieces of information you need.

Let's use the tools provided by **FastAPI** to handle security.
````

<details>
<summary>Texto completo</summary>

````text
# Security - First Steps { #security-first-steps }

Let's imagine that you have your **backend** API in some domain.

And you have a **frontend** in another domain or in a different path of the same domain (or in a mobile application).

And you want to have a way for the frontend to authenticate with the backend, using a **username** and **password**.

We can use **OAuth2** to build that with **FastAPI**.

But let's save you the time of reading the full long specification just to find those little pieces of information you need.

Let's use the tools provided by **FastAPI** to handle security.
````

</details>

**[5] Simple OAuth2 with Password and Bearer > Return the token** · fragmento · https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/#return-the-token

````text
## Return the token { #return-the-token }

The response of the `token` endpoint must be a JSON object.

It should have a `token_type`. In our case, as we are using "Bearer" tokens, the token type should be "`bearer`".

And it should have an `access_token`, with a string containing our access token.

For this simple example, we are going to just be completely insecure and return the same `username` as the token.

/// tip

In the next chapter, you will see a real secure implementation, with password hashing and <abbr title="JSON Web Tokens">JWT</abbr> tokens.

But for now, let's focus on the specific details we need.

///

```python
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": "fakehashedsecret",
        "disabled": False,
    },
    "alice": {
        "username": "alice",
        "full_name": "Alice Wonderson",
        "email": "alice@example.com",
        "hashed_password": "fakehashedsecret2",
        "disabled": True,
    },
}

app = FastAPI()


def fake_hash_password(password: str):
    return "fakehashed" + password


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: [...]
````

<details>
<summary>Texto completo</summary>

````text
## Return the token { #return-the-token }

The response of the `token` endpoint must be a JSON object.

It should have a `token_type`. In our case, as we are using "Bearer" tokens, the token type should be "`bearer`".

And it should have an `access_token`, with a string containing our access token.

For this simple example, we are going to just be completely insecure and return the same `username` as the token.

/// tip

In the next chapter, you will see a real secure implementation, with password hashing and <abbr title="JSON Web Tokens">JWT</abbr> tokens.

But for now, let's focus on the specific details we need.

///

```python
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": "fakehashedsecret",
        "disabled": False,
    },
    "alice": {
        "username": "alice",
        "full_name": "Alice Wonderson",
        "email": "alice@example.com",
        "hashed_password": "fakehashedsecret2",
        "disabled": True,
    },
}

app = FastAPI()


def fake_hash_password(password: str):
    return "fakehashed" + password


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


def fake_decode_token(token):
    # This doesn't provide any security at all
    # Check the next version
    user = get_user(fake_users_db, token)
    return user


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    user = fake_decode_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@app.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user_dict = fake_users_db.get(form_data.username)
    if not user_dict:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    user = UserInDB(**user_dict)
    hashed_password = fake_hash_password(form_data.password)
    if not hashed_password == user.hashed_password:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    return {"access_token": user.username, "token_type": "bearer"}  # highlight


@app.get("/users/me")
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return current_user
```

/// tip

By the spec, you should return a JSON with an `access_token` and a `token_type`, the same as in this example.

This is something that you have to do yourself in your code, and make sure you use those JSON keys.
````

</details>

## g02 — ¿Cómo declaro un parámetro de ruta con tipo int para que FastAPI lo valide automáticamente?

Ruta esperada: `answer` · obtenida: `answer`

### Respuesta del modelo

Para declarar un parámetro de ruta con tipo int y que FastAPI lo valide automáticamente, debes usar anotaciones de tipo estándar de Python en la función que maneja la ruta. Por ejemplo:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/items/{item_id}")
async def read_item(item_id: int):  # Aquí se declara item_id como int
    return {"item_id": item_id}
```

En este caso, `item_id` es declarado como un entero (`int`), y FastAPI validará automáticamente que el valor recibido en la ruta sea un entero.


**Citas:**

- Path Parameters > Path parameters with types · https://fastapi.tiangolo.com/tutorial/path-params/#path-parameters-with-types

### Afirmaciones del juez

| # | Afirmación | Juez | ¿De acuerdo? (sí/no) | Nota |
|---|---|---|---|---|
| 1 | Para declarar un parámetro de ruta con tipo int y que FastAPI lo valide automáticamente, debes usar anotaciones de tipo estándar de Python en la función que maneja la ruta. | apoyada | | |
| 2 | Debes usar anotaciones de tipo estándar de Python en la función que maneja la ruta. | apoyada | | |
| 3 | Ejemplo de código con FastAPI que declara un parámetro de ruta item_id como int: from fastapi import FastAPI app = FastAPI() @app.get("/items/{item_id}") async def read_item(item_id: int): return {"item_id": item_id} | apoyada | | |
| 4 | En este caso, item_id es declarado como un entero (int). | apoyada | | |
| 5 | FastAPI validará automáticamente que el valor recibido en la ruta sea un entero. | apoyada | | |

### Contexto que vio el modelo

**[1] Path Parameters > Path parameters with types** · sección completa (get_section) · https://fastapi.tiangolo.com/tutorial/path-params/#path-parameters-with-types

````text
## Path parameters with types

You can declare the type of a path parameter in the function, using standard Python type annotations:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/items/{item_id}")
async def read_item(item_id: int):  # highlight
    return {"item_id": item_id}
```

In this case, `item_id` is declared to be an `int`.

/// tip

This will give you editor support inside of your function, with error checks, completion, etc.

///
````

<details>
<summary>Texto completo</summary>

````text
## Path parameters with types

You can declare the type of a path parameter in the function, using standard Python type annotations:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/items/{item_id}")
async def read_item(item_id: int):  # highlight
    return {"item_id": item_id}
```

In this case, `item_id` is declared to be an `int`.

/// tip

This will give you editor support inside of your function, with error checks, completion, etc.

///
````

</details>

**[2] Path Parameters** · fragmento · https://fastapi.tiangolo.com/tutorial/path-params/

````text
# Path Parameters { #path-parameters }

You can declare path "parameters" or "variables" with the same syntax used by Python format strings:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/items/{item_id}")  # highlight
async def read_item(item_id):  # highlight
    return {"item_id": item_id}
```

The value of the path parameter `item_id` will be passed to your function as the argument `item_id`.

So, if you run this example and go to [http://127.0.0.1:8000/items/foo](http://127.0.0.1:8000/items/foo), you will see a response of:

```JSON
{"item_id":"foo"}
```
````

<details>
<summary>Texto completo</summary>

````text
# Path Parameters { #path-parameters }

You can declare path "parameters" or "variables" with the same syntax used by Python format strings:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/items/{item_id}")  # highlight
async def read_item(item_id):  # highlight
    return {"item_id": item_id}
```

The value of the path parameter `item_id` will be passed to your function as the argument `item_id`.

So, if you run this example and go to [http://127.0.0.1:8000/items/foo](http://127.0.0.1:8000/items/foo), you will see a response of:

```JSON
{"item_id":"foo"}
```
````

</details>

**[3] Path Parameters > OpenAPI support** · fragmento · https://fastapi.tiangolo.com/tutorial/path-params/#openapi-support

````text
### OpenAPI support { #openapi-support }

OpenAPI doesn't support a way to declare a *path parameter* to contain a *path* inside, as that could lead to scenarios that are difficult to test and define.

Nevertheless, you can still do it in **FastAPI**, using one of the internal tools from Starlette.

And the docs would still work, although not adding any documentation telling that the parameter should contain a path.
````

<details>
<summary>Texto completo</summary>

````text
### OpenAPI support { #openapi-support }

OpenAPI doesn't support a way to declare a *path parameter* to contain a *path* inside, as that could lead to scenarios that are difficult to test and define.

Nevertheless, you can still do it in **FastAPI**, using one of the internal tools from Starlette.

And the docs would still work, although not adding any documentation telling that the parameter should contain a path.
````

</details>

**[4] Query Parameters > Multiple path and query parameters** · fragmento · https://fastapi.tiangolo.com/tutorial/query-params/#multiple-path-and-query-parameters

````text
## Multiple path and query parameters { #multiple-path-and-query-parameters }

You can declare multiple path parameters and query parameters at the same time, **FastAPI** knows which is which.

And you don't have to declare them in any specific order.

They will be detected by name:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/users/{user_id}/items/{item_id}")  # highlight
async def read_user_item(
    user_id: int, item_id: str, q: str | None = None, short: bool = False  # highlight
):
    item = {"item_id": item_id, "owner_id": user_id}
    if q:
        item.update({"q": q})
    if not short:
        item.update(
            {"description": "This is an amazing item that has a long description"}
        )
    return item
```
````

<details>
<summary>Texto completo</summary>

````text
## Multiple path and query parameters { #multiple-path-and-query-parameters }

You can declare multiple path parameters and query parameters at the same time, **FastAPI** knows which is which.

And you don't have to declare them in any specific order.

They will be detected by name:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/users/{user_id}/items/{item_id}")  # highlight
async def read_user_item(
    user_id: int, item_id: str, q: str | None = None, short: bool = False  # highlight
):
    item = {"item_id": item_id, "owner_id": user_id}
    if q:
        item.update({"q": q})
    if not short:
        item.update(
            {"description": "This is an amazing item that has a long description"}
        )
    return item
```
````

</details>

**[5] Path Parameters > Path convertor** · fragmento · https://fastapi.tiangolo.com/tutorial/path-params/#path-convertor

````text
### Path convertor { #path-convertor }

Using an option directly from Starlette you can declare a *path parameter* containing a *path* using a URL like:

```
/files/{file_path:path}
```

In this case, the name of the parameter is `file_path`, and the last part, `:path`, tells it that the parameter should match any *path*.

So, you can use it with:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/files/{file_path:path}")  # highlight
async def read_file(file_path: str):
    return {"file_path": file_path}
```

/// tip

You might need the parameter to contain `/home/johndoe/myfile.txt`, with a leading slash (`/`).

In that case, the URL would be: `/files//home/johndoe/myfile.txt`, with a double slash (`//`) between `files` and `home`.

///
````

<details>
<summary>Texto completo</summary>

````text
### Path convertor { #path-convertor }

Using an option directly from Starlette you can declare a *path parameter* containing a *path* using a URL like:

```
/files/{file_path:path}
```

In this case, the name of the parameter is `file_path`, and the last part, `:path`, tells it that the parameter should match any *path*.

So, you can use it with:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/files/{file_path:path}")  # highlight
async def read_file(file_path: str):
    return {"file_path": file_path}
```

/// tip

You might need the parameter to contain `/home/johndoe/myfile.txt`, with a leading slash (`/`).

In that case, the URL would be: `/files//home/johndoe/myfile.txt`, with a double slash (`//`) between `files` and `home`.

///
````

</details>

## g10 — How do I declare a request body using a Pydantic model?

Ruta esperada: `answer` · obtenida: `answer`

### Respuesta del modelo

To declare a request body using a Pydantic model in FastAPI, you define a Pydantic model class with the fields you expect in the request body, and then use that model as a parameter in your path operation function. FastAPI will automatically recognize that the parameter should be taken from the request body. For example:

```python
from fastapi import FastAPI
from pydantic import BaseModel

class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None

app = FastAPI()

@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item):
    return {"item_id": item_id, **item.model_dump()}
```

In this example, the `item` parameter is a Pydantic model and will be taken from the request body, while `item_id` is a path parameter taken from the URL path.

**Citas:**

- Request Body > Request body + path parameters · https://fastapi.tiangolo.com/tutorial/body/#request-body-path-parameters

### Afirmaciones del juez

| # | Afirmación | Juez | ¿De acuerdo? (sí/no) | Nota |
|---|---|---|---|---|
| 1 | To declare a request body using a Pydantic model in FastAPI, you define a Pydantic model class with the fields you expect in the request body | apoyada | | |
| 2 | Then use that model as a parameter in your path operation function | apoyada | | |
| 3 | FastAPI will automatically recognize that the parameter should be taken from the request body | apoyada | | |
| 4 | Example code defining Item model with fields name, description, price, tax | apoyada | | |
| 5 | Example code shows app.put decorator with path /items/{item_id} | apoyada | | |
| 6 | Example code shows async def update_item(item_id: int, item: Item) function | apoyada | | |
| 7 | Function returns dictionary with item_id and item.model_dump() | apoyada | | |
| 8 | In this example, the item parameter is a Pydantic model and will be taken from the request body | apoyada | | |
| 9 | item_id is a path parameter taken from the URL path | apoyada | | |

### Contexto que vio el modelo

**[1] Request Body** · sección completa (get_section) · https://fastapi.tiangolo.com/tutorial/body/

````text
# Request Body

When you need to send data from a client (let's say, a browser) to your API, you send it as a **request body**.

A **request** body is data sent by the client to your API. A **response** body is the data your API sends to the client.

Your API almost always has to send a **response** body. But clients don't necessarily need to send **request bodies** all the time, sometimes they only request a path, maybe with some query parameters, but don't send a body.

To declare a **request** body, you use [Pydantic](https://pydantic.dev/docs/) models with all their power and benefits.

/// note

To send data, you should use one of: `POST` (the most common), `PUT`, `DELETE` or `PATCH`.

Sending a body with a `GET` request has an undefined behavior in the specifications, nevertheless, it is supported by FastAPI, only for very complex/extreme use cases.

As it is discouraged, the interactive docs with Swagger UI won't show the documentation for the body when using `GET`, and proxies in the middle might not support it.

///
````

<details>
<summary>Texto completo</summary>

````text
# Request Body

When you need to send data from a client (let's say, a browser) to your API, you send it as a **request body**.

A **request** body is data sent by the client to your API. A **response** body is the data your API sends to the client.

Your API almost always has to send a **response** body. But clients don't necessarily need to send **request bodies** all the time, sometimes they only request a path, maybe with some query parameters, but don't send a body.

To declare a **request** body, you use [Pydantic](https://pydantic.dev/docs/) models with all their power and benefits.

/// note

To send data, you should use one of: `POST` (the most common), `PUT`, `DELETE` or `PATCH`.

Sending a body with a `GET` request has an undefined behavior in the specifications, nevertheless, it is supported by FastAPI, only for very complex/extreme use cases.

As it is discouraged, the interactive docs with Swagger UI won't show the documentation for the body when using `GET`, and proxies in the middle might not support it.

///
````

</details>

**[2] Request Body > Without Pydantic** · fragmento · https://fastapi.tiangolo.com/tutorial/body/#without-pydantic

````text
## Without Pydantic { #without-pydantic }

If you don't want to use Pydantic models, you can also use **Body** parameters. See the docs for [Body - Multiple Parameters: Singular values in body](body-multiple-params.md#singular-values-in-body).
````

<details>
<summary>Texto completo</summary>

````text
## Without Pydantic { #without-pydantic }

If you don't want to use Pydantic models, you can also use **Body** parameters. See the docs for [Body - Multiple Parameters: Singular values in body](body-multiple-params.md#singular-values-in-body).
````

</details>

**[3] Request Body > Request body + path parameters** · fragmento · https://fastapi.tiangolo.com/tutorial/body/#request-body-path-parameters

````text
## Request body + path parameters { #request-body-path-parameters }

You can declare path parameters and request body at the same time.

**FastAPI** will recognize that the function parameters that match path parameters should be **taken from the path**, and that function parameters that are declared to be Pydantic models should be **taken from the request body**.

```python
from fastapi import FastAPI
from pydantic import BaseModel


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None


app = FastAPI()


@app.put("/items/{item_id}")  # highlight
async def update_item(item_id: int, item: Item):  # highlight
    return {"item_id": item_id, **item.model_dump()}
```
````

<details>
<summary>Texto completo</summary>

````text
## Request body + path parameters { #request-body-path-parameters }

You can declare path parameters and request body at the same time.

**FastAPI** will recognize that the function parameters that match path parameters should be **taken from the path**, and that function parameters that are declared to be Pydantic models should be **taken from the request body**.

```python
from fastapi import FastAPI
from pydantic import BaseModel


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None


app = FastAPI()


@app.put("/items/{item_id}")  # highlight
async def update_item(item_id: int, item: Item):  # highlight
    return {"item_id": item_id, **item.model_dump()}
```
````

</details>

**[4] Form Models > Pydantic Models for Forms** · fragmento · https://fastapi.tiangolo.com/tutorial/request-form-models/#pydantic-models-for-forms

````text
## Pydantic Models for Forms { #pydantic-models-for-forms }

You just need to declare a **Pydantic model** with the fields you want to receive as **form fields**, and then declare the parameter as `Form`:

```python
from typing import Annotated

from fastapi import FastAPI, Form
from pydantic import BaseModel

app = FastAPI()


class FormData(BaseModel):  # highlight
    username: str  # highlight
    password: str  # highlight


@app.post("/login/")
async def login(data: Annotated[FormData, Form()]):  # highlight
    return data
```

**FastAPI** will **extract** the data for **each field** from the **form data** in the request and give you the Pydantic model you defined.

For [HTML checkboxes](request-forms.md#boolean-form-fields), declare boolean fields with a default of `False`.
````

<details>
<summary>Texto completo</summary>

````text
## Pydantic Models for Forms { #pydantic-models-for-forms }

You just need to declare a **Pydantic model** with the fields you want to receive as **form fields**, and then declare the parameter as `Form`:

```python
from typing import Annotated

from fastapi import FastAPI, Form
from pydantic import BaseModel

app = FastAPI()


class FormData(BaseModel):  # highlight
    username: str  # highlight
    password: str  # highlight


@app.post("/login/")
async def login(data: Annotated[FormData, Form()]):  # highlight
    return data
```

**FastAPI** will **extract** the data for **each field** from the **form data** in the request and give you the Pydantic model you defined.

For [HTML checkboxes](request-forms.md#boolean-form-fields), declare boolean fields with a default of `False`.
````

</details>

**[5] Body - Nested Models** · fragmento · https://fastapi.tiangolo.com/tutorial/body-nested-models/

````text
# Body - Nested Models { #body-nested-models }

With **FastAPI**, you can define, validate, document, and use arbitrarily deeply nested models (thanks to Pydantic).
````

<details>
<summary>Texto completo</summary>

````text
# Body - Nested Models { #body-nested-models }

With **FastAPI**, you can define, validate, document, and use arbitrarily deeply nested models (thanks to Pydantic).
````

</details>

## g12 — How do I run code at startup and shutdown with the lifespan parameter?

Ruta esperada: `answer` · obtenida: `answer`

### Respuesta del modelo

You can run code at startup and shutdown by defining a lifespan function using the `lifespan` parameter of the `FastAPI` app. This function should be an async context manager that uses `yield` to separate startup and shutdown logic. Code before the `yield` runs once before the application starts receiving requests (startup), and code after the `yield` runs once after the application finishes handling requests (shutdown). For example, you can load resources like machine learning models before `yield` and clean them up after `yield`.

Here's a simplified example:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

ml_models = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load resources
    ml_models["answer_to_everything"] = lambda x: x * 42
    yield
    # Shutdown: clean up resources
    ml_models.clear()

app = FastAPI(lifespan=lifespan)
```

This approach is recommended because it keeps startup and shutdown logic together and allows sharing variables easily.


**Citas:**

- Lifespan Events > Lifespan · https://fastapi.tiangolo.com/advanced/events/#lifespan
- Lifespan Events > `startup` and `shutdown` together · https://fastapi.tiangolo.com/advanced/events/#startup-and-shutdown-together

### Afirmaciones del juez

| # | Afirmación | Juez | ¿De acuerdo? (sí/no) | Nota |
|---|---|---|---|---|
| 1 | You can run code at startup and shutdown by defining a lifespan function using the `lifespan` parameter of the `FastAPI` app. | apoyada | | |
| 2 | This function should be an async context manager that uses `yield` to separate startup and shutdown logic. | apoyada | | |
| 3 | Code before the `yield` runs once before the application starts receiving requests (startup). | apoyada | | |
| 4 | Code after the `yield` runs once after the application finishes handling requests (shutdown). | apoyada | | |
| 5 | For example, you can load resources like machine learning models before `yield` and clean them up after `yield`. | apoyada | | |
| 6 | The example code imports `asynccontextmanager` from `contextlib` and `FastAPI` from `fastapi`. | apoyada | | |
| 7 | The example code defines `ml_models` as an empty dictionary. | apoyada | | |
| 8 | The example defines an async context manager function `lifespan` that loads a lambda function into `ml_models` before `yield` and clears `ml_models` after `yield`. | apoyada | | |
| 9 | The example creates a `FastAPI` app with `lifespan=lifespan`. | apoyada | | |
| 10 | This approach is recommended because it keeps startup and shutdown logic together and allows sharing variables easily. | apoyada | | |

### Contexto que vio el modelo

**[1] Lifespan Events > `startup` and `shutdown` together** · sección completa (get_section) · https://fastapi.tiangolo.com/advanced/events/#startup-and-shutdown-together

````text
### `startup` and `shutdown` together

There's a high chance that the logic for your *startup* and *shutdown* is connected, you might want to start something and then finish it, acquire a resource and then release it, etc.

Doing that in separate functions that don't share logic or variables together is more difficult as you would need to store values in global variables or similar tricks.

Because of that, it's now recommended to instead use the `lifespan` as explained above.
````

<details>
<summary>Texto completo</summary>

````text
### `startup` and `shutdown` together

There's a high chance that the logic for your *startup* and *shutdown* is connected, you might want to start something and then finish it, acquire a resource and then release it, etc.

Doing that in separate functions that don't share logic or variables together is more difficult as you would need to store values in global variables or similar tricks.

Because of that, it's now recommended to instead use the `lifespan` as explained above.
````

</details>

**[2] Lifespan Events** · fragmento · https://fastapi.tiangolo.com/advanced/events/

````text
# Lifespan Events { #lifespan-events }

You can define logic (code) that should be executed before the application **starts up**. This means that this code will be executed **once**, **before** the application **starts receiving requests**.

The same way, you can define logic (code) that should be executed when the application is **shutting down**. In this case, this code will be executed **once**, **after** having handled possibly **many requests**.

Because this code is executed before the application **starts** taking requests, and right after it **finishes** handling requests, it covers the whole application **lifespan** (the word "lifespan" will be important in a second 😉).

This can be very useful for setting up **resources** that you need to use for the whole app, and that are **shared** among requests, and/or that you need to **clean up** afterwards. For example, a database connection pool, or loading a shared machine learning model.
````

<details>
<summary>Texto completo</summary>

````text
# Lifespan Events { #lifespan-events }

You can define logic (code) that should be executed before the application **starts up**. This means that this code will be executed **once**, **before** the application **starts receiving requests**.

The same way, you can define logic (code) that should be executed when the application is **shutting down**. In this case, this code will be executed **once**, **after** having handled possibly **many requests**.

Because this code is executed before the application **starts** taking requests, and right after it **finishes** handling requests, it covers the whole application **lifespan** (the word "lifespan" will be important in a second 😉).

This can be very useful for setting up **resources** that you need to use for the whole app, and that are **shared** among requests, and/or that you need to **clean up** afterwards. For example, a database connection pool, or loading a shared machine learning model.
````

</details>

**[3] Lifespan Events > Lifespan** · fragmento · https://fastapi.tiangolo.com/advanced/events/#lifespan

````text
## Lifespan { #lifespan }

You can define this *startup* and *shutdown* logic using the `lifespan` parameter of the `FastAPI` app, and a "context manager" (I'll show you what that is in a second).

Let's start with an example and then see it in detail.

We create an async function `lifespan()` with `yield` like this:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI


def fake_answer_to_everything_ml_model(x: float):
    return x * 42


ml_models = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML model
    ml_models["answer_to_everything"] = fake_answer_to_everything_ml_model  # highlight
    yield
    # Clean up the ML models and release the resources
    ml_models.clear()  # highlight


app = FastAPI(lifespan=lifespan)


@app.get("/predict")
async def predict(x: float):
    result = ml_models["answer_to_everything"](x)
    return {"result": result}
```

Here we are simulating the expensive *startup* operation of loading the model by putting the (fake) model function in the dictionary with machine learning models before the `yield`. This code will be executed **before** the application **starts taking requests**, during the *startup*.

And then, right after the `yield`, we unload the model. This code will be executed **after** the application **finishes handling requests**, right before the *shutdown*. This could, for example, release resources like memory or a GPU.

/// tip

The `shutdown` would happen when you a [...]
````

<details>
<summary>Texto completo</summary>

````text
## Lifespan { #lifespan }

You can define this *startup* and *shutdown* logic using the `lifespan` parameter of the `FastAPI` app, and a "context manager" (I'll show you what that is in a second).

Let's start with an example and then see it in detail.

We create an async function `lifespan()` with `yield` like this:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI


def fake_answer_to_everything_ml_model(x: float):
    return x * 42


ml_models = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML model
    ml_models["answer_to_everything"] = fake_answer_to_everything_ml_model  # highlight
    yield
    # Clean up the ML models and release the resources
    ml_models.clear()  # highlight


app = FastAPI(lifespan=lifespan)


@app.get("/predict")
async def predict(x: float):
    result = ml_models["answer_to_everything"](x)
    return {"result": result}
```

Here we are simulating the expensive *startup* operation of loading the model by putting the (fake) model function in the dictionary with machine learning models before the `yield`. This code will be executed **before** the application **starts taking requests**, during the *startup*.

And then, right after the `yield`, we unload the model. This code will be executed **after** the application **finishes handling requests**, right before the *shutdown*. This could, for example, release resources like memory or a GPU.

/// tip

The `shutdown` would happen when you are **stopping** the application.

Maybe you need to start a new version, or you just got tired of running it. 🤷

///
````

</details>

**[4] Lifespan Events > Technical Details** · fragmento · https://fastapi.tiangolo.com/advanced/events/#technical-details

````text
## Technical Details { #technical-details }

Just a technical detail for the curious nerds. 🤓

Underneath, in the ASGI technical specification, this is part of the [Lifespan Protocol](https://asgi.readthedocs.io/en/latest/specs/lifespan.html), and it defines events called `startup` and `shutdown`.

/// note

You can read more about the Starlette `lifespan` handlers in [Starlette's  Lifespan' docs](https://starlette.dev/lifespan/).

Including how to handle lifespan state that can be used in other areas of your code.

///
````

<details>
<summary>Texto completo</summary>

````text
## Technical Details { #technical-details }

Just a technical detail for the curious nerds. 🤓

Underneath, in the ASGI technical specification, this is part of the [Lifespan Protocol](https://asgi.readthedocs.io/en/latest/specs/lifespan.html), and it defines events called `startup` and `shutdown`.

/// note

You can read more about the Starlette `lifespan` handlers in [Starlette's  Lifespan' docs](https://starlette.dev/lifespan/).

Including how to handle lifespan state that can be used in other areas of your code.

///
````

</details>

**[5] Deployments Concepts > Running on Startup** · fragmento · https://fastapi.tiangolo.com/deployment/concepts/#running-on-startup

````text
## Running on Startup { #running-on-startup }

In most cases, when you create a web API, you want it to be **always running**, uninterrupted, so that your clients can always access it. This is of course, unless you have a specific reason why you want it to run only in certain situations, but most of the time you want it constantly running and **available**.
````

<details>
<summary>Texto completo</summary>

````text
## Running on Startup { #running-on-startup }

In most cases, when you create a web API, you want it to be **always running**, uninterrupted, so that your clients can always access it. This is of course, unless you have a specific reason why you want it to run only in certain situations, but most of the time you want it constantly running and **available**.
````

</details>

## g16 — How do I add a custom header to the response and also set a cookie on that same response?

Ruta esperada: `answer` · obtenida: `answer`

### Respuesta del modelo

You can add a custom header and set a cookie on the same response by declaring a parameter of type `Response` in your path operation function. Then, set the custom header directly on the `response.headers` dictionary and set the cookie using the `response.set_cookie()` method. Finally, return the response content as usual. Here's an example combining both:

```python
from fastapi import FastAPI, Response

app = FastAPI()

@app.get("/example/")
def example(response: Response):
    response.headers["X-Custom-Header"] = "custom value"
    response.set_cookie(key="mycookie", value="cookievalue")
    return {"message": "Hello with custom header and cookie"}
```

This way, FastAPI will include both the custom header and the cookie in the final response along with the returned content.

**Citas:**

- Response Headers > Use a `Response` parameter · https://fastapi.tiangolo.com/advanced/response-headers/#use-a-response-parameter
- Response Cookies > Use a `Response` parameter · https://fastapi.tiangolo.com/advanced/response-cookies/#use-a-response-parameter

### Afirmaciones del juez

| # | Afirmación | Juez | ¿De acuerdo? (sí/no) | Nota |
|---|---|---|---|---|
| 1 | You can add a custom header and set a cookie on the same response by declaring a parameter of type `Response` in your path operation function. | apoyada | | |
| 2 | Then, set the custom header directly on the `response.headers` dictionary. | apoyada | | |
| 3 | Set the cookie using the `response.set_cookie()` method. | apoyada | | |
| 4 | Return the response content as usual. | apoyada | | |
| 5 | Example code with FastAPI importing Response, defining app, and a path operation function that sets a custom header and a cookie on the response and returns a dict. | apoyada | | |
| 6 | FastAPI will include both the custom header and the cookie in the final response along with the returned content. | apoyada | | |

### Contexto que vio el modelo

**[1] Response Headers > Custom Headers** · sección completa (get_section) · https://fastapi.tiangolo.com/advanced/response-headers/#custom-headers

````text
## Custom Headers

Keep in mind that custom proprietary headers can be added [using the `X-` prefix](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers).

But if you have custom headers that you want a client in a browser to be able to see, you need to add them to your CORS configurations (read more in [CORS (Cross-Origin Resource Sharing)](../tutorial/cors.md)), using the parameter `expose_headers` documented in [Starlette's CORS docs](https://starlette.dev/middleware/#corsmiddleware).
````

<details>
<summary>Texto completo</summary>

````text
## Custom Headers

Keep in mind that custom proprietary headers can be added [using the `X-` prefix](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers).

But if you have custom headers that you want a client in a browser to be able to see, you need to add them to your CORS configurations (read more in [CORS (Cross-Origin Resource Sharing)](../tutorial/cors.md)), using the parameter `expose_headers` documented in [Starlette's CORS docs](https://starlette.dev/middleware/#corsmiddleware).
````

</details>

**[2] Handling Errors > Add custom headers** · fragmento · https://fastapi.tiangolo.com/tutorial/handling-errors/#add-custom-headers

````text
## Add custom headers { #add-custom-headers }

There are some situations where it's useful to be able to add custom headers to the HTTP error. For example, for some types of security.

You probably won't need to use it directly in your code.

But in case you needed it for an advanced scenario, you can add custom headers:

```python
from fastapi import FastAPI, HTTPException

app = FastAPI()

items = {"foo": "The Foo Wrestlers"}


@app.get("/items-header/{item_id}")
async def read_item_header(item_id: str):
    if item_id not in items:
        raise HTTPException(
            status_code=404,
            detail="Item not found",
            headers={"X-Error": "There goes my error"},  # highlight
        )
    return {"item": items[item_id]}
```
````

<details>
<summary>Texto completo</summary>

````text
## Add custom headers { #add-custom-headers }

There are some situations where it's useful to be able to add custom headers to the HTTP error. For example, for some types of security.

You probably won't need to use it directly in your code.

But in case you needed it for an advanced scenario, you can add custom headers:

```python
from fastapi import FastAPI, HTTPException

app = FastAPI()

items = {"foo": "The Foo Wrestlers"}


@app.get("/items-header/{item_id}")
async def read_item_header(item_id: str):
    if item_id not in items:
        raise HTTPException(
            status_code=404,
            detail="Item not found",
            headers={"X-Error": "There goes my error"},  # highlight
        )
    return {"item": items[item_id]}
```
````

</details>

**[3] Response Headers > Use a `Response` parameter** · fragmento · https://fastapi.tiangolo.com/advanced/response-headers/#use-a-response-parameter

````text
## Use a `Response` parameter { #use-a-response-parameter }

You can declare a parameter of type `Response` in your *path operation function* (as you can do for cookies).

And then you can set headers in that *temporary* response object.

```python
from fastapi import FastAPI, Response  # highlight

app = FastAPI()


@app.get("/headers-and-object/")
def get_headers(response: Response):  # highlight
    response.headers["X-Cat-Dog"] = "alone in the world"  # highlight
    return {"message": "Hello World"}
```

And then you can return any object you need, as you normally would (a `dict`, a database model, etc).

And if you declared a `response_model`, it will still be used to filter and convert the object you returned.

**FastAPI** will use that *temporary* response to extract the headers (also cookies and status code), and will put them in the final response that contains the value you returned, filtered by any `response_model`.

You can also declare the `Response` parameter in dependencies, and set headers (and cookies) in them.
````

<details>
<summary>Texto completo</summary>

````text
## Use a `Response` parameter { #use-a-response-parameter }

You can declare a parameter of type `Response` in your *path operation function* (as you can do for cookies).

And then you can set headers in that *temporary* response object.

```python
from fastapi import FastAPI, Response  # highlight

app = FastAPI()


@app.get("/headers-and-object/")
def get_headers(response: Response):  # highlight
    response.headers["X-Cat-Dog"] = "alone in the world"  # highlight
    return {"message": "Hello World"}
```

And then you can return any object you need, as you normally would (a `dict`, a database model, etc).

And if you declared a `response_model`, it will still be used to filter and convert the object you returned.

**FastAPI** will use that *temporary* response to extract the headers (also cookies and status code), and will put them in the final response that contains the value you returned, filtered by any `response_model`.

You can also declare the `Response` parameter in dependencies, and set headers (and cookies) in them.
````

</details>

**[4] Response Cookies > Use a `Response` parameter** · fragmento · https://fastapi.tiangolo.com/advanced/response-cookies/#use-a-response-parameter

````text
## Use a `Response` parameter { #use-a-response-parameter }

You can declare a parameter of type `Response` in your *path operation function*.

And then you can set cookies in that *temporary* response object.

```python
from fastapi import FastAPI, Response  # highlight

app = FastAPI()


@app.post("/cookie-and-object/")
def create_cookie(response: Response):
    response.set_cookie(key="fakesession", value="fake-cookie-session-value")  # highlight
    return {"message": "Come to the dark side, we have cookies"}  # highlight
```

And then you can return any object you need, as you normally would (a `dict`, a database model, etc).

And if you declared a `response_model`, it will still be used to filter and convert the object you returned.

**FastAPI** will use that *temporary* response to extract the cookies (also headers and status code), and will put them in the final response that contains the value you returned, filtered by any `response_model`.

You can also declare the `Response` parameter in dependencies, and set cookies (and headers) in them.
````

<details>
<summary>Texto completo</summary>

````text
## Use a `Response` parameter { #use-a-response-parameter }

You can declare a parameter of type `Response` in your *path operation function*.

And then you can set cookies in that *temporary* response object.

```python
from fastapi import FastAPI, Response  # highlight

app = FastAPI()


@app.post("/cookie-and-object/")
def create_cookie(response: Response):
    response.set_cookie(key="fakesession", value="fake-cookie-session-value")  # highlight
    return {"message": "Come to the dark side, we have cookies"}  # highlight
```

And then you can return any object you need, as you normally would (a `dict`, a database model, etc).

And if you declared a `response_model`, it will still be used to filter and convert the object you returned.

**FastAPI** will use that *temporary* response to extract the cookies (also headers and status code), and will put them in the final response that contains the value you returned, filtered by any `response_model`.

You can also declare the `Response` parameter in dependencies, and set cookies (and headers) in them.
````

</details>

**[5] Header Parameters** · fragmento · https://fastapi.tiangolo.com/tutorial/header-params/

````text
# Header Parameters { #header-parameters }

You can define Header parameters the same way you define `Query`, `Path` and `Cookie` parameters.
````

<details>
<summary>Texto completo</summary>

````text
# Header Parameters { #header-parameters }

You can define Header parameters the same way you define `Query`, `Path` and `Cookie` parameters.
````

</details>

## g30 — ¿Qué cambios incompatibles trae FastAPI 1.0 y en qué fecha se publica?

Ruta esperada: `either` · obtenida: `answer`

### Respuesta del modelo

No se proporciona información específica sobre los cambios incompatibles que trae FastAPI 1.0 ni la fecha de su publicación en los fragmentos de contexto proporcionados. Solo se menciona que las versiones actuales están por debajo de 1.0.0 y que cualquier versión menor a 1.0.0 podría tener cambios incompatibles, siguiendo las convenciones de Semantic Versioning, pero no se detalla qué cambios específicos ocurrirán en la versión 1.0 ni cuándo será lanzada.

**Citas:**

- (ninguna)

### Afirmaciones del juez

| # | Afirmación | Juez | ¿De acuerdo? (sí/no) | Nota |
|---|---|---|---|---|
| 1 | No se proporciona información específica sobre los cambios incompatibles que trae FastAPI 1.0 ni la fecha de su publicación en los fragmentos de contexto proporcionados. | apoyada | | |
| 2 | Solo se menciona que las versiones actuales están por debajo de 1.0.0 y que cualquier versión menor a 1.0.0 podría tener cambios incompatibles, siguiendo las convenciones de Semantic Versioning. | apoyada | | |
| 3 | No se detalla qué cambios específicos ocurrirán en la versión 1.0 ni cuándo será lanzada. | apoyada | | |

### Contexto que vio el modelo

**[1] About FastAPI versions** · sección completa (get_section) · https://fastapi.tiangolo.com/deployment/versions/

````text
# About FastAPI versions

**FastAPI** is already being used in production in many applications and systems. And the test coverage is kept at 100%. But its development is still moving quickly.

New features are added frequently, bugs are fixed regularly, and the code is still continuously improving.

That's why the current versions are still `0.x.x`, this reflects that each version could potentially have breaking changes. This follows the [Semantic Versioning](https://semver.org/) conventions.

You can create production applications with **FastAPI** right now (and you have probably been doing it for some time), you just have to make sure that you use a version that works correctly with the rest of your code.
````

<details>
<summary>Texto completo</summary>

````text
# About FastAPI versions

**FastAPI** is already being used in production in many applications and systems. And the test coverage is kept at 100%. But its development is still moving quickly.

New features are added frequently, bugs are fixed regularly, and the code is still continuously improving.

That's why the current versions are still `0.x.x`, this reflects that each version could potentially have breaking changes. This follows the [Semantic Versioning](https://semver.org/) conventions.

You can create production applications with **FastAPI** right now (and you have probably been doing it for some time), you just have to make sure that you use a version that works correctly with the rest of your code.
````

</details>

**[2] Dependencies > **FastAPI** compatibility** · fragmento · https://fastapi.tiangolo.com/tutorial/dependencies/#fastapi-compatibility

````text
## **FastAPI** compatibility { #fastapi-compatibility }

The simplicity of the dependency injection system makes **FastAPI** compatible with:

* all the relational databases
* NoSQL databases
* external packages
* external APIs
* authentication and authorization systems
* API usage monitoring systems
* response data injection systems
* etc.
````

<details>
<summary>Texto completo</summary>

````text
## **FastAPI** compatibility { #fastapi-compatibility }

The simplicity of the dependency injection system makes **FastAPI** compatible with:

* all the relational databases
* NoSQL databases
* external packages
* external APIs
* authentication and authorization systems
* API usage monitoring systems
* response data injection systems
* etc.
````

</details>

**[3] Features > FastAPI features** · fragmento · https://fastapi.tiangolo.com/features/#fastapi-features

````text
## FastAPI features { #fastapi-features }

**FastAPI** gives you the following:
````

<details>
<summary>Texto completo</summary>

````text
## FastAPI features { #fastapi-features }

**FastAPI** gives you the following:
````

</details>

**[4] About FastAPI versions > About versions** · fragmento · https://fastapi.tiangolo.com/deployment/versions/#about-versions

````text
## About versions { #about-versions }

Following the Semantic Versioning conventions, any version below `1.0.0` could potentially add breaking changes.

FastAPI also follows the convention that any "PATCH" version change is for bug fixes and non-breaking changes.

/// tip

The "PATCH" is the last number, for example, in `0.2.3`, the PATCH version is `3`.

///

So, you should be able to pin to a version like:

```txt
fastapi>=0.45.0,<0.46.0
```

Breaking changes and new features are added in "MINOR" versions.

/// tip

The "MINOR" is the number in the middle, for example, in `0.2.3`, the MINOR version is `2`.

///
````

<details>
<summary>Texto completo</summary>

````text
## About versions { #about-versions }

Following the Semantic Versioning conventions, any version below `1.0.0` could potentially add breaking changes.

FastAPI also follows the convention that any "PATCH" version change is for bug fixes and non-breaking changes.

/// tip

The "PATCH" is the last number, for example, in `0.2.3`, the PATCH version is `3`.

///

So, you should be able to pin to a version like:

```txt
fastapi>=0.45.0,<0.46.0
```

Breaking changes and new features are added in "MINOR" versions.

/// tip

The "MINOR" is the number in the middle, for example, in `0.2.3`, the MINOR version is `2`.

///
````

</details>

**[5] Migrate from Pydantic v1 to Pydantic v2** · fragmento · https://fastapi.tiangolo.com/how-to/migrate-from-pydantic-v1-to-pydantic-v2/

````text
# Migrate from Pydantic v1 to Pydantic v2 { #migrate-from-pydantic-v1-to-pydantic-v2 }

If you have an old FastAPI app, you might be using Pydantic version 1.

FastAPI version 0.100.0 had support for either Pydantic v1 or v2. It would use whichever you had installed.

FastAPI version 0.119.0 introduced partial support for Pydantic v1 from inside of Pydantic v2 (as `pydantic.v1`), to facilitate the migration to v2.

FastAPI 0.126.0 dropped support for Pydantic v1, while still supporting `pydantic.v1` for a little while.

FastAPI 0.128.0 dropped support for `pydantic.v1` as well, so the latest versions of FastAPI require Pydantic v2.

/// warning

The Pydantic team stopped support for Pydantic v1 for the latest versions of Python, starting with **Python 3.14**.

This includes `pydantic.v1`, which is no longer supported in Python 3.14 and above.

If you want to use the latest features of Python, you will need to make sure you use Pydantic v2.

///

If you have an old FastAPI app with Pydantic v1, here I'll show you how to migrate it to Pydantic v2, and the **features in FastAPI 0.119.0** to help you with a gradual migration.
````

<details>
<summary>Texto completo</summary>

````text
# Migrate from Pydantic v1 to Pydantic v2 { #migrate-from-pydantic-v1-to-pydantic-v2 }

If you have an old FastAPI app, you might be using Pydantic version 1.

FastAPI version 0.100.0 had support for either Pydantic v1 or v2. It would use whichever you had installed.

FastAPI version 0.119.0 introduced partial support for Pydantic v1 from inside of Pydantic v2 (as `pydantic.v1`), to facilitate the migration to v2.

FastAPI 0.126.0 dropped support for Pydantic v1, while still supporting `pydantic.v1` for a little while.

FastAPI 0.128.0 dropped support for `pydantic.v1` as well, so the latest versions of FastAPI require Pydantic v2.

/// warning

The Pydantic team stopped support for Pydantic v1 for the latest versions of Python, starting with **Python 3.14**.

This includes `pydantic.v1`, which is no longer supported in Python 3.14 and above.

If you want to use the latest features of Python, you will need to make sure you use Pydantic v2.

///

If you have an old FastAPI app with Pydantic v1, here I'll show you how to migrate it to Pydantic v2, and the **features in FastAPI 0.119.0** to help you with a gradual migration.
````

</details>

## g03 — ¿Cómo hago que un endpoint de creación devuelva el código de estado 201 en lugar de 200?

Ruta esperada: `answer` · obtenida: `answer`

### Respuesta del modelo

Para que un endpoint de creación devuelva el código de estado 201 en lugar de 200, debes usar el parámetro `status_code` en el decorador del path operation, por ejemplo `@app.post("/items/", status_code=201)`. Esto hará que la respuesta tenga el código 201 y también se documente así en el esquema OpenAPI. Alternativamente, puedes usar la constante `status.HTTP_201_CREATED` importándola desde `fastapi.status` para mayor claridad. Por ejemplo:

```python
from fastapi import FastAPI, status

app = FastAPI()

@app.post("/items/", status_code=status.HTTP_201_CREATED)
async def create_item(item: Item):
    return item
```

Esto hará que el endpoint devuelva el código 201 en la respuesta.


**Citas:**

- Response Status Code · https://fastapi.tiangolo.com/tutorial/response-status-code/
- Path Operation Configuration > Response Status Code · https://fastapi.tiangolo.com/tutorial/path-operation-configuration/#response-status-code
- Status Codes · https://fastapi.tiangolo.com/reference/status/

### Afirmaciones del juez

| # | Afirmación | Juez | ¿De acuerdo? (sí/no) | Nota |
|---|---|---|---|---|
| 1 | Para que un endpoint de creación devuelva el código de estado 201 en lugar de 200, debes usar el parámetro `status_code` en el decorador del path operation, por ejemplo `@app.post("/items/", status_code=201)`. | apoyada | | |
| 2 | Esto hará que la respuesta tenga el código 201 y también se documente así en el esquema OpenAPI. | apoyada | | |
| 3 | Puedes usar la constante `status.HTTP_201_CREATED` importándola desde `fastapi.status` para mayor claridad. | apoyada | | |
| 4 | Ejemplo de código con `status.HTTP_201_CREATED` en el decorador `@app.post` para que el endpoint devuelva el código 201. | apoyada | | |

### Contexto que vio el modelo

**[1] Response Status Code** · sección completa (get_section) · https://fastapi.tiangolo.com/tutorial/response-status-code/

````text
# Response Status Code

The same way you can specify a response model, you can also declare the HTTP status code used for the response with the parameter `status_code` in any of the *path operations*:

* `@app.get()`
* `@app.post()`
* `@app.put()`
* `@app.delete()`
* etc.

```python
from fastapi import FastAPI

app = FastAPI()


@app.post("/items/", status_code=201)  # highlight
async def create_item(name: str):
    return {"name": name}
```

/// note

Notice that `status_code` is a parameter of the "decorator" method (`get`, `post`, etc). Not of your *path operation function*, like all the parameters and body.

///

The `status_code` parameter receives a number with the HTTP status code.

/// note

`status_code` can alternatively also receive an `IntEnum`, such as Python's [`http.HTTPStatus`](https://docs.python.org/3/library/http.html#http.HTTPStatus).

///

It will:

* Return that status code in the response.
* Document it as such in the OpenAPI schema (and so, in the user interfaces):

<img src="/img/tutorial/response-status-code/image01.png">

/// note

Some response codes (see the next section) indicate that the response does not have a body.

FastAPI knows this, and will produce OpenAPI docs that state there is no response body.

///
````

<details>
<summary>Texto completo</summary>

````text
# Response Status Code

The same way you can specify a response model, you can also declare the HTTP status code used for the response with the parameter `status_code` in any of the *path operations*:

* `@app.get()`
* `@app.post()`
* `@app.put()`
* `@app.delete()`
* etc.

```python
from fastapi import FastAPI

app = FastAPI()


@app.post("/items/", status_code=201)  # highlight
async def create_item(name: str):
    return {"name": name}
```

/// note

Notice that `status_code` is a parameter of the "decorator" method (`get`, `post`, etc). Not of your *path operation function*, like all the parameters and body.

///

The `status_code` parameter receives a number with the HTTP status code.

/// note

`status_code` can alternatively also receive an `IntEnum`, such as Python's [`http.HTTPStatus`](https://docs.python.org/3/library/http.html#http.HTTPStatus).

///

It will:

* Return that status code in the response.
* Document it as such in the OpenAPI schema (and so, in the user interfaces):

<img src="/img/tutorial/response-status-code/image01.png">

/// note

Some response codes (see the next section) indicate that the response does not have a body.

FastAPI knows this, and will produce OpenAPI docs that state there is no response body.

///
````

</details>

**[2] Path Operation Configuration > Response Status Code** · fragmento · https://fastapi.tiangolo.com/tutorial/path-operation-configuration/#response-status-code

````text
## Response Status Code { #response-status-code }

You can define the (HTTP) `status_code` to be used in the response of your *path operation*.

You can pass directly the `int` code, like `404`.

But if you don't remember what each number code is for, you can use the shortcut constants in `status`:

```python
from fastapi import FastAPI, status  # highlight
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None
    tags: set[str] = set()


@app.post("/items/", status_code=status.HTTP_201_CREATED)  # highlight
async def create_item(item: Item) -> Item:
    return item
```

That status code will be used in the response and will be added to the OpenAPI schema.

/// note | Technical Details

You could also use `from starlette import status`.

**FastAPI** provides the same `starlette.status` as `fastapi.status` just as a convenience for you, the developer. But it comes directly from Starlette.

///
````

<details>
<summary>Texto completo</summary>

````text
## Response Status Code { #response-status-code }

You can define the (HTTP) `status_code` to be used in the response of your *path operation*.

You can pass directly the `int` code, like `404`.

But if you don't remember what each number code is for, you can use the shortcut constants in `status`:

```python
from fastapi import FastAPI, status  # highlight
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None
    tags: set[str] = set()


@app.post("/items/", status_code=status.HTTP_201_CREATED)  # highlight
async def create_item(item: Item) -> Item:
    return item
```

That status code will be used in the response and will be added to the OpenAPI schema.

/// note | Technical Details

You could also use `from starlette import status`.

**FastAPI** provides the same `starlette.status` as `fastapi.status` just as a convenience for you, the developer. But it comes directly from Starlette.

///
````

</details>

**[3] Additional Status Codes** · fragmento · https://fastapi.tiangolo.com/advanced/additional-status-codes/

````text
# Additional Status Codes { #additional-status-codes }

By default, **FastAPI** will return the responses using a `JSONResponse`, putting the content you return from your *path operation* inside of that `JSONResponse`.

It will use the default status code or the one you set in your *path operation*.
````

<details>
<summary>Texto completo</summary>

````text
# Additional Status Codes { #additional-status-codes }

By default, **FastAPI** will return the responses using a `JSONResponse`, putting the content you return from your *path operation* inside of that `JSONResponse`.

It will use the default status code or the one you set in your *path operation*.
````

</details>

**[4] Response - Change Status Code > Use a `Response` parameter** · fragmento · https://fastapi.tiangolo.com/advanced/response-change-status-code/#use-a-response-parameter

````text
## Use a `Response` parameter { #use-a-response-parameter }

You can declare a parameter of type `Response` in your *path operation function* (as you can do for cookies and headers).

And then you can set the `status_code` in that *temporary* response object.

```python
from fastapi import FastAPI, Response, status  # highlight

app = FastAPI()

tasks = {"foo": "Listen to the Bar Fighters"}


@app.put("/get-or-create-task/{task_id}", status_code=200)
def get_or_create_task(task_id: str, response: Response):  # highlight
    if task_id not in tasks:
        tasks[task_id] = "This didn't exist before"
        response.status_code = status.HTTP_201_CREATED  # highlight
    return tasks[task_id]
```

And then you can return any object you need, as you normally would (a `dict`, a database model, etc).

And if you declared a `response_model`, it will still be used to filter and convert the object you returned.

**FastAPI** will use that *temporary* response to extract the status code (also cookies and headers), and will put them in the final response that contains the value you returned, filtered by any `response_model`.

You can also declare the `Response` parameter in dependencies, and set the status code in them. But keep in mind that the last one to be set will win.
````

<details>
<summary>Texto completo</summary>

````text
## Use a `Response` parameter { #use-a-response-parameter }

You can declare a parameter of type `Response` in your *path operation function* (as you can do for cookies and headers).

And then you can set the `status_code` in that *temporary* response object.

```python
from fastapi import FastAPI, Response, status  # highlight

app = FastAPI()

tasks = {"foo": "Listen to the Bar Fighters"}


@app.put("/get-or-create-task/{task_id}", status_code=200)
def get_or_create_task(task_id: str, response: Response):  # highlight
    if task_id not in tasks:
        tasks[task_id] = "This didn't exist before"
        response.status_code = status.HTTP_201_CREATED  # highlight
    return tasks[task_id]
```

And then you can return any object you need, as you normally would (a `dict`, a database model, etc).

And if you declared a `response_model`, it will still be used to filter and convert the object you returned.

**FastAPI** will use that *temporary* response to extract the status code (also cookies and headers), and will put them in the final response that contains the value you returned, filtered by any `response_model`.

You can also declare the `Response` parameter in dependencies, and set the status code in them. But keep in mind that the last one to be set will win.
````

</details>

**[5] Status Codes** · fragmento · https://fastapi.tiangolo.com/reference/status/

````text
# Status Codes

You can import the `status` module from `fastapi`:

```python
from fastapi import status
```

`status` is provided directly by Starlette.

It contains a group of named constants (variables) with integer status codes.

For example:

* 200: `status.HTTP_200_OK`
* 403: `status.HTTP_403_FORBIDDEN`
* etc.

It can be convenient to quickly access HTTP (and WebSocket) status codes in your app, using autocompletion for the name without having to memorize the integer status codes.

Read more about it in the [FastAPI docs about Response Status Code](https://fastapi.tiangolo.com/tutorial/response-status-code/).
````

<details>
<summary>Texto completo</summary>

````text
# Status Codes

You can import the `status` module from `fastapi`:

```python
from fastapi import status
```

`status` is provided directly by Starlette.

It contains a group of named constants (variables) with integer status codes.

For example:

* 200: `status.HTTP_200_OK`
* 403: `status.HTTP_403_FORBIDDEN`
* etc.

It can be convenient to quickly access HTTP (and WebSocket) status codes in your app, using autocompletion for the name without having to memorize the integer status codes.

Read more about it in the [FastAPI docs about Response Status Code](https://fastapi.tiangolo.com/tutorial/response-status-code/).
````

</details>

## g06 — ¿Cómo recibo campos de un formulario HTML en lugar de JSON?

Ruta esperada: `answer` · obtenida: `answer`

### Respuesta del modelo

Para recibir campos de un formulario HTML en lugar de JSON en FastAPI, debes usar el tipo `Form` para declarar los campos que esperas recibir. FastAPI se encargará de leer los datos del formulario desde el lugar correcto, que normalmente está codificado con el tipo de medio `application/x-www-form-urlencoded` para formularios sin archivos, o `multipart/form-data` si el formulario incluye archivos. Además, para usar formularios, primero debes instalar la librería `python-multipart` en tu proyecto. Por ejemplo, puedes instalarla con el comando `uv add python-multipart`.

Ten en cuenta que no puedes declarar parámetros `Form` y también parámetros `Body` que esperas recibir como JSON en la misma operación, ya que el cuerpo de la solicitud estará codificado como formulario y no como JSON, lo cual es una limitación del protocolo HTTP, no de FastAPI.

**Citas:**

- Form Data > About "Form Fields" · https://fastapi.tiangolo.com/tutorial/request-forms/#about-form-fields
- Form Data · https://fastapi.tiangolo.com/tutorial/request-forms/
- Request Files > What is "Form Data" · https://fastapi.tiangolo.com/tutorial/request-files/#what-is-form-data

### Afirmaciones del juez

| # | Afirmación | Juez | ¿De acuerdo? (sí/no) | Nota |
|---|---|---|---|---|
| 1 | Para recibir campos de un formulario HTML en lugar de JSON en FastAPI, debes usar el tipo `Form` para declarar los campos que esperas recibir. | apoyada | | |
| 2 | FastAPI se encargará de leer los datos del formulario desde el lugar correcto, que normalmente está codificado con el tipo de medio `application/x-www-form-urlencoded` para formularios sin archivos, o `multipart/form-data` si el formulario incluye archivos. | apoyada | | |
| 3 | Para usar formularios, primero debes instalar la librería `python-multipart` en tu proyecto. | apoyada | | |
| 4 | Puedes instalarla con el comando `uv add python-multipart`. | no apoyada | | |
| 5 | No puedes declarar parámetros `Form` y también parámetros `Body` que esperas recibir como JSON en la misma operación, ya que el cuerpo de la solicitud estará codificado como formulario y no como JSON. | apoyada | | |
| 6 | Esta es una limitación del protocolo HTTP, no de FastAPI. | apoyada | | |

### Contexto que vio el modelo

**[1] Form Data > About "Form Fields"** · sección completa (get_section) · https://fastapi.tiangolo.com/tutorial/request-forms/#about-form-fields

````text
## About "Form Fields"

The way HTML forms (`<form></form>`) send the data to the server normally uses a "special" encoding for that data, it's different from JSON.

**FastAPI** will make sure to read that data from the right place instead of JSON.

/// note | Technical Details

Data from forms is normally encoded using the "media type" `application/x-www-form-urlencoded`.

But when the form includes files, it is encoded as `multipart/form-data`. You'll read about handling files in the next chapter.

You can use `Form(media_type="multipart/form-data")` to describe a multipart form in OpenAPI. Setting it on one parameter is enough when combining form parameters or models.

If you want to read more about these encodings and form fields, head to the [<abbr title="Mozilla Developer Network">MDN</abbr> web docs for `POST`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/POST).

///

/// warning

You can declare multiple `Form` parameters in a *path operation*, but you can't also declare `Body` fields that you expect to receive as JSON, as the request will have the body encoded using `application/x-www-form-urlencoded` instead of `application/json`.

This is not a limitation of **FastAPI**, it's part of the HTTP protocol.

///
````

<details>
<summary>Texto completo</summary>

````text
## About "Form Fields"

The way HTML forms (`<form></form>`) send the data to the server normally uses a "special" encoding for that data, it's different from JSON.

**FastAPI** will make sure to read that data from the right place instead of JSON.

/// note | Technical Details

Data from forms is normally encoded using the "media type" `application/x-www-form-urlencoded`.

But when the form includes files, it is encoded as `multipart/form-data`. You'll read about handling files in the next chapter.

You can use `Form(media_type="multipart/form-data")` to describe a multipart form in OpenAPI. Setting it on one parameter is enough when combining form parameters or models.

If you want to read more about these encodings and form fields, head to the [<abbr title="Mozilla Developer Network">MDN</abbr> web docs for `POST`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/POST).

///

/// warning

You can declare multiple `Form` parameters in a *path operation*, but you can't also declare `Body` fields that you expect to receive as JSON, as the request will have the body encoded using `application/x-www-form-urlencoded` instead of `application/json`.

This is not a limitation of **FastAPI**, it's part of the HTTP protocol.

///
````

</details>

**[2] Request Files > What is "Form Data"** · fragmento · https://fastapi.tiangolo.com/tutorial/request-files/#what-is-form-data

````text
## What is "Form Data" { #what-is-form-data }

The way HTML forms (`<form></form>`) send the data to the server normally uses a "special" encoding for that data, it's different from JSON.

**FastAPI** will make sure to read that data from the right place instead of JSON.

/// note | Technical Details

Data from forms is normally encoded using the "media type" `application/x-www-form-urlencoded` when it doesn't include files.

But when the form includes files, it is encoded as `multipart/form-data`. If you use `File`, **FastAPI** will know it has to get the files from the correct part of the body.

If you want to read more about these encodings and form fields, head to the [<abbr title="Mozilla Developer Network">MDN</abbr> web docs for `POST`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/POST).

///

/// warning

You can declare multiple `File` and `Form` parameters in a *path operation*, but you can't also declare `Body` fields that you expect to receive as JSON, as the request will have the body encoded using `multipart/form-data` instead of `application/json`.

This is not a limitation of **FastAPI**, it's part of the HTTP protocol.

///
````

<details>
<summary>Texto completo</summary>

````text
## What is "Form Data" { #what-is-form-data }

The way HTML forms (`<form></form>`) send the data to the server normally uses a "special" encoding for that data, it's different from JSON.

**FastAPI** will make sure to read that data from the right place instead of JSON.

/// note | Technical Details

Data from forms is normally encoded using the "media type" `application/x-www-form-urlencoded` when it doesn't include files.

But when the form includes files, it is encoded as `multipart/form-data`. If you use `File`, **FastAPI** will know it has to get the files from the correct part of the body.

If you want to read more about these encodings and form fields, head to the [<abbr title="Mozilla Developer Network">MDN</abbr> web docs for `POST`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/POST).

///

/// warning

You can declare multiple `File` and `Form` parameters in a *path operation*, but you can't also declare `Body` fields that you expect to receive as JSON, as the request will have the body encoded using `multipart/form-data` instead of `application/json`.

This is not a limitation of **FastAPI**, it's part of the HTTP protocol.

///
````

</details>

**[3] Form Models** · fragmento · https://fastapi.tiangolo.com/tutorial/request-form-models/

````text
# Form Models { #form-models }

You can use **Pydantic models** to declare **form fields** in FastAPI.

/// note

To use forms, first install [`python-multipart`](https://github.com/Kludex/python-multipart).

Add it to your project:

```console
$ uv add python-multipart
```

///

/// note

This is supported since FastAPI version `0.113.0`. 🤓

///
````

<details>
<summary>Texto completo</summary>

````text
# Form Models { #form-models }

You can use **Pydantic models** to declare **form fields** in FastAPI.

/// note

To use forms, first install [`python-multipart`](https://github.com/Kludex/python-multipart).

Add it to your project:

```console
$ uv add python-multipart
```

///

/// note

This is supported since FastAPI version `0.113.0`. 🤓

///
````

</details>

**[4] Form Models > Summary** · fragmento · https://fastapi.tiangolo.com/tutorial/request-form-models/#summary

````text
## Summary { #summary }

You can use Pydantic models to declare form fields in FastAPI. 😎
````

<details>
<summary>Texto completo</summary>

````text
## Summary { #summary }

You can use Pydantic models to declare form fields in FastAPI. 😎
````

</details>

**[5] Form Data** · fragmento · https://fastapi.tiangolo.com/tutorial/request-forms/

````text
# Form Data { #form-data }

When you need to receive form fields instead of JSON, you can use `Form`.

/// note

To use forms, first install [`python-multipart`](https://github.com/Kludex/python-multipart).

Add it to your project:

```console
$ uv add python-multipart
```

///
````

<details>
<summary>Texto completo</summary>

````text
# Form Data { #form-data }

When you need to receive form fields instead of JSON, you can use `Form`.

/// note

To use forms, first install [`python-multipart`](https://github.com/Kludex/python-multipart).

Add it to your project:

```console
$ uv add python-multipart
```

///
````

</details>

## g07 — ¿Cómo creo un middleware que mida el tiempo de cada petición y lo agregue en una cabecera?

Ruta esperada: `answer` · obtenida: `answer`

### Respuesta del modelo

Para crear un middleware en FastAPI que mida el tiempo que tarda cada petición y agregue ese tiempo en una cabecera, puedes usar el decorador `@app.middleware("http")` sobre una función asíncrona que reciba el objeto `request` y una función `call_next`. Dentro de esta función, mides el tiempo antes y después de llamar a `call_next(request)`, que procesa la petición y genera la respuesta. Luego, agregas el tiempo calculado en segundos como un valor en la cabecera `X-Process-Time` de la respuesta y la retornas. Aquí un ejemplo de código:

```python
import time
from fastapi import FastAPI, Request

app = FastAPI()

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

Este middleware ejecuta código antes y después de la petición, midiendo el tiempo total y agregándolo en la cabecera de la respuesta para que el cliente pueda conocerlo.

**Citas:**

- Middleware > Create a middleware · https://fastapi.tiangolo.com/tutorial/middleware/#create-a-middleware
- Middleware > Before and after the `response` · https://fastapi.tiangolo.com/tutorial/middleware/#before-and-after-the-response

### Afirmaciones del juez

| # | Afirmación | Juez | ¿De acuerdo? (sí/no) | Nota |
|---|---|---|---|---|
| 1 | Para crear un middleware en FastAPI que mida el tiempo que tarda cada petición y agregue ese tiempo en una cabecera, puedes usar el decorador `@app.middleware("http")` sobre una función asíncrona que reciba el objeto `request` y una función `call_next`. | apoyada | | |
| 2 | Dentro de esta función, mides el tiempo antes y después de llamar a `call_next(request)`, que procesa la petición y genera la respuesta. | apoyada | | |
| 3 | Luego, agregas el tiempo calculado en segundos como un valor en la cabecera `X-Process-Time` de la respuesta y la retornas. | apoyada | | |
| 4 | Aquí un ejemplo de código: ```python import time from fastapi import FastAPI, Request app = FastAPI() @app.middleware("http") async def add_process_time_header(request: Request, call_next): start_time = time.perf_counter() response = await call_next(request) process_time = time.perf_counter() - start_time response.headers["X-Process-Time"] = str(process_time) return response ``` | apoyada | | |
| 5 | Este middleware ejecuta código antes y después de la petición, midiendo el tiempo total y agregándolo en la cabecera de la respuesta para que el cliente pueda conocerlo. | apoyada | | |

### Contexto que vio el modelo

**[1] Middleware > Create a middleware** · sección completa (get_section) · https://fastapi.tiangolo.com/tutorial/middleware/#create-a-middleware

````text
## Create a middleware

To create a middleware you use the decorator `@app.middleware("http")` on top of a function.

The middleware function receives:

* The `request`.
* A function `call_next` that will receive the `request` as a parameter.
    * This function will pass the `request` to the corresponding *path operation*.
    * Then it returns the `response` generated by the corresponding *path operation*.
* You can then further modify the `response` before returning it.

```python
import time

from fastapi import FastAPI, Request

app = FastAPI()


@app.middleware("http")  # highlight
async def add_process_time_header(request: Request, call_next):  # highlight
    start_time = time.perf_counter()
    response = await call_next(request)  # highlight
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response  # highlight
```

/// tip

Keep in mind that custom proprietary headers can be added [using the `X-` prefix](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers).

But if you have custom headers that you want a client in a browser to be able to see, you need to add them to your CORS configurations ([CORS (Cross-Origin Resource Sharing)](cors.md)) using the parameter `expose_headers` documented in [Starlette's CORS docs](https://starlette.dev/middleware/#corsmiddleware).

///

/// note | Technical Details

You could also use `from starlette.requests import Request`.

**FastAPI** provides it as a [...]
````

<details>
<summary>Texto completo</summary>

````text
## Create a middleware

To create a middleware you use the decorator `@app.middleware("http")` on top of a function.

The middleware function receives:

* The `request`.
* A function `call_next` that will receive the `request` as a parameter.
    * This function will pass the `request` to the corresponding *path operation*.
    * Then it returns the `response` generated by the corresponding *path operation*.
* You can then further modify the `response` before returning it.

```python
import time

from fastapi import FastAPI, Request

app = FastAPI()


@app.middleware("http")  # highlight
async def add_process_time_header(request: Request, call_next):  # highlight
    start_time = time.perf_counter()
    response = await call_next(request)  # highlight
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response  # highlight
```

/// tip

Keep in mind that custom proprietary headers can be added [using the `X-` prefix](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers).

But if you have custom headers that you want a client in a browser to be able to see, you need to add them to your CORS configurations ([CORS (Cross-Origin Resource Sharing)](cors.md)) using the parameter `expose_headers` documented in [Starlette's CORS docs](https://starlette.dev/middleware/#corsmiddleware).

///

/// note | Technical Details

You could also use `from starlette.requests import Request`.

**FastAPI** provides it as a convenience for you, the developer. But it comes directly from Starlette.

///
````

</details>

**[2] Middleware** · fragmento · https://fastapi.tiangolo.com/tutorial/middleware/

````text
# Middleware { #middleware }

You can add middleware to **FastAPI** applications.

A "middleware" is a function that works with every **request** before it is processed by any specific *path operation*. And also with every **response** before returning it.

* It takes each **request** that comes to your application.
* It can then do something to that **request** or run any needed code.
* Then it passes the **request** to be processed by the rest of the application (by some *path operation*).
* It then takes the **response** generated by the application (by some *path operation*).
* It can do something to that **response** or run any needed code.
* Then it returns the **response**.

/// note | Technical Details

If you have dependencies with `yield`, the exit code will run *after* the middleware.

If there were any background tasks (covered in the [Background Tasks](background-tasks.md) section, you will see it later), they will run *after* all the middleware.

///
````

<details>
<summary>Texto completo</summary>

````text
# Middleware { #middleware }

You can add middleware to **FastAPI** applications.

A "middleware" is a function that works with every **request** before it is processed by any specific *path operation*. And also with every **response** before returning it.

* It takes each **request** that comes to your application.
* It can then do something to that **request** or run any needed code.
* Then it passes the **request** to be processed by the rest of the application (by some *path operation*).
* It then takes the **response** generated by the application (by some *path operation*).
* It can do something to that **response** or run any needed code.
* Then it returns the **response**.

/// note | Technical Details

If you have dependencies with `yield`, the exit code will run *after* the middleware.

If there were any background tasks (covered in the [Background Tasks](background-tasks.md) section, you will see it later), they will run *after* all the middleware.

///
````

</details>

**[3] Middleware > Other middlewares** · fragmento · https://fastapi.tiangolo.com/tutorial/middleware/#other-middlewares

````text
## Other middlewares { #other-middlewares }

You can later read more about other middlewares in the [Advanced User Guide: Advanced Middleware](../advanced/middleware.md).

You will read about how to handle <abbr title="Cross-Origin Resource Sharing">CORS</abbr> with a middleware in the next section.
````

<details>
<summary>Texto completo</summary>

````text
## Other middlewares { #other-middlewares }

You can later read more about other middlewares in the [Advanced User Guide: Advanced Middleware](../advanced/middleware.md).

You will read about how to handle <abbr title="Cross-Origin Resource Sharing">CORS</abbr> with a middleware in the next section.
````

</details>

**[4] Middleware > Before and after the `response`** · fragmento · https://fastapi.tiangolo.com/tutorial/middleware/#before-and-after-the-response

````text
### Before and after the `response` { #before-and-after-the-response }

You can add code to be run with the `request`,  before any *path operation* receives it.

And also after the `response` is generated, before returning it.

For example, you could add a custom header `X-Process-Time` containing the time in seconds that it took to process the request and generate a response:

```python
import time

from fastapi import FastAPI, Request

app = FastAPI()


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()  # highlight
    response = await call_next(request)
    process_time = time.perf_counter() - start_time  # highlight
    response.headers["X-Process-Time"] = str(process_time)  # highlight
    return response
```

/// tip

Here we use [`time.perf_counter()`](https://docs.python.org/3/library/time.html#time.perf_counter) instead of `time.time()` because it can be more precise for these use cases. 🤓

///
````

<details>
<summary>Texto completo</summary>

````text
### Before and after the `response` { #before-and-after-the-response }

You can add code to be run with the `request`,  before any *path operation* receives it.

And also after the `response` is generated, before returning it.

For example, you could add a custom header `X-Process-Time` containing the time in seconds that it took to process the request and generate a response:

```python
import time

from fastapi import FastAPI, Request

app = FastAPI()


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()  # highlight
    response = await call_next(request)
    process_time = time.perf_counter() - start_time  # highlight
    response.headers["X-Process-Time"] = str(process_time)  # highlight
    return response
```

/// tip

Here we use [`time.perf_counter()`](https://docs.python.org/3/library/time.html#time.perf_counter) instead of `time.time()` because it can be more precise for these use cases. 🤓

///
````

</details>

**[5] Advanced Middleware** · fragmento · https://fastapi.tiangolo.com/advanced/middleware/

````text
# Advanced Middleware { #advanced-middleware }

In the main tutorial you read how to add [Custom Middleware](../tutorial/middleware.md) to your application.

And then you also read how to handle [CORS with the `CORSMiddleware`](../tutorial/cors.md).

In this section we'll see how to use other middlewares.
````

<details>
<summary>Texto completo</summary>

````text
# Advanced Middleware { #advanced-middleware }

In the main tutorial you read how to add [Custom Middleware](../tutorial/middleware.md) to your application.

And then you also read how to handle [CORS with the `CORSMiddleware`](../tutorial/cors.md).

In this section we'll see how to use other middlewares.
````

</details>
