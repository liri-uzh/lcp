# Glossary

## Corpus

A corpus is a collection of represenation of things or facts of the real world. A typical text corpus, for example, will be a collection of actual texts that were produced at some point. While for textual corpora this may appear trivial, it is not so much the case for

## Anchoring

This term is used interchangeable with [**dimension**](#dimension).


## Annotation (vs. Data)

A corpus contains representation of things, or facts. However, in most cases, these data are ``enriched'' by information that is not there in the primary data. As is

## Dimension

A dimension is one of the three conceptual axes along which data and annotations are positioned in LCP: **Text**, **Time**, and **Space**.

## Layer

The term "layer" should always be qualified to clarify what it refers to. Often, it will occur in the phrase "**annotation layer**", in which case it refers to a level of representation of the data that corpus creators can define arbitrarily.

Mostly in LCP a 'Layer' designates an abstract class of entities - see [this page](data_structure.md#layers) for more details.

Alternatively, the term "layer" could be understood as synonymous with "tier" or "track", as can be seen in tools such as ELAN, or in the timeline of VideoScope for example. Although the timeline can dedicate a single track to display the annotations of one annotation layer in the corpus, that need not be the case, and there is **no** systematic one-to-one correspondance between the annotation layers of a corpus and the tracks of a timeline.

## Track

The term "track", in this documentation, refers to a horizontal band that can report a variety of annotations in the timeline of a time-aligned corpus, as can be seen in VideoScope. For example, the timeline of a given document involving three speakers in a corpus could consist of three tracks, one track per speaker, which would report their respective sentences. Such a corpus need not define three corresponding _annotation layers_ (see above); instead, it most likely would have a single annotation layer grouping all the sentences of all the speaker, with an _attribute_ on that annotation layer serving to identify which speaker is associated with it.

## Entity

If the term "entity" is used in the context of [DQD queries](dqd.md), it reflects the idea of [Entity-Relationship models](https://en.wikipedia.org/wiki/Entity%E2%80%93relationship_model). An entity is a unit that can have a _label_, constraints, and relate to other entities in the query. While most entities in DQD queries are directly associated to an _annotation layer_, the terms are not synonymous: for example, a DQD query can instantiate multiple entities on the same annotation layer (typically, multiple instances of the Token layer) and some entities do not match a single annotation layer unit: [sequences](sequence.md), [sets](set.md) or [groups](group.md) are entities in and of themselves (e.g. they can receive labels) but they contain _multiple_ units (for example, a sequence of several consecutive tokens).
If used outside the context of DQD, especiall in this documentation, 'entity' is used with its conventional meaning, i.e. *a concrete, existing thing, as distinguished from a mere function, or property*.

## Unit

This term has two meanings:
 1. This term is used in the JSON representation of queries for to introduce entities that correspond to single annotation layer units: one token instance, one segment instance, etc.
 2. Furthermore, in the [Corpus Template](corpus-template.md) it specifies on of the Layer types: 'Unit' Layers are base layers, i.e. instances of those layers cannot be broken up into smaller entities (e.g. *Tokens* in a typical text corpus). This is in contrast to the other layer types 'span' (a layer that comprises sequential instances of other layers (e.g. *Segments* span *Tokens*)) and 'relation' (a layer that connects non-contiguous instances of other layers (e.g. a *Dependency Relation* connects two *Tokens*, that are not necessarily next to each other)).

## Metadata

There are at least two meaning of _meta(data)_ in LCP:

 1. The metadata of a **corpus**, as visible when clicking it from the homepage, and stored in the main database table
 2. The metadata on the **annotation layers** of a corpus, which need to be further distinguished:
    - outside of LCP, some people call "metadata" any non-standard annotation, such as optional comments associated with each token in an OCR corpus (as opposed to, say, _form_ and _lemma_, which are standard annotations for tokens); LCP has no such **pre**-conceived opposition between standard vs. metadata
    - on each annotation layer, the author of a corpus can decide to place attributes under a `meta` key, in which case the data is represented (and queried) differently in the database

