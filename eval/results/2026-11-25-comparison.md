# Comparación antes/después

Antes: `2026-11-17` (`gpt-4.1-mini` · umbral 0.52) · después: `2026-11-25` (`gpt-4.1-mini` · umbral 0.52). Métricas recalculadas desde los casos con `compute_metrics`.

## Golden set

| Métrica | Antes | Después |
|---|---|---|
| Casos | 30 sin error · 0 con error | 30 sin error · 0 con error |
| Ruta | 80.0% (24/30) | 90.0% (27/30) |
| Ruta del clasificador | 96.6% (28/29) | 96.6% (28/29) |
| Falsos «no sé» | 4 | 1 |
| Falsos «respondí» | 2 | 2 |
| Citas válidas | 88.2% (15/17) | 90.0% (18/20) |
| Acierto de fuente | 87.5% (14/16) | 84.2% (16/19) |
| Fidelidad | 1.00 (17/17 juzgadas) | 0.99 (20/20 juzgadas) |
| Latencia p50 | 3,261 ms | 3,418 ms |
| Latencia p95 | 5,412 ms | 5,948 ms |
| Costo por pregunta (sin juez) | 0.0007 USD | 0.0009 USD |
| Costo por pregunta (con juez) | 0.0013 USD | 0.0016 USD |

«Ruta del clasificador» cuenta los casos `answer` (acierta si no los corta) y los `no_se` de categoría `out_*` o `trap_mentioned` (acierta si los corta); los demás `trap_*`, los `either` y los casos con error quedan fuera: esos le tocan al umbral.

### Cambios del clasificador

Ningún caso cambió de decisión en el clasificador.

### Cambios de ruta

Todos los casos cuya ruta, quién cortó o condición de falso «no sé»/«respondí» cambió (cualquier idioma): un falso «respondí» nuevo aparece aunque el conteo total no cambie.

| Caso | Idioma | Ruta esperada | Ruta antes | Ruta después | Cortó antes | Cortó después | Cambio |
|---|---|---|---|---|---|---|---|
| g03 | es | answer | no_se | answer | umbral | — | corrige falso «no sé» |
| g06 | es | answer | no_se | answer | umbral | — | corrige falso «no sé» |
| g07 | es | answer | no_se | answer | umbral | — | corrige falso «no sé» |

## Español fuera del corpus

Preguntas `es` con ruta esperada `no_se` (o `either`, donde ambas rutas valen). Distancia antes: con la pregunta original; después: con la consulta que usó el grafo (la traducción).

| Caso | Esperada | Ruta antes | Cortó antes | Ruta después | Cortó después | Distancia antes | Distancia después | ¿Más cerca del corpus? |
|---|---|---|---|---|---|---|---|---|
| g19 | no_se | no_se | clasificador | no_se | clasificador | 0.8567 | 0.8205 | sí |
| g22 | no_se | no_se | clasificador | no_se | clasificador | 0.5898 | 0.5352 | sí |
| g25 | no_se | no_se | clasificador | no_se | clasificador | 0.4073 | 0.3728 | sí |
| g26 | no_se | no_se | clasificador | no_se | clasificador | 0.6443 | 0.6228 | sí |
| g27 | no_se | no_se | clasificador | no_se | clasificador | 0.6009 | 0.5843 | sí |
| g30 | either | answer | — | answer | — | 0.4074 | 0.3838 | sí |

## Detalle de g03, g06, g07, g09

| Caso | Pregunta | Distancia antes | Distancia después | Ruta antes | Ruta después | Consulta usada (después) | Fuentes (después) |
|---|---|---|---|---|---|---|---|
| g03 | ¿Cómo hago que un endpoint de creación devuelva el código de estado 201 en lugar de 200? | 0.6033 | 0.4544 | no_se | answer | How to make a creation endpoint return status code 201 instead of 200 in FastAPI? | https://fastapi.tiangolo.com/tutorial/response-status-code/<br>https://fastapi.tiangolo.com/tutorial/path-operation-configuration/#response-status-code<br>https://fastapi.tiangolo.com/advanced/additional-status-codes/<br>https://fastapi.tiangolo.com/advanced/response-change-status-code/#use-a-response-parameter<br>https://fastapi.tiangolo.com/reference/status/ |
| g06 | ¿Cómo recibo campos de un formulario HTML en lugar de JSON? | 0.6165 | 0.3745 | no_se | answer | How do I receive form fields instead of JSON in FastAPI? | https://fastapi.tiangolo.com/tutorial/request-forms/#about-form-fields<br>https://fastapi.tiangolo.com/tutorial/request-files/#what-is-form-data<br>https://fastapi.tiangolo.com/tutorial/request-form-models/<br>https://fastapi.tiangolo.com/tutorial/request-form-models/#summary<br>https://fastapi.tiangolo.com/tutorial/request-forms/ |
| g07 | ¿Cómo creo un middleware que mida el tiempo de cada petición y lo agregue en una cabecera? | 0.5892 | 0.4767 | no_se | answer | How to create a middleware that measures the time of each request and adds it in a header? | https://fastapi.tiangolo.com/tutorial/middleware/#create-a-middleware<br>https://fastapi.tiangolo.com/tutorial/middleware/<br>https://fastapi.tiangolo.com/tutorial/middleware/#other-middlewares<br>https://fastapi.tiangolo.com/tutorial/middleware/#before-and-after-the-response<br>https://fastapi.tiangolo.com/advanced/middleware/ |
| g09 | ¿Cómo limito la longitud máxima de un parámetro de consulta de texto? | 0.6666 | 0.5792 | no_se | no_se | How to limit the maximum length of a query parameter of type string? | https://fastapi.tiangolo.com/tutorial/query-param-models/#forbid-extra-query-parameters<br>https://fastapi.tiangolo.com/tutorial/query-params-str-validations/#add-query-to-annotated-in-the-q-parameter<br>https://fastapi.tiangolo.com/tutorial/query-params-str-validations/#additional-validation<br>https://fastapi.tiangolo.com/tutorial/query-params-str-validations/#alternative-old-query-as-the-default-value<br>https://fastapi.tiangolo.com/tutorial/query-param-models/#check-the-docs |

## Holdout (prompt congelado, una corrida)

Corrida `2026-11-25` (`gpt-4.1-mini` · umbral 0.52). Tabla aparte: no se suma al golden set.

| Métrica | Valor |
|---|---|
| Casos | 6 sin error · 0 con error |
| Ruta | 66.7% (4/6) |
| Ruta del clasificador | 100.0% (6/6) |
| Falsos «no sé» | 2 |
| Falsos «respondí» | 0 |
| Citas válidas | 100.0% (2/2) |
| Acierto de fuente | 100.0% (2/2) |
| Fidelidad | 1.00 (2/2 juzgadas) |
| Latencia p50 | 1,549 ms |
| Latencia p95 | 5,566 ms |
| Costo por pregunta (sin juez) | 0.0007 USD |
| Costo por pregunta (con juez) | 0.0011 USD |

### Holdout: español fuera del corpus

| Caso | Esperada | Ruta | Cortó | Distancia | Consulta usada |
|---|---|---|---|---|---|
| h05 | no_se | no_se | clasificador | 0.5233 | How to define a blueprint in Flask to group routes? |
| h06 | no_se | no_se | clasificador | 0.8873 | How many calories does a serving of arroz con pollo have? |
