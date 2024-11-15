# `set`


By default, each block matches one corresponding occurrence at a time. This means that the query below will match each possible pair of a verb with any of its (possibly many) dependencies as a separate result.

```
Segment s

Token@s tv
    upos = "VERB"

Token@s to
    DepRel
        head = tv
        dep = to
```

Say your corpus contains a segment with this sequence of tokens: `Moisha gave you something`. Assuming standard dependency relations, the query will match `s = <Moisha gave you something>, tv = <gave>, to = <you>`, but it will also match `s = <Moisha gave you something>, tv = <gave>, to = <something>` as a separate result; indeed, the latter triplet is different from the former and, as such, it constitutes a distinct match, even though the segment and the first token are the same in both matches

If you'd rather capture all possible dependencies of the verb as part of the same, single match, you can declare the corresponding `Token` block inside a [`set`](set.md) block:

```
Segment s

Token@s tv
    upos = "VERB"

set tos
    Token@s to
        DepRel
            head = tv
            dep = to
```

This query will now match `Moisha gave you something` with `s = <Moisha gave you something>, tv = <gave>, tos = [<you>,<something>]`, and that's it!

One way to understand this behavior is that blocks that start with a name of a layer, such as a `Token` block, are existentially bound and implicitly conjoined. Having two successive `Token` blocks roughly means "//any// token such that {this} **and** //any// token such that {that}". The keyword `set`, however, can be seen as carrying a universal force, so that when a `Token` block is embedded inside a `set` block, it becomes bound by the universal quantification. The `set` block above would then roughly translate as "//all// the entities that correspond to [//any// token that depends on the verb]"
