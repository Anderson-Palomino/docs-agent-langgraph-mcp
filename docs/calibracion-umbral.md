# Calibración del umbral de "no sé"

Mejor distancia coseno (k=1) de 20 preguntas contra `0.162.0` (modelo `text-embedding-3-small`), ordenadas de menor a mayor. Generado por `scripts/calibrate_threshold.py` con `scripts/calibration_questions.json`.

| Pregunta | Grupo | Mejor distancia | URL |
|---|---|---|---|
| How do I serve static files with FastAPI? | in_corpus | 0.2849 | https://fastapi.tiangolo.com/how-to/custom-docs-ui-assets/#serve-the-static-files |
| How do I use dependency injection with Depends in FastAPI? | in_corpus | 0.2858 | https://fastapi.tiangolo.com/reference/dependencies/#depends |
| How do I declare query parameters with default values in FastAPI? | in_corpus | 0.3197 | https://fastapi.tiangolo.com/tutorial/query-params/#required-query-parameters |
| How can I raise HTTP errors with HTTPException in FastAPI? | in_corpus | 0.3397 | https://fastapi.tiangolo.com/tutorial/handling-errors/#raise-an-httpexception-in-your-code |
| How do I handle CORS in a FastAPI application? | in_corpus | 0.3869 | https://fastapi.tiangolo.com/tutorial/cors/#use-corsmiddleware |
| ¿Cómo subo un archivo con UploadFile en FastAPI? | in_corpus | 0.3974 | https://fastapi.tiangolo.com/reference/uploadfile/ |
| ¿Cómo defino un modelo de respuesta con response_model? | in_corpus | 0.4395 | https://fastapi.tiangolo.com/tutorial/response-model/#response-model-parameter |
| ¿Cómo protejo un endpoint con OAuth2 en FastAPI y obtengo el usuario actual? Muéstrame la sección exacta. | in_corpus | 0.4608 | https://fastapi.tiangolo.com/tutorial/security/get-current-user/ |
| ¿Cómo ejecuto tareas en segundo plano con BackgroundTasks? | in_corpus | 0.4667 | https://fastapi.tiangolo.com/tutorial/background-tasks/ |
| ¿Cómo escribo tests de mi API con TestClient? | in_corpus | 0.4683 | https://fastapi.tiangolo.com/reference/testclient/ |
| How do I define a model with the Django ORM? | out_of_corpus | 0.5273 | https://fastapi.tiangolo.com/tutorial/body/#create-your-data-model |
| ¿Cómo creo una ruta con Express.js y middleware en Node? | out_of_corpus | 0.5946 | https://fastapi.tiangolo.com/tutorial/middleware/#create-a-middleware |
| ¿Cómo configuro permisos en Django REST Framework? | out_of_corpus | 0.6010 | https://fastapi.tiangolo.com/alternatives/#django-rest-framework |
| How do I use hooks like useEffect in React? | out_of_corpus | 0.6634 | https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/#dependencies-errors-and-return-values |
| ¿Cómo configuro un controlador en Spring Boot? | out_of_corpus | 0.7670 | https://fastapi.tiangolo.com/how-to/configure-swagger-ui/ |
| How do I make a sourdough bread at home? | out_of_corpus | 0.7690 | https://fastapi.tiangolo.com/how-to/general/ |
| What is the plot of the movie Inception? | out_of_corpus | 0.7769 | https://fastapi.tiangolo.com/tutorial/security/first-steps/#recap |
| How do I train for a marathon in 12 weeks? | out_of_corpus | 0.8205 | https://fastapi.tiangolo.com/deployment/docker/#dockerfile |
| ¿Cuál es la capital de Australia? | out_of_corpus | 0.8526 | https://fastapi.tiangolo.com/deployment/manually/#asgi-servers |
| ¿Cómo se calcula el impuesto a la renta en Perú? | out_of_corpus | 0.8715 | https://fastapi.tiangolo.com/advanced/stream-data/#simulate-a-file |

Umbral elegido: 0.52 (ver D21).
