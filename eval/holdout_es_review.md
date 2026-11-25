# Holdout en español: tabla de revisión

Generado por `scripts/golden_review.py` desde `eval/holdout_es.json`; no editar a mano.
Escribe tus comentarios en la última columna (o aparte, citando el id).

Casos: 6. Distribución: no aplica (holdout).

| id | categoría | lang | pregunta | ruta esperada | URLs esperadas | ¿existe? | notas | comentario del dueño |
|---|---|---|---|---|---|---|---|---|
| h01 | in_intermediate | es | Mi frontend en React corre en otro puerto y el navegador me bloquea las llamadas a mi API. ¿Cómo habilito CORS? | answer | https://fastapi.tiangolo.com/tutorial/cors/ | ✓ | Página que el golden set no usa. Redactada como síntoma de usuario (bloqueo del navegador), sin decir 'CORSMiddleware'. |  |
| h02 | in_basic | es | ¿Cómo sirvo imágenes y archivos CSS desde una carpeta de mi proyecto? | answer | https://fastapi.tiangolo.com/tutorial/static-files/ | ✓ | Página que el golden set no usa. No menciona StaticFiles ni 'mount'; el usuario describe lo que quiere lograr. |  |
| h03 | in_intermediate | es | Quiero mandar un correo de confirmación después de responder al cliente, sin que tenga que esperar. ¿Cómo lo hago? | answer | https://fastapi.tiangolo.com/tutorial/background-tasks/ | ✓ | Página que el golden set no usa. Pregunta por el caso de uso (correo tras responder), no por BackgroundTasks. |  |
| h04 | in_basic | es | ¿Cómo leo el User-Agent que manda el cliente en una operación de path? | answer | https://fastapi.tiangolo.com/tutorial/header-params/ | ✓ | Página que el golden set no usa (g15 es cookies, g16 cabeceras de respuesta). Aquí son cabeceras de la petición. |  |
| h05 | out_near | es | ¿Cómo defino un blueprint en Flask para agrupar rutas? | no_se | — | — | Fuera de alcance cercano: framework web vecino con vocabulario parecido (rutas, agrupar). El golden set tiene Flask en inglés (g21); aquí va en español. |  |
| h06 | out_obvious | es | ¿Cuántas calorías tiene una porción de arroz con pollo? | no_se | — | — | Fuera de alcance obvio: pregunta no técnica, de otro dominio. |  |
