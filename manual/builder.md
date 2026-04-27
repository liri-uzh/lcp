# Corpus builder

The tool `lcpcli` ships with a helper python class `Corpus` to prepare LCP corpora.

The [tutorial](import_tutorial_part1.md) uses the `Corpus` class to process SRT files and import a video corpus into LCP.

The following repositories also use the `Corpus` class to convert existing data sets:

 - [XML-to-LCP conversion of NOAH's Corpus](https://github.com/liri-uzh/lcpimport_noah_corpus)
 - [TEI-to-LCP conversion of OFROM](https://github.com/liri-uzh/lcpimport_ofrom)
 - [Conversion of Alto-XML scanned documents to LCP](https://github.com/liri-uzh/lcpimport_erara44085)

The various [tests in the `lcpcli` repository](https://github.com/liri-uzh/lcpcli/tree/main/tests) give concrete examples on how to use the `Corpus` class.

## `Corpus`

You need to instantiate the `Corpus` class to create a new corpus.

Arguments:

 - `name` (`str`, mandatory) is the name of the corpus
 - `document` (`str`, optional, default `"Document"`) is the name of the document-level layer of the corpus
 - `segment` (`str`, optional, default `"Segment"`) is the name of the sentence-level layer of the corpus
 - `token` (`str`, optional, default `"Token"`) is the name of the word-level layer of the corpus
 - `authors` (`str`, optional, default `"placeholder"`) is the name(s) of the author(s) of the corpus
 - `institution` (`str`, optional, default `""`) is the name of the institution associated with the corpus
 - `description` (`str`, optional, default `""`) is a description of the corpus, as it will be presented to end users
 - `date` (`str`, optional, default `"placeholder"`) is the date when the corpus was curated
 - `revision` (`int | float`, optional, default `1`) is the revision number of the corpus
 - `url` (`str`, optional, default `"placeholder"`) is the source URL of the corpus
 - `license` (`str | None`, optional, default `None`) is the code of the license of the corpus

The values of `authors`, `institution`, `description`, `date`, `revision`, `url` and `license` can be modified in LCP after import.

**Example**

```python
from lcpcli.builder import Corpus

c = Corpus("my great corpus", document="Book", segment="Sentence", token="Word")
```

### Instance methods

An instance of the `Corpus` class has an open set of methods, which should all start with a capital letter, and which will create and return an entity in the corpus with the passed attributes (an instance of the class `Layer`)

All corpora should create at least one entity by calling each of the methods named after the values passed as `document`, `segment` and `token` when instantiating the `Corpus` class.

**Example**

```python
from lcpcli.builder import Corpus

c = Corpus("my great corpus")

c.Document(
    c.Segment(
        c.Token("hello"),
        c.Token("world")
    )
)

c.make("path/to/output/")
```

#### `make`

Writes all the CSV files and the configuration JSON file of the corpus to the passed directory.

The `make` method is the only valid method on a `Corpus` instance that starts with a non-capital letter.

Arguments:

 - `destination` (`str`, mandatory) is a path where to place the output files
 - `is_global` (`dict`, optional, default `{}`) maps layers to attribute names whose possible values are defined globally, such as the [`upos` on tokens](https://universaldependencies.org/u/pos/)

Returns `None`

## `Layer` class

This class is never instantiated explicitly (as in `Layer(...)`). Instances of the `Layer` class are returned by calling a method that starts with a capital letter on an instance of `Corpus`, or on another `Layer` instance.

Upon instantiation, pass named arguments to create corresponding attributes on the entity, as in `corpus.Document(title="my document", year=2026)`. There are three special instantiation cases:

1. When instantiating **tokens**, you should pass a string as the sole unnamed argument to represent the form, as in `corpus.Token("is", lemma="be")`.
2. When instantiating **segments**, you can pass token instances as unnamed arguments, as in `document.Segment(corpus.Token("hello"), corpus.Token("world"))`.
3. You can pass a dictionary as the sole unnamed argument (and _no_ named argument) to create a `GlobalAttribute` instance instead of a `Layer` instance, as in `corpus.Speaker({"id": "johndoe", "firstname": "John", "lastname": "Doe"})`

### Instance methods

Just like `Corpus` instances, `Layer` instances have an open set of methods, which should all start with a capital letter, and which will create and return a new `Layer` instance.

In addition, `Layer` instances come with the methods listed below.

#### `make`

If called with **no argument**: makes the instance (and its children) in the destination corpus and will clear it from memory as soon as possible.

If call with **multiple unnamed arguments**: each argument should be a `Layer` instance with at least one attribute that points to another `Layer` instance. This is typically used for token dependency relations in a segment (see example below).

Arguments:

 - `child`: (`Layer`, mandatory) a `Layer` instance to add as a child of the current instance.


Returns:

 - the same `Layer` instance it was called on


Examples:

_Normal layer_

```python
s = c.Segment(c.Token("hello"), c.Token("world"))
s.make() # makes the segment and the tokens
```

_Dependency realtions_

```python
t1 = c.Token("the")
t2 = c.Token("cat")
s = c.Segment(t1, t2)
s.make()
c.DepRel.make(
    c.DepRel(dependent=t1, udep="root"),
    c.DepRel(head=t2, dependent=t1, udep="detj")
)
```


#### `add`

Adds a `Layer` instance as a child of the current instance.

Arguments:

 - `child`: (`Layer`, mandatory) a `Layer` instance to add as a child of the current instance.

Returns:

 - the same `Layer` instance it was called on

Example:

```python
s = c.Segment()
t = c.Token("hello")
# Add the token as a child of the segment
s.add(t)
```

#### `set_media`

Call this on a `Layer` instance at the document level to associate with a media file.

Arguments:

 - `name` (`str`, mandatory) is an arbitrary name for the media field
 - `filename` (`str`, mandatory) is the filename of the media file associated with the current document. It can be an audio or a video file.

Returns:

 - the same `Layer` instance it was called on

Example:

```python
d = c.Document(title="Interview with the vampire")
d.set_media("interview", "vampire.mp4")
```


#### `set_char`

Sets the character anchoring of the current instance. It is usually not necessary to call this manually, since the character axis is determined by the forms in the token sequence of the corpus; however, one can use `set_char` to add _parallel_ annotations on that axis.

Arguments:

 - `left` (`int`) is the index of the left anchor on the character axis
 - `right` (`int`) is the index of the right anchor on the character axis

Returns:

 - the same `Layer` instance it was called on

Example:

```python
forms = " ".split("the LCP corpus")
tokens = [c.Token(f) for f in forms]
s = c.Segment(*tokens)
# making the segment anchors the tokens
s.make()
ne = c.NamedEntity(form=forms[1])
# set the named entity to overlap with the "LCP" token
ne.set_char(tokens[1].get_char())
```

#### `get_char`

Returns the left and right anchors of the current layer entity on the character axis.

Return type: `tuple[int, int]`

Example:

```python
forms = " ".split("the LCP corpus")
tokens = [c.Token(f) for f in forms]
s = c.Segment(*tokens)
# making the segment anchors the tokens
s.make()
ne = c.NamedEntity(form=forms[1])
# set the named entity to overlap with the "LCP" token
ne.set_char(tokens[1].get_char())
```

#### `set_time`

Sets the time anchoring of the current instance.

Arguments:

 - `start` (`int`) is the index of the left anchor on the time axis (in seconds times 25)
 - `end` (`int`) is the index of the right anchor on the time axis (in seconds times 25)

Returns:

 - the same `Layer` instance it was called on

Example:

```python
transcript = [
    {
        "form": "hello",
        "start": 0.0,
        "end": 0.4
    },
    {
        "form": "world",
        "start": 0.45,
        "end": 0.8
    },
]
tokens = []
for t in transcript:
    token = c.Token(t['form'])
    token.set_time(int(t['start'] * 25), int(t['end'] * 25))
s = c.Segment(*token)
s.make() # inherits the start and end time anchors from the tokens
```

#### `get_time`

Returns the start and end time anchors of the current layer entity (in seconds times 25).

Return type: `tuple[int, int]`

Example:

```python
# store the end time of the current document in offset
_, offset = doc.get_time()
# create a new document
doc = c.Document(name="Second Document")
doc.set_media("interview", "vampire.mp4")
hello = c.Token("hello")
world = c.Token("world")
hello.set_time(offset + 0, offset + 10)
world.set_time(offset + 11, offset + 20)
s = doc.Segment(hello, world)
s.make() # inherits the start and end time anchors from the tokens
doc.make() # inherits the start and end time anchors from the sentence
```

#### `set_xy`

Sets the (X1,Y1,X2,Y2) plane anchoring of the current instance, typically used to map annotations to areas of images.

Take care of offsetting the annotations of separate documents so they do not overlap, on the horizontal axis, on the vertical axis, or both.

Arguments:

 - `x1` (`int`) is the left-most point of the annotation area
 - `y1` (`int`) is the top-most point of the annotation area
 - `x2` (`int`) is the right-most point of the annotation area
 - `y2` (`int`) is the bottom-most point of the annotation area

Returns:

 - the same `Layer` instance it was called on

Example:

```python
p = c.Page(name="Page 1", image="file.png")
p._attributes["image"]._type = "image" # force an image type on this attribute
p.set_xy(0, 0, 100, 50) # a 100x50px document
s = p.Segment()
hello = s.Token("hello")
world = s.Token("world")
hello.set_xy(10, 10, 33, 40)
world.set_xy(50, 10, 90, 40)
s.make() # s inherits the plane anchoring from its tokens 
p.make() # the page's anchors were explicitly set above
```

#### `get_xy`

Returns the (X1,Y1,X2,Y2) plane anchors of the current instance.

Return type: `tuple[int, int, int, int]`

Example:

```python
_, _, offset, _ = p.get_xy() # horizontal offset
p = c.Page(name="Page 2", image="file2.png")
p.set_xy(offset + 0, 0, offset + 100, 50)
```

## `GlobalAttribute` class

Pass a dictionary as the sole unnamed argument (and _no_ named argument) of a new-layer method to create a `GlobalAttribute` instance instead. You can then pass this an attribute of multiple layers.

Arguments:

 - `attributes` (`dict`) is a key-value dictionary of the global attribute's sub-attributes.

Example:

```python
jane = c.Speaker({"firstname": "Jane", "lastname": "Doe"})
john = c.Speaker({"firstname": "John", "lastname": "Doe"})
s1 = doc.Segment(c.Token("Hello"), c.Token("world"), speaker=jane)
s2 = doc.Segment(c.Token("Bye"), c.Token("people"), speaker=john)
s3 = doc.Segment(c.Token("So"), c.Token("long"), speaker=john)
s1.make()
s2.make()
s3.make()
```