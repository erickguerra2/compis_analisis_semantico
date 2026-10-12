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
| objetos | `t0 = new C` (reserva sin llamar al constructor), `t0 = o.campo`, `o.campo = y` |
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
- El programa principal se llama `main`; las funciones anidadas usan
  `externa.interna`, los métodos `Clase.metodo` y los constructores
  `Clase.constructor`. `this` conserva ese nombre.
- Los campos de clase no se renombran: se acceden como `obj.campo`.

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

## Estructuras de control

La condición de `if`, `while`, `do-while` y `for` se evalúa a un operando, se
usa en el salto y se libera. Si la condición es una variable se usa
directamente, sin copiarla a un temporal. Las etiquetas de cada construcción se
numeran en el orden en que aparecen en su patrón.

`if` con `else`; sin `else` el salto va directo a `Lend` y no hay `goto`:

```text
<cond → c>
ifFalse c goto Lelse
<then>
goto Lend
Lelse:
<else>
Lend:
```

`while` (`continue` salta a `Lstart`, `break` a `Lend`):

```text
Lstart:
<cond → c>
ifFalse c goto Lend
<cuerpo>
goto Lstart
Lend:
```

`do-while` (`continue` salta a `Lcont`, `break` a `Lend`):

```text
Lstart:
<cuerpo>
Lcont:
<cond → c>
if c goto Lstart
Lend:
```

`for` (`continue` salta a `Lcont`, `break` a `Lend`). La condición y la
actualización son opcionales; sin condición no se emite el `ifFalse`:

```text
<init>
Lstart:
<cond → c>
ifFalse c goto Lend
<cuerpo>
Lcont:
<actualización>
goto Lstart
Lend:
```

Por ejemplo, `for (let i = 0; i < 3; i = i + 1) { print(i); }` produce:

```text
i = 0
L0:
t0 = i < 3
ifFalse t0 goto L2
print i
L1:
t0 = i + 1
i = t0
goto L0
L2:
```

`switch` evalúa su expresión una sola vez y la compara con cada `case` en
orden. El operando de la expresión se mantiene vivo durante las comparaciones:

```text
<expr → s>
t = s == <expr del case 0>
if t goto Lcase_0
t = s == <expr del case 1>
if t goto Lcase_1
goto Ldefault
Lcase_0:
<cuerpo del case 0>
Lcase_1:
<cuerpo del case 1>
Ldefault:
<cuerpo del default>
Lend:
```

Sin `default`, el salto posterior a las comparaciones va a `Lend`. Entre los
cuerpos no hay saltos, así que la ejecución cae al siguiente `case`
(fall-through) hasta encontrar un `break`. `break` sale de la construcción más
cercana, sea ciclo o `switch`; `continue` dentro de un `switch` va al ciclo que
lo contiene.

## Excepciones

| Instrucción | Significado |
|---|---|
| `try_begin L0` | registra `L0` como handler activo |
| `try_end` | desregistra el handler activo más reciente |
| `throw .str0` | salta al handler activo con el string como mensaje; sin handler, el programa termina e imprime el mensaje |
| `catch err` | primera instrucción de un handler: guarda el mensaje en `err` |

`try/catch`:

```text
try_begin Lcatch
<bloque try>
try_end
goto Lend
Lcatch:
catch err
<bloque catch>
Lend:
```

La variable del `catch` es de tipo `string`, ya está inicializada y solo existe
dentro del bloque `catch`. Si su nombre ya estaba en uso, se renombra como
cualquier otra declaración (`err_1`).

Un `break` o `continue` que abandona un `try` emite antes del `goto` un
`try_end` por cada `try` abierto desde que se entró al ciclo o `switch` de
destino, para que no queden handlers registrados:

```text
try_begin L2
t0 = i == 2
ifFalse t0 goto L4
try_end
goto L1
L4:
try_end
goto L3
L2:
catch e
print e
L3:
```

Un salto que no sale del `try` (por ejemplo, el `break` de un ciclo que está
dentro del bloque `try`) no emite `try_end`.

## Funciones y llamadas

Las declaraciones se agregan a `pending`: primero se emite `main` y luego las
funciones en el orden en que se encontraron. Al emitir una función externa, sus
funciones anidadas se agregan al final de la cola. Los nombres de código son
`f`, `externa.interna` y `Clase.metodo`. Cada unidad reinicia los temporales;
las etiquetas de control conservan su contador global.

Los argumentos se evalúan de izquierda a derecha y todos sus operandos se
conservan hasta emitir todos los `param` en ese orden. Después se liberan sus
temporales y se emite `call`. Las llamadas a funciones sin tipo de retorno no
tienen resultado.

```text
begin_func main
param 1
param 2
t0 = call add, 2
print t0
end_func main
begin_func add
t0 = a + b
return t0
end_func add
```

`return e` evalúa `e`, emite un `try_end` por cada handler activo en esa
función, emite `return e` y libera el temporal consumido. `return;` no lleva
operando. Se agrega un `return` sin operando al final de una función si su
última instrucción no es un `return`. No se genera TAC con errores semánticos,
incluidos argumentos inválidos y retornos fuera de una función.

## Clases y objetos

Una declaración de clase no emite nada en el sitio donde aparece. Sus métodos
(incluido `constructor`) se agregan a `pending` en orden de declaración y se
emiten como unidades `Clase.metodo` después de `main`. Dentro de un método,
`this` es el parámetro 0 y se escribe `this`.

`new C(a1, a2)` reserva el objeto, ejecuta los inicializadores de campos de la
clase raíz hacia `C` y llama al constructor con el objeto como primer
parámetro. El resultado de la expresión es el temporal del objeto:

```text
t0 = new C
t0.campo = <expr>          (un inicializador por campo, de la raíz a C)
<evalúa a1 → o1>
<evalúa a2 → o2>
param t0
param o1
param o2
call K.constructor, 3
```

`K` es la clase más cercana a `C`, subiendo por la herencia, que declara
`constructor`; si ninguna lo declara no se emite la llamada. Un campo sin
inicializador no genera instrucción: `new` entrega la memoria en cero, que
equivale a `0`, `false` o `null` según el tipo.

Una llamada a método `obj.m(a)` empuja primero el receptor y después los
argumentos, y llama a `K.m` con `n + 1` parámetros. `K` es la clase más
cercana a la del tipo declarado de `obj` que declara `m`, así que un método
heredado se llama con el nombre de la clase que lo define y una variable de
tipo base llama a la versión de la base (despacho estático):

```text
class Animal { ... function speak(): string { ... } }
class Dog : Animal { function speak(): string { ... } }
let d: Dog = new Dog("Rex");
let a: Animal = d;
print(d.speak());
print(a.speak());
```

```text
t0 = new Dog
param t0
param .str0
call Animal.constructor, 2
d = t0
a = d
param d
t0 = call Dog.speak, 1
print t0
param a
t0 = call Animal.speak, 1
print t0
```

Lectura y escritura de campos:

| Fuente | TAC |
|---|---|
| `this.nombre = x;` | `this.nombre = x` |
| `print(this.nombre);` | `t0 = this.nombre`, `print t0` |
| `let v = a.b.c;` | `t0 = a.b`, `t0 = t0.c`, `v = t0` |
| `a.b.c = 1;` | `t0 = a.b`, `t0.c = 1` |

## Arreglos

Un literal reserva el arreglo con su número de elementos y escribe cada uno.
Los literales anidados producen un arreglo por fila:

```text
let m = [[1, 2], [3]];

t0 = new_array 2
t1 = new_array 2
t1[0] = 1
t1[1] = 2
t0[0] = t1
t1 = new_array 1
t1[0] = 3
t0[1] = t1
m = t0
```

Toda lectura y escritura por índice verifica primero el rango con `bounds`. En
un acceso multidimensional se verifica cada nivel:

| Fuente | TAC |
|---|---|
| `print(a[i]);` | `bounds a, i`, `t0 = a[i]`, `print t0` |
| `a[i] = y;` | `bounds a, i`, `a[i] = y` |
| `print(m[i][j]);` | `bounds m, i`, `t0 = m[i]`, `bounds t0, j`, `t0 = t0[j]`, `print t0` |

En una asignación a un campo o a un elemento se evalúa primero el valor de la
derecha y después el destino, igual que en la asignación a variables. El valor
de la expresión es el valor asignado, así que `let x = a[0] = 5;` produce
`bounds a, 0`, `a[0] = 5` y `x = 5`.

## foreach

El arreglo se guarda en un temporal antes de empezar, de modo que reasignar la
variable original dentro del cuerpo no cambia el recorrido. Si la expresión ya
es un temporal (por ejemplo, el resultado de una llamada) se usa sin copiarlo.
El arreglo, su longitud y el contador se mantienen vivos todo el ciclo y se
liberan en `Lend`:

```text
ta = <expr>
tn = len ta
ti = 0
Lstart:
tc = ti < tn
ifFalse tc goto Lend
item = ta[ti]
<cuerpo>
Lcont:
ti = ti + 1
goto Lstart
Lend:
```

`continue` salta a `Lcont` y `break` a `Lend`. La lectura `ta[ti]` no lleva
`bounds` porque el contador siempre está dentro del rango. La variable de
iteración es la que declara el analizador en el ámbito del `foreach` y se
renombra como cualquier otra declaración (`n_1` si `n` ya existía).

## Errores en tiempo de ejecución

El único error que detecta el programa generado es el acceso fuera de rango.
`bounds a, i` falla si `i < 0` o `i >= len a` con el mensaje
`"indice fuera de rango"`, que se registra en la zona de datos la primera vez
que se emite un `bounds`. Si hay un `try_begin` activo, el programa salta a su
handler y `catch err` guarda ahí el mensaje; si no hay ninguno, el programa
termina e imprime el mensaje. Es el ejemplo del enunciado:

```text
let lista = [1, 2, 3];
try { let peligro = lista[100]; } catch (err) { print("Error atrapado: " + err); }
```

```text
.data
    .str0: "indice fuera de rango"
    .str1: "Error atrapado: "
.code
    ...
    try_begin L0
    bounds lista, 100
    t0 = lista[100]
    peligro = t0
    try_end
    goto L1
    L0:
    catch err
    t0 = concat .str1, err
    print t0
    L1:
```

`throw` no tiene sintaxis en Compiscript: es el salto que la fase de MIPS
genera al expandir `bounds`.

## Memoria y registros de activación

`MemoryLayout` recorre el árbol anotado y los scopes conservados del
analizador. Los símbolos reciben `offset`, `size`, `label`, `storage` y
`depth`. `label` solo se asigna a funciones y métodos. Los valores integer,
boolean y las referencias (string, arreglos, objetos y null) ocupan 4 bytes;
`size_of` expone ese contrato.

Las variables fuera de funciones se ubican en el segmento global, con offset
`4*k` en orden de declaración y `depth=0`. Los bloques de nivel superior
también usan almacenamiento global. Los locales de bloques hermanos no
reutilizan espacio.

| Slot | Offset desde fp |
|---|---|
| Dirección de retorno | 0 |
| Enlace de control (fp del llamador) | 4 |
| Enlace de acceso (fp del contenedor léxico) | 8 |
| Parámetro i | 12 + 4*i |
| Local k | 12 + 4*nparams + 4*k |
| Temporal tN | 12 + 4*(nparams + nlocales) + 4*N |

`ActivationRecord.size` es `12 + 4*(nparams + nlocales + ntemporals)`. El
número de temporales se completa después de generar TAC con
`emitter.function_temps`. `main` tiene registro para sus temporales, mientras
sus variables se almacenan en el segmento global. En los métodos `this` ocupa
el parámetro 0 (offset 12), así que el primer parámetro declarado queda en el
offset 16.

Un local de función de nivel superior tiene `depth=1`, uno de función anidada
`depth=2`, etc. El enlace de acceso de una función de nivel superior es 0; una
función anidada apunta a su contenedor léxico, identificado por
`ActivationRecord.access_parent`. El acceso a una variable externa usa su
profundidad para seguir esos enlaces en la fase de MIPS. No se generan closures
como valores de primera clase.

Los campos tienen `storage=field` y su offset se mide desde la base del objeto:
primero los heredados, en el orden de la clase padre, y luego los propios. Un
campo que la subclase vuelve a declarar reutiliza el slot del heredado. El
símbolo de la clase guarda el tamaño del objeto (`4 * ncampos`, sin
encabezado) y `analyzer.class_layouts` guarda la lista de campos de cada clase:

| Clase | Campos (offset) | Tamaño |
|---|---|---|
| `class A { let x: integer; let y: string; }` | `x@0`, `y@4` | 8 |
| `class B : A { let z: boolean; }` | `x@0`, `y@4`, `z@8` | 12 |

Los arreglos almacenan la longitud en el offset 0 y el elemento `i` en
`4 + 4*i`. Los strings referencian la zona de datos; `concat` y `to_str`
producen referencias nuevas.

El IDE expone los cinco campos de memoria en la tabla de símbolos y muestra los
registros de activación con parámetros, locales, temporales y slots de
control. `POST /compile` incluye `activationRecords`; si no se genera TAC la
lista está vacía.

## Supuestos

- Las funciones no son valores de primera clase (la gramática no tiene tipo
  función), así que los closures del enunciado se reducen a funciones anidadas
  que leen variables de la función externa por enlace de acceso.
- No se comprueba división entre cero; el comportamiento queda indefinido.
- El despacho de métodos es estático según el tipo declarado del receptor; no
  hay polimorfismo dinámico ni tabla de métodos virtuales.
- El constructor se hereda: si la clase no declara `constructor` se usa el del
  ancestro más cercano que lo declare.
- `new` entrega la memoria del objeto en cero; los campos sin inicializador
  valen `0`, `false` o `null`.
- En una asignación se evalúa primero el valor y después el destino.
- El único error en tiempo de ejecución es el índice fuera de rango.
- Un programa con errores léxicos, sintácticos o semánticos no genera TAC.
