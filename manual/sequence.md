# `sequence`

One can use the keyword [`sequence`](sequence.md) to look for consecutive entities. The query below, for example, looks for artciles that are _immediately_ followed by the word "dogs". Note that `sequence` also accepts the [`@`](../dqd.md) operator (all entities defined in the sequence must then be part of the referenced entity) and labels for future references to the sequence.

```
Segment s

sequence@s seq
    Token t1
        upos = "DET"
    Token t2
        form = "dogs"
```

## Repetitions and nesting

The `sequence` keyword also accepts a _repetition_ operator of the form `n..m` to look for `n` to `m` occurrences of the defined sequence. Use `0` for `n` to make the sequence optional, and `*` for `m` to allow for an arbitrary number of repetitions.

The repetition operator would normally only prove useful when a sequence is _nested_ within another sequence, as in:

```
Segment s

sequence@s seq
    Token t1
        upos = "DET"
    sequence 0..*
        sequence 0..1
            Token
                upos = "ADV"
        Token
            upos = "ADJ"
    Token t2
        form = "dogs"
```

This query looks for sequences (labeled `seq`) which start with a determiner and end with the word "dogs"; between these two tokens can _optionally_ appear a subsequence any number of times (`sequence 0..*`). That subsequence ends with an adjective, which can be optionally preceded by at most one adverb (`sequence 0..1`). As a result, this query would match not only `the dogs`, but also `some cute dogs` or even `the almost extinct wild dogs`.

Note that subsequences in the scope of a main `sequence` keyword that is already bound by the `@` oeprator necessarily inherit that scope, so we don't need to repeat the `@` operator on the nested `sequence` keywords. We also decided not to give a label to the sub-sequences, for we did not need to reference them anywhere; moreoever, because these subsequences are quantified expressions (cf. their repetition operators) the tokens they contain are bound variables and, as such, cannot be referenced outside of the scope of those subsequences (accordingly, we didn't label those tokens either).
