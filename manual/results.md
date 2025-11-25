# Results

There is no formal separation between the query part and the results part of a DQD script, other than the convention of writing the results part after the query part. Results blocks always start with a variable name, a fat arrow (`=>`) and one of the three keywords [`plain`](results.md), [`analysis`](results.md) or [`collocation`](results.md).

## `plain`

The `plain` keyword will give you back matching entities in the context in which they occur. It is formed of two sub-blocks defined by the keywords `context` and `entities`. `entities` should reference variable names of the matching entities you are interested in, and `context` should reference a variable name of a matching entity that contains the ones in `entities`.

The example below repeats the query part from the [[#DepRel|DepRel]] section and adds a simple `plain` results part, which asks to show each possible pair of the (possibly inflected) verb _take_ with an object of its, shown in the context of the segment that contains them.

```
Segment s

Token@s t1
    upos = "VERB"
    lemma = "take"
      
Token@s tx
    DepRel
        head = t1
        dep = tx
        label = "dobj"


myKWIC1 => plain
    context
        s
    entities
        t1
        tx
```

The LCP will display the results in a tab named _myKWIC1_, as specified by the variable name before the fat arrow. That tab will show one segment per row, in which the instances of _take_ and its object will be highlighted.

## `analysis`

The `analysis` keyword will give you back a statistical transformation of attributes, optionally filtered. It is formed of two (optionally three) sub-blocks defined by the keywords `attributes` and `functions` (and optionally `filter`). `attributes` should reference attributes of entities, using the format `entity_variable.attribute`, that the statistical transformations will be applied to. `functions` should reference one or more function names that apply a statistical transformation: `frequency`, `minimum`, `maximum`, `average` or `stddev`. **Note that LCP currently only supports the function `frequency`.** Finally, the optional `filter` block lets you exclude some lines from the results; for example, specifying `frequency > 5` in the `filter` block below has the effect of excluding lemmas that appear less than 6 times from the `myStat1` table.

Example:

```
myStat1 => analysis
    attributes
        tv.lemma
        to.lemma
    functions
        frequency
    filter
        frequency > 5
```

The LCP will display the results in a tab named _myStat1_, as specified by the variable name before the fat arrow. That tab shows one lemma per row, along with how many times that lemma occurs in the queried corpus (as long as it occurs at least 6 times).


## `collocation`

The `collocation` keyword returns a table listing how often entities appear near the referenced entity/entities. It comes in two different formats:

  - One option is to provide a `center` sub-block and a `window` sub-block. `center` should reference an entity variable (eg `t1`) and `window` should specify how many entities ahead and behind of that reference entity the collocation measure should be performed (eg `-2..2`)
  - Another option is to provide a `space` sub-block which should reference the name of a `set`, in which case the collocation measure will be performed within all the entities in the set.

Examples:

```
myColl1 => collocation
    center
        t1
    window
        -2..+2
    attribute
        lemma
```

LCP displays the results in a tab named _myColl1_, as specified by the variable name before the fat arrow. That tab will show one lemma per row, along with how many times that lemma co-occurs within 2 tokens ahead and 2 tokens behind the `t1` matches.

```
Document d

Segment@d s

Token@s t
    xpos2 = "SUBST"

set prox
    Token@s tx
        position(tx) > position(t) - 20
        position(tx) < position(t) + 20
        tx != t

subst => plain
    context
        s
    entities
        t

nearSubst => collocation
    space
        prox
    attribute
        form
```

The results tab named _nearSubst_ will report how many times each form of a token within 20 characters of `t` co-occcurs with it.