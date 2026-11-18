# Calibración del umbral de "no sé"

Generado por `scripts/calibrate_threshold.py --from-results` a partir de la corrida `2026-11-17.json` del 2026-11-17 (umbral 0.52 · k=5 · docs FastAPI 0.162.0 · modelo `gpt-4.1-mini`).

Nota: la simulación mide solo la ruta (responde / "no sé"), no la fidelidad (faithfulness). Los casos `either` nunca cuentan como error bajo simulación (spec 5.1): no se conocen las citas.

## Casos por mejor distancia

| id | Pregunta | Esperada | Clasificador | Mejor distancia | URL |
|---|---|---|---|---|---|
| g11 | How can I add tags and a summary to a path operation so they show up in the docs? | answer | aceptó | 0.2931 | https://fastapi.tiangolo.com/how-to/general/#documentation-tags-openapi |
| g10 | How do I declare a request body using a Pydantic model? | answer | aceptó | 0.3201 | https://fastapi.tiangolo.com/tutorial/body/ |
| g05 | ¿Cómo construyo una imagen de Docker para mi aplicación FastAPI? | answer | aceptó | 0.3275 | https://fastapi.tiangolo.com/deployment/docker/#build-a-docker-image-for-fastapi |
| g28 | How do I define a Marshmallow schema to validate and serialize request data? | no_se | rechazó | 0.3741 | https://fastapi.tiangolo.com/alternatives/#marshmallow |
| g12 | How do I run code at startup and shutdown with the lifespan parameter? | answer | aceptó | 0.3772 | https://fastapi.tiangolo.com/advanced/events/#startup-and-shutdown-together |
| g13 | How do I create a WebSocket endpoint and then write a test for it with TestClient? | answer | aceptó | 0.3936 | https://fastapi.tiangolo.com/advanced/testing-websockets/ |
| g14 | How do I replace a dependency with a fake one during tests? | answer | aceptó | 0.4066 | https://fastapi.tiangolo.com/advanced/testing-dependencies/#overriding-dependencies-during-testing |
| g25 | ¿Cómo defino rutas con Route y Mount en una aplicación Starlette pura, sin FastAPI? | no_se | rechazó | 0.4073 | https://fastapi.tiangolo.com/advanced/sub-applications/#mounting-a-fastapi-application |
| g30 | ¿Qué cambios incompatibles trae FastAPI 1.0 y en qué fecha se publica? | either | aceptó | 0.4074 | https://fastapi.tiangolo.com/deployment/versions/ |
| g16 | How do I add a custom header to the response and also set a cookie on that same response? | answer | aceptó | 0.4331 | https://fastapi.tiangolo.com/advanced/response-headers/#custom-headers |
| g04 | ¿Cómo funciona una dependencia con yield para abrir y cerrar una sesión de base de datos? | answer | aceptó | 0.4390 | https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#a-database-dependency-with-yield |
| g17 | How do I require specific OAuth2 scopes for a path operation? | answer | aceptó | 0.4439 | https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/#advanced-usage-with-scopes |
| g02 | ¿Cómo declaro un parámetro de ruta con tipo int para que FastAPI lo valide automáticamente? | answer | aceptó | 0.4456 | https://fastapi.tiangolo.com/tutorial/path-params/#path-parameters-with-types |
| g29 | How do I handle errors? | answer | aceptó | 0.4545 | https://fastapi.tiangolo.com/tutorial/handling-errors/ |
| g01 | ¿Cómo protejo un endpoint con OAuth2 en FastAPI y obtengo el usuario actual? Muéstrame la sección exacta. | answer | aceptó | 0.4608 | https://fastapi.tiangolo.com/tutorial/security/get-current-user/ |
| g08 | ¿Cómo divido mi aplicación en varios archivos con APIRouter y además aplico una dependencia a todas las rutas de la aplicación? | answer | aceptó | 0.4747 | https://fastapi.tiangolo.com/tutorial/bigger-applications/#apirouter |
| g24 | How do I write a Pydantic v1 @validator with pre=True and each_item=True for a list field? | no_se | aceptó | 0.4899 | https://fastapi.tiangolo.com/features/#validation |
| g18 | How should I load configuration from environment variables with a settings class? | answer | aceptó | 0.4989 | https://fastapi.tiangolo.com/advanced/settings/#pydantic-settings |
| g15 | How do I read a cookie value sent by the client in a path operation? | answer | aceptó | 0.4995 | https://fastapi.tiangolo.com/tutorial/cookie-param-models/#check-the-docs |
| g21 | How do I register a Blueprint in a Flask application? | no_se | rechazó | 0.5723 | https://fastapi.tiangolo.com/tutorial/bigger-applications/ |
| g07 | ¿Cómo creo un middleware que mida el tiempo de cada petición y lo agregue en una cabecera? | answer | aceptó | 0.5892 | https://fastapi.tiangolo.com/tutorial/middleware/#create-a-middleware |
| g22 | ¿Cómo agrego un middleware de autenticación en Express.js? | no_se | rechazó | 0.5898 | https://fastapi.tiangolo.com/tutorial/middleware/#create-a-middleware |
| g27 | ¿Cómo configuro permisos en Django REST Framework? | no_se | rechazó | 0.6009 | https://fastapi.tiangolo.com/alternatives/#django-rest-framework |
| g23 | How do I create and apply database migrations with Django's makemigrations command? | no_se | rechazó | 0.6031 | https://fastapi.tiangolo.com/how-to/migrate-from-pydantic-v1-to-pydantic-v2/#migrate-in-steps |
| g03 | ¿Cómo hago que un endpoint de creación devuelva el código de estado 201 en lugar de 200? | answer | aceptó | 0.6033 | https://fastapi.tiangolo.com/tutorial/response-status-code/#about-http-status-codes |
| g06 | ¿Cómo recibo campos de un formulario HTML en lugar de JSON? | answer | aceptó | 0.6165 | https://fastapi.tiangolo.com/tutorial/request-forms/ |
| g26 | ¿Cómo protejo rutas con middleware de autenticación en Laravel? | no_se | rechazó | 0.6443 | https://fastapi.tiangolo.com/tutorial/middleware/#other-middlewares |
| g09 | ¿Cómo limito la longitud máxima de un parámetro de consulta de texto? | answer | aceptó | 0.6666 | https://fastapi.tiangolo.com/tutorial/query-params-str-validations/#additional-validation |
| g20 | What is the offside rule in football? | no_se | rechazó | 0.8070 | https://fastapi.tiangolo.com/tutorial/cors/ |
| g19 | ¿Cuál es la receta de un ceviche clásico peruano? | no_se | rechazó | 0.8567 | https://fastapi.tiangolo.com/how-to/general/ |

## Umbrales (simulación offline sobre `best_distance`)

| Umbral | Cortados por clasificador | Cortados por umbral | Falsos "no sé" (clasificador) | Falsos "no sé" (umbral) | Falsos "respondí" | Exactitud de ruta |
|---|---|---|---|---|---|---|
| 0.48 | 9 | 7 | 0 | 6 | 0 | 80.0% (24/30) |
| 0.50 | 9 | 4 | 0 | 4 | 1 | 83.3% (25/30) |
| 0.52 (actual) | 9 | 4 | 0 | 4 | 1 | 83.3% (25/30) |
| 0.55 | 9 | 4 | 0 | 4 | 1 | 83.3% (25/30) |
