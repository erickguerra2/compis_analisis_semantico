# Decisiones de diseño

## Visitor y acumulación de errores

Se usa el Visitor generado por ANTLR porque cada visita de expresión puede devolver su tipo. Los
errores semánticos se acumulan con una regla estable además del mensaje; esto permite mostrar
varios problemas en el IDE y hacer aserciones precisas en las pruebas.

## `switch`, `break` y `continue`

`switch` tiene fallthrough como C/Java/JavaScript. `break` es válido tanto en bucles como en un
`switch`; `continue` solo es válido en bucles. Cada `case` valida que su expresión sea comparable
por igualdad con el subject del `switch`.

## Retorno garantizado

El análisis es conservador. Un `if/else` garantiza retorno únicamente si ambas ramas lo hacen y
un `do-while` puede garantizarlo porque ejecuta su cuerpo al menos una vez. `while`, `for`,
`switch` y `try/catch` no se consideran garantía aun cuando un caso concreto pudiera serlo.

## Clases y constructores

- Los miembros se predeclaran antes de analizar métodos e inicializadores.
- Una propiedad se busca primero en la clase concreta y después en cada clase base.
- Una instancia de una clase hija es asignable y comparable con su tipo base, pero no al revés.
- La clase base debe estar declarada antes que la clase hija.
- Los constructores no se heredan. Si una clase no declara `function constructor(...)`, solo se
  permite construirla sin argumentos.
- `this` está disponible en métodos y en funciones anidadas dentro de ellos, donde se comporta
  como un valor capturado. Fuera de ese contexto es un error.

## Ámbitos de iteración

`foreach` crea un ámbito para su variable de iteración. Actualmente el encabezado de `for` no
crea un ámbito separado: una variable declarada allí queda en el ámbito contenedor. Esta decisión
se conserva por compatibilidad con la implementación actual y debe ratificarse con el equipo.

## Casos todavía abiertos

- La gramática no incluye `float` ni literal flotante, aunque el sistema de tipos ya contiene el
  tipo y la promoción `integer -> float`.

# Decisiones de generación TAC

- El TAC usa objetos `Quad` y operandos tipados; `Emitter.lines()` es la
  representación canónica que consumen las pruebas y las siguientes fases.
- Los temporales se reciclan con un pool de menor identificador libre y se
  reinician por unidad de código. Las etiquetas y literales string son globales.
- El analizador conserva `Annotation(scope, type, symbol)` por identidad de nodo
  para desacoplar la generación del recorrido mutable de la tabla de símbolos.
- No se genera TAC cuando existe cualquier error previo. Las construcciones de
  turnos posteriores fallan explícitamente con `NotImplementedError`.
- La variable de `catch` es de tipo `string` y vive en el ámbito del bloque
  `catch`: recibe el mensaje del error lanzado.
- `switch` tiene fall-through, y `break` y `continue` cierran con `try_end`
  cada `try` que abandonan.
- El IDE devuelve el TAC en `POST /compile` (`tac`, `strings`) y, mientras
  haya construcciones sin generación, las reporta en `tacError` en lugar de
  fallar.
- El despacho de métodos es estático: `obj.m()` llama a `K.m`, con `K` la
  clase más cercana al tipo declarado de `obj` que declara `m`. Sin
  polimorfismo dinámico no hace falta tabla de métodos virtuales ni
  encabezado en el objeto.
- El constructor se hereda. El analizador y el generador buscan
  `constructor` subiendo por la herencia, así que `new Dog("Rex")` es válido
  cuando solo `Animal` lo declara (caso de `program/program.cps`).
- Los inicializadores de campos se emiten en el sitio de cada `new`, de la
  clase raíz a la instanciada y antes del constructor. `new` entrega la
  memoria en cero, por lo que un campo sin inicializador vale `0`, `false` o
  `null` sin instrucciones extra.
- Un campo redeclarado en una subclase reutiliza el slot del campo heredado,
  de modo que el layout del padre siempre es prefijo del layout del hijo.
- Un literal de arreglo cuyos elementos son arreglos suma una dimensión:
  `[[1, 2], [3, 4]]` es `integer[][]`.
- Toda lectura y escritura por índice emite `bounds` antes del acceso. Es el
  único error en tiempo de ejecución; su mensaje se interna como literal
  string y el `catch` lo recibe en su variable.
- `foreach` guarda el arreglo, su longitud y el contador en temporales que
  viven todo el ciclo, para que reasignar la variable recorrida no altere la
  iteración.
- En asignaciones a campos y elementos se evalúa primero el valor y después
  el destino, igual que en la asignación a variables del turno 1.
