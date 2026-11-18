# Revisión humana del juez

6 casos `judge_review`. Los fragmentos se muestran truncados a ~1500 caracteres para leer (`[...]`); el juez recibió el texto completo. Escribe tu puntaje (0-1) en cada línea del dueño.

## g01 — ¿Cómo protejo un endpoint con OAuth2 en FastAPI y obtengo el usuario actual? Muéstrame la sección exacta.

Ruta esperada: `answer` · obtenida: `answer`

### Fragmentos que vio el modelo

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

**[2] Security - First Steps** · fragmento · https://fastapi.tiangolo.com/tutorial/security/first-steps/

````text
# Security - First Steps { #security-first-steps }

Let's imagine that you have your **backend** API in some domain.

And you have a **frontend** in another domain or in a different path of the same domain (or in a mobile application).

And you want to have a way for the frontend to authenticate with the backend, using a **username** and **password**.

We can use **OAuth2** to build that with **FastAPI**.

But let's save you the time of reading the full long specification just to find those little pieces of information you need.

Let's use the tools provided by **FastAPI** to handle security.
````

**[3] Simple OAuth2 with Password and Bearer > Return the token** · fragmento · https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/#return-the-token

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

**[4] Security Tools > OAuth2 Authentication** · fragmento · https://fastapi.tiangolo.com/reference/security/#oauth2-authentication

````text
## OAuth2 Authentication

::: fastapi.security.OAuth2

::: fastapi.security.OAuth2AuthorizationCodeBearer

::: fastapi.security.OAuth2PasswordBearer
````

**[5] Simple OAuth2 with Password and Bearer > Get the `username` and `password`** · fragmento · https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/#get-the-username-and-password

````text
## Get the `username` and `password` { #get-the-username-and-password }

We are going to use **FastAPI** security utilities to get the `username` and `password`.

OAuth2 specifies that when using the "password flow" (that we are using) the client/user must send `username` and `password` fields as form data.

And the spec says that the fields have to be named like that. So `user-name` or `email` wouldn't work.

But don't worry, you can show it as you wish to your final users in the frontend.

And your database models can use any other names you want.

But for the login *path operation*, we need to use these names to be compatible with the spec (and be able to, for example, use the integrated API documentation system).

The spec also states that the `username` and `password` must be sent as form data (so, no JSON here).
````

### Respuesta

Para proteger un endpoint con OAuth2 en FastAPI y obtener el usuario actual, puedes usar la dependencia `OAuth2PasswordBearer` para extraer el token y luego obtener el usuario actual decodificando ese token. En el ejemplo proporcionado, se define una función `get_current_user` que depende del token extraído por `oauth2_scheme` y devuelve el usuario actual o lanza una excepción si no está autenticado. Además, se puede definir `get_current_active_user` para verificar que el usuario no esté deshabilitado. Finalmente, en el endpoint protegido, se usa `Depends(get_current_active_user)` para obtener el usuario actual activo. Aquí un extracto clave del código:

```python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

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

Esta sección está en la documentación bajo "Get Current User" y "Simple OAuth2 with Password and Bearer".

**Citas:**

- Get Current User · https://fastapi.tiangolo.com/tutorial/security/get-current-user/
- Simple OAuth2 with Password and Bearer > Return the token · https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/#return-the-token

**Puntaje del juez:** 1.00

**Afirmaciones:**

- ✓ Para proteger un endpoint con OAuth2 en FastAPI y obtener el usuario actual, puedes usar la dependencia OAuth2PasswordBearer para extraer el token y luego obtener el usuario actual decodificando ese token.
- ✓ Se define una función get_current_user que depende del token extraído por oauth2_scheme y devuelve el usuario actual o lanza una excepción si no está autenticado.
- ✓ Se puede definir get_current_active_user para verificar que el usuario no esté deshabilitado.
- ✓ En el endpoint protegido, se usa Depends(get_current_active_user) para obtener el usuario actual activo.
- ✓ El código mostrado es exactamente el que aparece en la documentación bajo "Get Current User" y "Simple OAuth2 with Password and Bearer".

**Motivo del juez:** El contexto incluye exactamente el código y explicación que el asistente cita para proteger un endpoint con OAuth2 y obtener el usuario actual en FastAPI.

Puntaje del dueño (0-1): ___ · Comentario: ___

## g02 — ¿Cómo declaro un parámetro de ruta con tipo int para que FastAPI lo valide automáticamente?

Ruta esperada: `answer` · obtenida: `answer`

### Fragmentos que vio el modelo

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

**[2] Query Parameters > Multiple path and query parameters** · fragmento · https://fastapi.tiangolo.com/tutorial/query-params/#multiple-path-and-query-parameters

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

**[3] Path Parameters > OpenAPI support** · fragmento · https://fastapi.tiangolo.com/tutorial/path-params/#openapi-support

````text
### OpenAPI support { #openapi-support }

OpenAPI doesn't support a way to declare a *path parameter* to contain a *path* inside, as that could lead to scenarios that are difficult to test and define.

Nevertheless, you can still do it in **FastAPI**, using one of the internal tools from Starlette.

And the docs would still work, although not adding any documentation telling that the parameter should contain a path.
````

**[4] Path Parameters** · fragmento · https://fastapi.tiangolo.com/tutorial/path-params/

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

**[5] Classes as Dependencies > Classes as dependencies** · fragmento · https://fastapi.tiangolo.com/tutorial/dependencies/classes-as-dependencies/#classes-as-dependencies_1

````text
Those parameters are what **FastAPI** will use to "solve" the dependency.

In both cases, it will have:

* An optional `q` query parameter that is a `str`.
* A `skip` query parameter that is an `int`, with a default of `0`.
* A `limit` query parameter that is an `int`, with a default of `100`.

In both cases the data will be converted, validated, documented on the OpenAPI schema, etc.
````

### Respuesta

Para declarar un parámetro de ruta con tipo int en FastAPI y que sea validado automáticamente, debes usar anotaciones de tipo estándar de Python en la función que maneja la ruta. Por ejemplo:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/items/{item_id}")
async def read_item(item_id: int):  # Aquí se declara item_id como int
    return {"item_id": item_id}
```

En este ejemplo, `item_id` es declarado como un entero (`int`), y FastAPI se encargará de validar que el valor recibido en la ruta sea un entero, además de proporcionar soporte en el editor para autocompletado y chequeo de errores.

**Citas:**

- Path Parameters > Path parameters with types · https://fastapi.tiangolo.com/tutorial/path-params/#path-parameters-with-types

**Puntaje del juez:** 1.00

**Afirmaciones:**

- ✓ Para declarar un parámetro de ruta con tipo int en FastAPI y que sea validado automáticamente, debes usar anotaciones de tipo estándar de Python en la función que maneja la ruta.
- ✓ En el ejemplo dado, item_id es declarado como un entero (int).
- ✓ FastAPI se encargará de validar que el valor recibido en la ruta sea un entero.
- ✓ FastAPI proporciona soporte en el editor para autocompletado y chequeo de errores cuando se usa anotación de tipo.

**Motivo del juez:** El contexto incluye un ejemplo explícito de cómo declarar un parámetro de ruta con tipo int usando anotaciones de tipo estándar de Python, y menciona que FastAPI valida automáticamente el tipo y proporciona soporte en el editor.

Puntaje del dueño (0-1): ___ · Comentario: ___

## g10 — How do I declare a request body using a Pydantic model?

Ruta esperada: `answer` · obtenida: `answer`

### Fragmentos que vio el modelo

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

**[2] Request Body > Without Pydantic** · fragmento · https://fastapi.tiangolo.com/tutorial/body/#without-pydantic

````text
## Without Pydantic { #without-pydantic }

If you don't want to use Pydantic models, you can also use **Body** parameters. See the docs for [Body - Multiple Parameters: Singular values in body](body-multiple-params.md#singular-values-in-body).
````

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

**[5] Body - Nested Models** · fragmento · https://fastapi.tiangolo.com/tutorial/body-nested-models/

````text
# Body - Nested Models { #body-nested-models }

With **FastAPI**, you can define, validate, document, and use arbitrarily deeply nested models (thanks to Pydantic).
````

### Respuesta

To declare a request body using a Pydantic model in FastAPI, you define a Pydantic model class with the fields you expect in the request body. Then, you use this model as a parameter in your path operation function. FastAPI will automatically recognize that this parameter should be taken from the request body. For example:

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

In this example, the `item` parameter is a Pydantic model and will be extracted from the request body.

**Citas:**

- Request Body · https://fastapi.tiangolo.com/tutorial/body/
- Request Body > Request body + path parameters · https://fastapi.tiangolo.com/tutorial/body/#request-body-path-parameters

**Puntaje del juez:** 1.00

**Afirmaciones:**

- ✓ To declare a request body using a Pydantic model in FastAPI, you define a Pydantic model class with the fields you expect in the request body.
- ✓ Then, you use this model as a parameter in your path operation function.
- ✓ FastAPI will automatically recognize that this parameter should be taken from the request body.
- ✓ Example code defining a Pydantic model Item with fields name, description, price, tax.
- ✓ Example code shows FastAPI app with a PUT operation at /items/{item_id} that takes item_id and item: Item as parameters.
- ✓ The function returns a dictionary with item_id and the item data using item.model_dump().
- ✓ In this example, the item parameter is a Pydantic model and will be extracted from the request body.

**Motivo del juez:** All claims are directly supported by the example and explanation in the context, especially from section [3] Request Body + path parameters.

Puntaje del dueño (0-1): ___ · Comentario: ___

## g12 — How do I run code at startup and shutdown with the lifespan parameter?

Ruta esperada: `answer` · obtenida: `answer`

### Fragmentos que vio el modelo

**[1] Lifespan Events > `startup` and `shutdown` together** · sección completa (get_section) · https://fastapi.tiangolo.com/advanced/events/#startup-and-shutdown-together

````text
### `startup` and `shutdown` together

There's a high chance that the logic for your *startup* and *shutdown* is connected, you might want to start something and then finish it, acquire a resource and then release it, etc.

Doing that in separate functions that don't share logic or variables together is more difficult as you would need to store values in global variables or similar tricks.

Because of that, it's now recommended to instead use the `lifespan` as explained above.
````

**[2] Lifespan Events** · fragmento · https://fastapi.tiangolo.com/advanced/events/

````text
# Lifespan Events { #lifespan-events }

You can define logic (code) that should be executed before the application **starts up**. This means that this code will be executed **once**, **before** the application **starts receiving requests**.

The same way, you can define logic (code) that should be executed when the application is **shutting down**. In this case, this code will be executed **once**, **after** having handled possibly **many requests**.

Because this code is executed before the application **starts** taking requests, and right after it **finishes** handling requests, it covers the whole application **lifespan** (the word "lifespan" will be important in a second 😉).

This can be very useful for setting up **resources** that you need to use for the whole app, and that are **shared** among requests, and/or that you need to **clean up** afterwards. For example, a database connection pool, or loading a shared machine learning model.
````

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

**[5] Deployments Concepts > Running on Startup** · fragmento · https://fastapi.tiangolo.com/deployment/concepts/#running-on-startup

````text
## Running on Startup { #running-on-startup }

In most cases, when you create a web API, you want it to be **always running**, uninterrupted, so that your clients can always access it. This is of course, unless you have a specific reason why you want it to run only in certain situations, but most of the time you want it constantly running and **available**.
````

### Respuesta

You can run code at startup and shutdown by defining a lifespan function using the `lifespan` parameter of the `FastAPI` app. This function should be an async context manager that uses `yield` to separate startup and shutdown logic. Code before the `yield` runs once before the application starts receiving requests (startup), and code after the `yield` runs once after the application finishes handling requests (shutdown). For example, you can load resources like machine learning models before `yield` and clean them up after `yield`.

Here is a simplified example:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code here
    load_resources()
    yield
    # Shutdown code here
    cleanup_resources()

app = FastAPI(lifespan=lifespan)
```

This approach is recommended because it allows you to manage startup and shutdown logic together, sharing variables and avoiding global state.

For more details and an example, see the FastAPI documentation on Lifespan Events.

**Citas:**

- Lifespan Events > Lifespan · https://fastapi.tiangolo.com/advanced/events/#lifespan
- Lifespan Events > `startup` and `shutdown` together · https://fastapi.tiangolo.com/advanced/events/#startup-and-shutdown-together

**Puntaje del juez:** 1.00

**Afirmaciones:**

- ✓ You can run code at startup and shutdown by defining a lifespan function using the `lifespan` parameter of the `FastAPI` app.
- ✓ This function should be an async context manager that uses `yield` to separate startup and shutdown logic.
- ✓ Code before the `yield` runs once before the application starts receiving requests (startup).
- ✓ Code after the `yield` runs once after the application finishes handling requests (shutdown).
- ✓ For example, you can load resources like machine learning models before `yield` and clean them up after `yield`.
- ✓ Here is a simplified example: from contextlib import asynccontextmanager from fastapi import FastAPI @asynccontextmanager async def lifespan(app: FastAPI): # Startup code here load_resources() yield # Shutdown code here cleanup_resources() app = FastAPI(lifespan=lifespan)
- ✓ This approach is recommended because it allows you to manage startup and shutdown logic together, sharing variables and avoiding global state.
- ✓ For more details and an example, see the FastAPI documentation on Lifespan Events.

**Motivo del juez:** All claims in the answer are directly supported by the provided context, including the explanation, example, and recommendation about using the lifespan parameter for startup and shutdown code.

Puntaje del dueño (0-1): ___ · Comentario: ___

## g16 — How do I add a custom header to the response and also set a cookie on that same response?

Ruta esperada: `answer` · obtenida: `answer`

### Fragmentos que vio el modelo

**[1] Response Headers > Custom Headers** · sección completa (get_section) · https://fastapi.tiangolo.com/advanced/response-headers/#custom-headers

````text
## Custom Headers

Keep in mind that custom proprietary headers can be added [using the `X-` prefix](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers).

But if you have custom headers that you want a client in a browser to be able to see, you need to add them to your CORS configurations (read more in [CORS (Cross-Origin Resource Sharing)](../tutorial/cors.md)), using the parameter `expose_headers` documented in [Starlette's CORS docs](https://starlette.dev/middleware/#corsmiddleware).
````

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

**[5] Header Parameters** · fragmento · https://fastapi.tiangolo.com/tutorial/header-params/

````text
# Header Parameters { #header-parameters }

You can define Header parameters the same way you define `Query`, `Path` and `Cookie` parameters.
````

### Respuesta

You can add a custom header and set a cookie on the same response by declaring a parameter of type `Response` in your path operation function. Then, set the custom header directly on `response.headers` and set the cookie using `response.set_cookie()`. Finally, return the response content as usual. Here's an example combining both:

```python
from fastapi import FastAPI, Response

app = FastAPI()

@app.get("/custom-header-and-cookie/")
def custom_header_and_cookie(response: Response):
    response.headers["X-Custom-Header"] = "custom value"
    response.set_cookie(key="mycookie", value="cookievalue")
    return {"message": "Custom header and cookie set"}
```

This way, FastAPI will include both the custom header and the cookie in the final response.

**Citas:**

- Response Headers > Use a `Response` parameter · https://fastapi.tiangolo.com/advanced/response-headers/#use-a-response-parameter
- Response Cookies > Use a `Response` parameter · https://fastapi.tiangolo.com/advanced/response-cookies/#use-a-response-parameter

**Puntaje del juez:** 1.00

**Afirmaciones:**

- ✓ You can add a custom header and set a cookie on the same response by declaring a parameter of type `Response` in your path operation function.
- ✓ Then, set the custom header directly on `response.headers`.
- ✓ Set the cookie using `response.set_cookie()`.
- ✓ Return the response content as usual.
- ✓ Example code with FastAPI importing Response, defining app, and a path operation function that sets a custom header and a cookie on the response and returns a dict.
- ✓ FastAPI will include both the custom header and the cookie in the final response.

**Motivo del juez:** All claims are directly supported by the context, including the example code and explanation of setting headers and cookies using a Response parameter.

Puntaje del dueño (0-1): ___ · Comentario: ___

## g30 — ¿Qué cambios incompatibles trae FastAPI 1.0 y en qué fecha se publica?

Ruta esperada: `either` · obtenida: `answer`

### Fragmentos que vio el modelo

**[1] About FastAPI versions** · sección completa (get_section) · https://fastapi.tiangolo.com/deployment/versions/

````text
# About FastAPI versions

**FastAPI** is already being used in production in many applications and systems. And the test coverage is kept at 100%. But its development is still moving quickly.

New features are added frequently, bugs are fixed regularly, and the code is still continuously improving.

That's why the current versions are still `0.x.x`, this reflects that each version could potentially have breaking changes. This follows the [Semantic Versioning](https://semver.org/) conventions.

You can create production applications with **FastAPI** right now (and you have probably been doing it for some time), you just have to make sure that you use a version that works correctly with the rest of your code.
````

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

**[3] Features > FastAPI features** · fragmento · https://fastapi.tiangolo.com/features/#fastapi-features

````text
## FastAPI features { #fastapi-features }

**FastAPI** gives you the following:
````

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

### Respuesta

No se proporciona información específica sobre los cambios incompatibles que trae FastAPI 1.0 ni la fecha de su publicación en los fragmentos de contexto disponibles. Solo se menciona que las versiones por debajo de 1.0.0 pueden tener cambios incompatibles y que FastAPI sigue las convenciones de Semantic Versioning, pero no se detalla qué cambios específicos ocurren en la versión 1.0 ni cuándo se lanza.

**Citas:**

- (ninguna)

**Puntaje del juez:** 1.00

**Afirmaciones:**

- ✓ No se proporciona información específica sobre los cambios incompatibles que trae FastAPI 1.0 ni la fecha de su publicación en los fragmentos de contexto disponibles.
- ✓ Solo se menciona que las versiones por debajo de 1.0.0 pueden tener cambios incompatibles y que FastAPI sigue las convenciones de Semantic Versioning.
- ✓ No se detalla qué cambios específicos ocurren en la versión 1.0 ni cuándo se lanza.

**Motivo del juez:** El contexto menciona que las versiones por debajo de 1.0 pueden tener cambios incompatibles y que se sigue Semantic Versioning, pero no hay información sobre cambios incompatibles específicos en la versión 1.0 ni su fecha de publicación.

Puntaje del dueño (0-1): ___ · Comentario: ___
