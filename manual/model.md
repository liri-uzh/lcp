# Data model

A key goal of LCP is to allow storage of very diverse corpora (simple and richly annotated; text-based or audiovisual; hundreds or billions of words) within a common structure, and to provide interfaces that allow querying these corpora for linguistic information via both web-browser and API. To that end, LCP models all corpora in a similar way. All data and annotations stored according to this data model are linearized and unambiguously positioned along at least one of three dimensions.

## Dimensions

Annotations and data must be aligned along at least one of three dimension:

1. **Text**: traditional text corpora, comprised of (generally large amounts) of text data and annotations
2. **Time**: audio/video corpora, where words are situation along a timeline
3. **Space**: multimodal corpora, where text is positioned on spatial coordinates, such as a position on a page.

These are explained in more detail below.
  
### Textual dimension

An entity being aligned to the text dimension simply means that the entity has a textual representation - e.g. tokens in a conventional text corpus: LCP concpetionally flattens all text in a corpus (= all text is concatenated into one large "string"), and for each *Token* its single, unambiguous spot, that can be described by means of a start and end position in that text stream is computed.
These positions allows for quick and simple comparisons between *Tokens* (e.g. *does Token B follow Token A?*), as well as other Layers that are textually anchored (e.g. 'does Document X contain Token A?').

### Temporal dimension

Entities that can be temporally located, are aligned relative to the time axis. E.g. in a video corpus with annotated gestures, each *Gesture* has an unambiguous start and end time point relative to the video (in fact, if the corpus contains several videos, then all videos are put in a (potentially arbitrary) sequential order and all entities are positioned relative to the global start point).

### Spatial dimension

Lastly, entities can occupy a section on a 2-dimensional plane: E.g. on a scanned medieval document, each *Token* can be unambiguously located by its x- and y-coordinate.

It is important to understand that layers can have several anchorings: In a transcribed speech corpus, *Tokens* are located in the text dimension on the one hand, and they occupy also a position along the time axis (of course only, if this time information has been annotated on the token level); thus, they can serve as a "link" between the two dimensions, and queries where purely temporal and textual entities are combined are possible: `Show me all Tokens of form X that overlap with a Gesture Y`.

## Layers

A *layer* is an abstract class of things: *Token* is e.g. a layer, that contains all instances of tokens.
Through a layer definition, users can specify which attributes (see [below](model.md#attributes)) individual instances of it can or must have: E.g. a *Token* must always have form; or a *Gesture* must always have one of the types [X, Y, Z].
Layers are defined in the [Corpus Template](corpus-template.md). Though arbitrary names can be used, we use *Document* for documents, *Segment* for sentence segments and *Token* for tokens in the examples. As a convention to distinguish between layer names and e.g. variables in DQD queries, layer names are expected to start with an uppercase character.

## Attributes

Attributes are also defined in the [Corpus Template](corpus-template.md) and thus their naming is free for a corpus creator to define. As a standard set, we use *form* for word forms, *lemma* for lemmas, *upos* for [Universal part-of-speech tags](https://universaldependencies.org/u/pos/all.html), and *morph* for [Universal features](https://universaldependencies.org/u/feat/all.html). Attributes stored as [Meta Data](meta-data.md) is mapped to regular attributes unless a native attribute with the same name exists. In that case, the meta attribute needs to be explicitely referenced.

