# Lenguaje intermedio TAC

El compilador traduce Compiscript a código de tres direcciones (TAC). La salida
canónica se obtiene con `Emitter.lines()`; no aplica optimizaciones ni plegado
de constantes. `Emitter.dump()` agrega sangría y, cuando corresponde, la
sección de literales string para consumo humano.

## Instrucciones

| Construcción | Forma canónica |
|---|---|
| binaria | `t0 = a + b` (`+ - * / % < <= > >= == !=`) |
| unaria | `t0 = neg a`, `t0 = not a` |
| copia | `x = y` |
| control | `L0:`, `goto L0`, `if x goto L0`, `ifFalse x goto L0` |
| funciones | `begin_func f`, `end_func f`, `param x`, `t0 = call f, 2`, `return x` |
| arreglos | `t0 = a[i]`, `a[i] = y`, `t0 = new_array n`, `bounds a, i`, `t0 = len a` |
| objetos | `t0 = new C`, `t0 = o.campo`, `o.campo = y` |
| strings | `t0 = concat a, b`, `t0 = to_str a` |
| excepciones | `try_begin L0`, `try_end`, `throw .str0`, `catch err` |
| salida | `print x` |

La división de enteros trunca. `==` y `!=` comparan el valor de enteros y
booleanos, pero la identidad de referencias para strings, arreglos y objetos.

## Operandos y nombres

- Las constantes se imprimen como `5`, `true`, `false` y `null`. Un negativo
  escrito en el fuente se conserva como operación, por ejemplo `t0 = neg 3`.
- Los temporales son `t0`, `t1`, ... y reinician en cada unidad de código.
- Las etiquetas son globales (`L0`, `L1`, ...) y nunca reinician.
- Cada texto se interna una sola vez como `.str0`, `.str1`, ... en orden de
  aparición y queda disponible en `emitter.strings`.
- Las declaraciones homónimas se distinguen por orden: `x`, `x_1`, `x_2`.
- El programa principal se llama `main`; las funciones anidadas usarán
  `externa.interna`, los métodos `Clase.metodo` y los constructores
  `Clase.constructor`. `this` conserva ese nombre.

## Temporales

El pool entrega siempre el identificador libre más pequeño. Solo se liberan
temporales. En operaciones unarias y binarias se evalúan los operandos, se
liberan y después se solicita el resultado, lo que permite reutilizar un id:

```text
t0 = a * b
t1 = c * d
t0 = t0 + t1
```

La construcción que consume un operando es responsable de liberarlo. Al final
de cada sentencia debe haber tantos temporales vivos como al inicio. El
cortocircuito y el ternario reservan primero su temporal resultado para que las
ramas no puedan reutilizarlo.

## Expresiones y declaraciones

Las variables y constantes se usan directamente. Por ejemplo:

```text
begin_func main
t0 = 3 * 2
t0 = 5 + t0
x = t0
print x
end_func main
```

Una declaración sin inicializador recibe `0` si es `integer`, `false` si es
`boolean` y `null` en cualquier otro caso. Las asignaciones son expresiones:
`a = b = 3` produce `b = 3` seguido de `a = b`.

Para `a && b`, el resultado se copia antes del salto y el lado derecho solo se
evalúa si hace falta:

```text
r = a
ifFalse r goto Lend
r = b
Lend:
```

`||` usa `if r goto Lend`. El ternario reserva `r`, evalúa la condición, salta
a la rama falsa con `ifFalse`, y hace que ambas ramas copien su valor a `r`.

Si el resultado de `+` es string, se emite `concat`. Todo operando integer,
boolean o null se convierte previamente mediante `to_str`.

## Supuestos

- Las funciones no son valores de primera clase.
- No se comprueba división entre cero.
- El despacho de métodos será estático según el tipo declarado.
- Un programa con errores léxicos, sintácticos o semánticos no genera TAC.
