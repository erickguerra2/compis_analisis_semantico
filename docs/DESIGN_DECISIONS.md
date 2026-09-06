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
- `try/catch` todavía no declara ni asigna un tipo a la variable de `catch`; el equipo debe elegir
  si será `string`, un tipo de error o un tipo dinámico.
