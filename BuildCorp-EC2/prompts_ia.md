# Apoyo de IA en BuildCorp

## Consultas del proyecto

- «Tema 4 me toco». Se pidió identificar el proyecto asignado y extraer sus requisitos de los documentos de evaluación.
- «tengo que hacer todo en la instancia ?». Se revisó la diferencia entre desarrollar localmente y desplegar la aplicación y PostgreSQL en la misma EC2.
- «empieza a hacer BuildCorp, intenta que no se vea hecho con IA […] fijate en los detalles que pide y también el coso de texto». Se solicitó un primer desarrollo con plantillas propias, configuración parametrizada y los flujos del Tema 4.
- «una vez ya tengas todo para la evaluación ponele decoraciones de gatos spynfix y cosas asi, no en svg que sean ojala imagenes». Se pidió una imagen raster como detalle visual.
- «haz que cumpla todo los puntos para dejarla lista para llevarla a la instancia ec2 de amazon». Se pidió revisar la rúbrica y preparar la configuración de producción, la guía de verificación y un ZIP del código para EC2.
- «como si fuese una página y de ahi una subdireccion al admin». Se solicitó separar la portada y el acceso de contratistas de la gestión interna. Se agregó un portal privado que muestra los préstamos del contratista autenticado.
- Se compartió `MODELO EVA 2` como referencia para modelos, permisos y diseño. Se adaptó la separación entre catálogo y gestión, y el filtrado del historial y su detalle por cuenta autenticada.
- Se pidió un diseño más trabajado con gatitos esfinge y una simulación de pago desde el listado de servicios. Se agregaron tarjetas, un cálculo de ejemplo en CLP y escenarios aprobado y rechazado.
- Se pidió acercar el diseño a PupeShop, usar un flujo de arriendo con apariencia realista y aplicar una paleta rosa con una cabeza de gato con casco como logo y favicon.
- Se pidió rediseñar todo el recorrido del cliente con botones interactivos y más recursos de gatos esfinge. Se añadieron filtros, una guía de arriendo, preguntas frecuentes y controles de cantidad y contraseña.
- Se pidió pulir las páginas de error, incluida una 404 con el gato esfinge y un botón para volver al menú principal. Se agregó una vista común para errores web y mensajes para acceso restringido, formulario vencido y errores del servidor.
- Se pidieron sugerencias de búsqueda, un catálogo más amplio y un formulario completo de contratación.
- Se pidió exigir cuenta, precargar datos editables del registro, mostrar stock real ligado a inventario y base de datos, bloquear contratistas y devolver disponibilidad al registrar devoluciones.
- Se pidió corregir el acceso al registro, exigir RUT, agregar medios de pago con PNG, confirmación de éxito, informe PDF y datos de factura. Se implementaron comprobantes de demostración, sin emisión tributaria ni conexión bancaria real.

La imagen Webpay proviene del repositorio oficial de Transbank y se conservó su formato PNG.
[Fuente del recurso](https://github.com/TransbankDevelopers/transbank-plugin-woocommerce-webpay-rest/blob/master/plugin/images/webpay-logo.png)

## Resultado del apoyo

Codex generó el código inicial de inventario, trazabilidad, préstamos y mantenimiento. También preparó las pruebas de los flujos, el panel de gestión con marca propia y la guía para EC2. El bloqueo se calcula a partir de los préstamos abiertos y vencidos. La edición de registros históricos está restringida para conservar la trazabilidad.

## Imagen

Se usó la herramienta de generación de imágenes integrada con este prompt:

> Fotografía horizontal 4:3 para el acceso de BuildCorp. Gato esfinge (Sphynx) gris rosado, sentado junto a una caja metálica de herramientas cerrada y un casco amarillo de obra apoyado al lado, en una bodega ordenada. Luz natural suave, fondo gris cálido, encuadre editorial sencillo y realista. Encuadra el gato centrado, de cuerpo entero. Sin texto, marcas, logotipos ni bordes.

Para la nueva portada se usó la misma herramienta con este prompt:

> Create a wide 3:2 editorial photo for a Chilean construction tool rental website, horizontal composition. Two believable small Sphynx kittens, one pale warm pink and one slate gray, sit side by side on a closed dark olive tool chest in a clean construction equipment rental workshop. A yellow hard hat and a neatly coiled orange extension cable are nearby. Low afternoon sunlight from upper right, warm beige walls, lightly textured concrete, quiet funny expression, authentic photographic detail. Both kittens fully in frame in center, with generous margins, compelling natural color and strong but soft tonal contrast. No letters, signs, brands, text or logos. Realistic proportions and anatomy, no clothing on the cats.

Para las imágenes de las tarjetas de catálogo:

> Generate one wide 3:1 image made of three equally sized square product photos side by side, designed as one product contact sheet for a tool rental catalog. Precisely separate the squares at one-third and two-thirds of the width, no borders. All three use the same light warm grey studio backdrop with soft professional product lighting, shadow underneath, and generous room around the object, product centered in its own square. LEFT square: a forest green cordless electric drill and a compact hard carrying case. CENTER square: a compact yellow plate compactor for construction. RIGHT square: a small white flatbed work truck in three-quarter view, with a green toolbox secured in its bed. Realistic commercial product photography. No humans, lettering, labels, numbers, watermarks, logo or graphic decoration.

Para el logo y favicon:

> Transparent background raster logo mark only. Centered front-facing head of a pink Sphynx kitten wearing a bright golden yellow construction safety hard hat. Only the head and helmet, ears projecting naturally to both sides, no neck or body. Bold, minimal friendly mascot illustration, dark deep-plum outlines, simple flat warm pink planes, large clear almond eyes, no fine linework, high contrast, easily recognizable at a tiny 40 pixel header icon. Keep the silhouette compact and fill the square with about 7 percent safe margin. No words, no lettering, no badge or circle, no shading outside the silhouette.

Para el gato ayudante de la portada y del historial vacío:

> Transparent background, friendly BuildCorp website mascot illustration, full-body seated pink Sphynx cat with very large ears and a yellow construction hard hat, looking up with a gentle curious expression, one paw on a small closed rose pink toolbox. Visual family: simple friendly flat color mascot, thick deep plum outlines, warm golden yellow hat and peach pink skin, polished clean silhouette, suitable for the corner of a website help and empty-state card. Centered, fully in frame with margins. No text, lettering, shadows outside the silhouette, background shapes or border.

Para el PNG de transferencia bancaria se utilizó la herramienta integrada de generación de imágenes.

> One clean horizontal raster payment method icon on a pure white background. A small simple dark plum bank building pictogram on the left with two subtle opposing rose pink arrows underneath. To its right place the Spanish words 'Transferencia' on the first line and 'bancaria' on the second, in a clean geometric sans-serif similar to Poppins, dark plum. Minimal flat graphic, high contrast, readable at 160 pixels wide, no shadows, no border, no additional words, no logos or numbers.
