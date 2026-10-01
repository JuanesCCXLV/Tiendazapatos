# Guía de Exposición: Patrón SAGA por Orquestación

Este documento contiene el guión completo, diapositiva por diapositiva, para exponer la **SAGA Orquestada**. Incluye las explicaciones conceptuales, analogías clave, notas del orador y el paso a paso para la demostración en vivo.

---

## Diapositiva 1: La Lógica Central — El Orquestador

### Texto de la Diapositiva
> A diferencia de la coreografía donde todos los servicios hablan entre sí, en la orquestación tenemos un director central: el **Orquestador de la SAGA**. En el código, esto se ve como una máquina de estados. Este servicio es el único que conoce el mapa completo de la transacción. Él no hace el trabajo pesado en las bases de datos, simplemente da las órdenes: le dice a Zapatos "reserva el inventario", y espera pacientemente su respuesta antes de decirle a Clientes "cobra el saldo". Centralizamos el flujo en un solo lugar.

### 🎙️ Notas del Orador (Qué decir)
> *"Buenos días / tardes a todos. Cuando implementamos transacciones distribuidas en microservicios, el mayor desafío es mantener la consistencia sin caer en el bloqueo de dos fases (2PC) que destruye la escalabilidad.*
>
> *En la **SAGA por Coreografía**, cada servicio actúa de forma reactiva escuchando eventos globales. Pero a medida que el negocio crece, ese flujo se vuelve como un espagueti difícil de rastrear.*
>
> *Por eso hoy les presento la **SAGA por Orquestación**: aquí introducimos una figura central: **el Orquestador**. Imaginen una orquesta filarmónica: los músicos (Zapatos, Clientes, Ventas) son virtuosos en su instrumento (su propia base de datos), pero necesitan al **Director de Orquesta** para saber cuándo entrar y a qué ritmo tocar.*
>
> *A nivel de arquitectura de software, este Orquestador se implementa como una **Máquina de Estados Finita (State Machine)**. Este servicio es el único que conoce el mapa completo de la transacción y mantiene el historial de auditoría (*Saga Execution Log*). Él no accede directamente a PostgreSQL ni a MongoDB; simplemente despacha órdenes y coordina las transiciones de estado."*

---

## Diapositiva 2: Comunicación — Comandos y Respuestas

### Texto de la Diapositiva
> Para que el orquestador dirija la orquesta, seguimos usando un bus de mensajes como **RabbitMQ**, pero cambia el tipo de mensaje. Ya no lanzamos eventos al aire esperando que alguien reaccione. Ahora, el orquestador envía **"Comandos" directos**, por ejemplo: un mensaje de `ejecutar_reserva` específicamente a la cola del servicio de Zapatos. Cada microservicio procesa la orden, hace su commit local, y devuelve un mensaje de respuesta directo al orquestador indicando "Éxito" o "Fallo".

### 🎙️ Notas del Orador (Qué decir)
> *"Un cambio fundamental respecto a la coreografía es la semántica de los mensajes en RabbitMQ:*
>
> *1. **En Coreografía usábamos Eventos de Dominio:** Lanzábamos un evento al aire diciendo `venta.creada` en modo broadcast, esperando a ver quién lo escuchaba.*
>
> *2. **En Orquestación usamos el patrón Comando-Respuesta (Command-Reply):** El Orquestador no lanza eventos al vacío; envía **Comandos dirigidos** con intención imperativa: `comando.zapatos.reservar` directamente a la `cola_comandos_zapatos`.*
>
> *Cada participante recibe su comando, ejecuta su transacción local con commit en su base de datos privada (Database per Service), y emite una respuesta directa a la `cola_orquestador_respuestas` indicando: `respuesta.zapatos.reservado (OK)` o `respuesta.zapatos.fallo (ERROR)`.*
>
> *Esto desacopla a los servicios entre sí: **Zapatos no sabe que existe Clientes, ni Clientes sabe que existe Zapatos**. Ambos solo se comunican con el Orquestador."*

---

## Diapositiva 3: Ejecutando el flujo — Avanzando en la SAGA

### Texto de la Diapositiva
> ¿Cómo avanza el proceso? Cuando el orquestador recibe una respuesta exitosa, da el siguiente paso. Si Zapatos le responde que el stock fue reservado correctamente, el orquestador actualiza su registro interno y despacha el siguiente comando: `procesar_pago` hacia el servicio de Clientes. La ventaja aquí es que los microservicios se vuelven mucho más simples; no necesitan saber que son parte de una compra global, solo ejecutan la instrucción que el orquestador les manda y reportan el resultado.

### 🎙️ Notas del Orador (Qué decir)
> *"Veamos cómo transita la máquina de estados cuando todo va bien:*
>
> *1. Cuando Zapatos responde con éxito, el Orquestador toma la respuesta, registra en su log: `Estado: STOCK_RESERVADO`, y de inmediato evalúa la siguiente transición.*
>
> *2. El siguiente paso en la definición del negocio es cobrar el dinero. El Orquestador genera el comando `comando.clientes.cobrar` y se lo envía a la cola de Clientes.*
>
> *3. ¿Cuál es el gran beneficio de ingeniería de software aquí? **La simplicidad de los microservicios.** En coreografía, el microservicio de Clientes tenía que suscribirse a eventos de inventario y saber qué hacer. Aquí, Clientes es un componente puro: recibe una orden de cobro, valida el saldo en PostgreSQL, ejecuta el débito y le dice al Orquestador: 'listo, cobrado'. Toda la complejidad de negocio queda centralizada y testeable en un único componente."*

---

## Diapositiva 4: Manejando el fallo — Disparando las Compensaciones

### Texto de la Diapositiva
> Si el orquestador recibe una respuesta de error, por ejemplo un "saldo insuficiente" desde el servicio de Clientes, él toma el control total del **Rollback Semántico**. Como el orquestador tiene el historial exacto de qué pasos ya se ejecutaron con éxito, sabe perfectamente qué debe deshacer. Automáticamente despacha el comando inverso de `liberar_stock` a Zapatos. La lógica de qué compensar, en qué orden y cuándo hacerlo ya no está regada por todo el sistema, vive exclusivamente en el orquestador.

### 🎙️ Notas del Orador (Qué decir)
> *"Aquí es donde la SAGA Orquestada brilla con mayor fuerza: en el manejo de fallos y el **Rollback Semántico**.*
>
> *Recordemos que en microservicios no podemos hacer un `ROLLBACK` de base de datos tradicional entre múltiples bases de datos distintas (PostgreSQL y MongoDB). La reserva de Zapatos ya hizo `COMMIT`.*
>
> *Si el servicio de Clientes responde con error: `Saldo insuficiente`, el Orquestador no entra en pánico ni se producen condiciones de carrera. El Orquestador lee su historial de auditoría (*Saga Execution Log*) y dice:*
>
> *— 'Veo que Zapatos ya había reservado 1 unidad. Por lo tanto, debo compensar Zapatos antes de cancelar la orden.'*
>
> *Acto seguido, despacha el comando compensatorio `comando.zapatos.liberar`. Zapatos incrementa el inventario de vuelta en PostgreSQL, confirma la compensación, y el Orquestador procede a marcar la venta como CANCELADA en MongoDB.*
>
> ***La lógica de reversa vive en un solo lugar.** Si mañana agregamos un servicio de Envíos o Cupones, solo modificamos el Orquestador; los demás microservicios no se tocan."*

---

## Diapositiva 5: Caso Práctico - Escenario 1 (Camino Feliz con Orquestador)

### Texto de la Diapositiva
> Veamos el sistema en ejecución con el **Camino Feliz**. El cliente Samuel compra unos zapatos de 250.000 pesos teniendo 500.000 de saldo. En los logs ahora vemos al orquestador en el centro de todo: Primero, recibe la solicitud e inicia la SAGA. Segundo, envía el comando a Zapatos; Zapatos descuenta el stock de 10 a 9 en PostgreSQL y le responde "Ok". Tercero, el orquestador envía el comando a Clientes; Clientes debita la plata y le responde "Ok". Finalmente, el orquestador le da la instrucción a Ventas de marcar el pedido como CONFIRMADO. Todo fluye de forma estructurada bajo un control central.

### 🎙️ Notas del Orador (Demostración)
> *(Ejecutar en la terminal `python simular_saga.py` o mostrar los logs en vivo)*
>
> *"Miren los logs en pantalla:*
>
> *1. `orquestador-service` recibe `POST /saga/comprar` e inicializa la SAGA con ID `saga-8a100a00bc` en estado `INICIADA`.*
> *2. Despacha `comando.zapatos.reservar`. Vemos en verde cómo `zapatos-service` descuenta el stock de 10 a 9 en PostgreSQL y responde 'OK'.*
> *3. El Orquestador recibe el 'OK', pasa a `STOCK_RESERVADO` y envía `comando.clientes.cobrar` a `clientes-service`.*
> *4. Vemos en amarillo cómo `clientes-service` debita $250.000 del saldo de Samuel ($500.000 -> $250.000) y responde 'OK'.*
> *5. El Orquestador pasa a `PAGO_EXITOSO` y le envía a `ventas-service` el comando `comando.ventas.confirmar`.*
> *6. `ventas-service` en cian guarda el recibo en MongoDB con estado `CONFIRMADA`.*
> *7. El Orquestador finaliza la SAGA en estado `COMPLETADA`."*

---

## Diapositiva 6: Caso Práctico - Escenario 2 (Fallo y Compensación con Orquestador)

### Texto de la Diapositiva
> En el escenario de fallo, tenemos nuevamente a 'Carlos Pobre' con sus 50.000 pesos de saldo. El orquestador inicia la SAGA y manda a Zapatos a reservar el stock, pasando de 9 a 8 exitosamente. Luego, el orquestador le manda a Clientes el comando de cobrar. Clientes rechaza la operación por falta de fondos y le avisa al orquestador. Aquí el orquestador detiene el avance y activa la reversa: genera un comando de `cancelar_reserva` y se lo envía a Zapatos. Zapatos restaura su stock de 8 a 9 y confirma. Sabiendo que todo se revirtió correctamente, el orquestador cierra la SAGA y manda a marcar la orden como CANCELADA. El inventario está a salvo y el estado es consistente.

### 🎙️ Notas del Orador (Demostración)
> *"Ahora observemos la resiliencia del sistema ante un fallo de negocio:*
>
> *1. Carlos Pobre intenta comprar el zapato de $250.000 teniendo únicamente $50.000.*
> *2. El Orquestador inicia la SAGA y manda a Zapatos a reservar stock. Zapatos decrementa de 9 a 8 unidades (commit local).*
> *3. El Orquestador le ordena a Clientes cobrar. Clientes valida en PostgreSQL: $50.000 < $250.000. ¡Rechazado por saldo insuficiente! Clientes responde con error al Orquestador.*
> *4. Aquí se aprecia el poder del Orquestador: **no hay caos distribuido**. El Orquestador frena el avance y entra en modo `COMPENSANDO_STOCK`.*
> *5. Envía el comando compensatorio `comando.zapatos.liberar`. Zapatos toma la instrucción y devuelve la unidad: 8 -> 9 unidades (commit de compensación).*
> *6. El Orquestador recibe la confirmación de compensación y despacha `comando.ventas.cancelar` a Ventas, que marca el pedido como `CANCELADA` por 'Saldo insuficiente'.*
> *7. **Resultado final:** Ni un solo peso perdido, stock perfectamente consistente en 9 unidades, y consistencia eventual garantizada mediante compensación semántica."*

---

## Preguntas Frecuentes del Profesor y Cómo Responderlas

### P1: ¿El orquestador no se convierte en un punto único de falla (SPOF)?
> **Respuesta:** *"Es una excelente pregunta. En sistemas modernos, el Orquestador es un servicio **stateless** (sin estado propio volátil), cuya máquina de estados se respalda en una base de datos o en colas persistentes de RabbitMQ. Si una réplica del contenedor del orquestador cae, otra réplica toma el mensaje y continúa la máquina de estados gracias al ID de la SAGA."*

### P2: ¿Cuándo conviene usar Orquestación en lugar de Coreografía?
> **Respuesta:** *"La Coreografía es genial para flujos simples de 2 o 3 pasos donde los eventos son naturales. Pero cuando el flujo tiene múltiples pasos condicionales, bifurcaciones de compensación, o se requiere auditar en tiempo real el progreso de cada orden, la **Orquestación** es ampliamente superior porque centraliza la lógica y evita el espagueti distribuido."*
