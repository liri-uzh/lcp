# Importing

You can import your own corpora to LCP using a command-line tool called `lcpcli`. This page describes how to use it.

## LCP CLI module

> Command-line tool for converting CONLLU files and uploading the corpus to LCP

### Installation

Make sure you have python 3.11+ with `pip` installed in your local environment, then run

```bash
pip install lcpcli
```

### Usage

**Example:**

Corpus conversion:

```bash
lcpcli -i ~/conll_ext/ -o ~/upload/ -m upload
```

Data upload:

```bash
lcpcli -c ~/upload/ -k $API_KEY -s $API_SECRET -p my_project
```

**Help:**

```bash
lcpcli --help
```

`lcpcli` takes a corpus of CoNLL-U (PLUS) files and imports it to a project created in an LCP instance, such as _catchphrase_.

Besides the standard token-level CoNLL-U fields (`form`, `lemma`, `upos`, `xpos`, `feats`, `head`, `deprel`, `deps`) one can also provide document- and sentence-level annotations using comment lines in the files (see [the CoNLL-U Format section](#conll-u-format))

A more advanced functionality, `lcpcli` supports annotations aligned at the character level, such as named entities. See [the Named Entities section](#character-aligned-annotations-(e.g.-named-entities)) for more information

#### Example corpus

`lcpcli` ships with an example one-video "corpus": the video is an excerpt from the CC-BY 3.0 "Big Buck Bunny" video ((c) copyright 2008, Blender Foundation / www.bigbuckbunny.org) and the "transcription" is a sample of the Declaration of the Human Rights

To populate a folder with the example data, use this command

```bash
lcpcli --example /destination/folder/
```

This will create a subfolder named *free_video_corpus* in */destination/folder* which, itself, contains two subfolders: *input* and *output*. The *input* subfolder contains four files: 
 - *doc.conllu* is a CoNLL-U Plus file that contains the textual data, with time alignments in seconds at the token- (`start` and `end` in the MISC column), segment- (`# start = ` and `# end = ` comments) and document-level (`#newdoc start =` and `#newdoc end =`)
 - *namedentity.tsv* is a tab-separated value lookup file that contains information about the named entities, where each row associates an ID reported in the `namedentity` token cells of *doc.conllu* with two attributes, `type` and `form`
 - *shot.tsv* is a tab-separated value file that defines time-aligned annotations about the shots in the video in the `view` column, where the `start` and `end` columns are timestamps, in seconds, relative to the document referenced in the `doc_id` column
 - *meta.json* is a JSON file that defines the structure of the corpus, used both for pre-processing the data before upload, and when adding the data to the LCP database. Read on for information on the definitions in this file


#### CoNLL-U Format

The CoNLL-U format is documented at: https://universaldependencies.org/format.html

The LCP CLI converter will treat all the comments that start with `# newdoc KEY = VALUE` as document-level attributes.
This means that if a CoNLL-U file contains the line `# newdoc author = Jane Doe`, then in LCP all the sentences from this file will be associated with a document whose `meta` attribute will contain `author: 'Jane Doe'`

All other comment lines following the format `# key = value` will add an entry to the `meta` attribute of the _segment_ corresponding to the sentence below that line (ie not at the document level)

The key-value pairs in the `MISC` column of a token line will go in the `meta` attribute of the corresponding token, with the exceptions of these key-value combinations:
 - `SpaceAfter=Yes` vs. `SpaceAfter=No` (case senstive) controls whether the token will be represented with a trailing space character in the database
 - `start=n.m|end=o.p` (case senstive) will align tokens, segments (sentences) and documents along a temporal axis, where `n.m` and `o.p` should be floating values in seconds

See below how to report all the attributes in the template `.json` file

##### CoNLL-U Plus

CoNLL-U Plus is an extension to the CoNLLU-U format documented at: https://universaldependencies.org/ext-format.html

If your files start with a comment line of the form `# global.columns = ID FORM LEMMA UPOS XPOS FEATS HEAD DEPREL DEPS MISC`, `lcpcli` will treat them as CoNLL-U Plus files and process the columns according to the names you set in that line


##### Annotations of sequences of tokens (e.g. Named Entities)

You can use `lcpcli` to define annotations on sequences of tokens below the segment level, for example named entities. To do so, you will need to prepare your corpus as CoNLL-U Plus files which must define a dedicated column, e.g. `namedentity`:

```conllu
## global.columns = ID FORM LEMMA UPOS XPOS FEATS HEAD DEPREL DEPS MISC namedentity
```

All the tokens belonging to the same named entity should report the same index in that column, or `_` (as per CoNLL-U conventions) if it doesn't belong to a named entity. For example:

```conllu
1	Adopted	adopt	VERB	V	Tense=Past|VerbForm=Part	0	root	_	start=2.20|end=2.30	_
2	and	and	CCONJ	CC	_	3	cc	_	start=2.30|end=2.35	_
3	proclaimed	proclaim	VERB	V	Tense=Past|VerbForm=Part	1	conj	_	start=2.38|end=2.45	_
4	by	by	ADP	E	_	7	case	_	start=2.45|end=2.50	_
5	General	general	ADJ	A	Degree=Pos	6	amod	_	start=2.55|end=2.75	1
6	Assembly	assembly	NOUN	S	Number=Sing	7	nmod	_	start=2.85|end=3.15	1
7	resolution	resolution	NOUN	S	Number=Sing	3	obl	_	start=3.20|end=3.22	_
8	217	217	NUM	N	NumType=Card	7	nummod	_	SpaceAfter=No|start=3.24|end=3.40	_
9	A	A	X	X	_	8	dep	_	start=3.42|end=3.44	_
10	(	(	PUNCT	FB	_	11	punct	_	SpaceAfter=No|start=3.44|end=3.45	_
11	III	third	ADJ	NO	Degree=Pos|NumType=Ord	8	amod	_	SpaceAfter=No|start=3.47|end=3.53	_
12	)	)	PUNCT	FB	_	11	punct	_	start=3.53|end=3.54	_
13	of	of	ADP	E	_	14	case	_	start=3.55|end=3.62	_
14	10	10	NUM	N	NumType=Card	7	nmod	_	start=3.75|end=4.07	2
15	December	December	PROPN	SP	_	14	flat	_	start=4.09|end=4.13	2
16	1948	1948	NUM	N	NumType=Card	14	flat	_	SpaceAfter=No|start=4.15|end=4.23	2
17	.	.	PUNCT	FS	_	1	punct	_	start=4.24|end=4.25	_
```

In this example, tokens 5-6 belong to the same named entity ("General Assembly") and "10 December 1948" forms another named entity.

The directory containing your corpus files should also include one TSV file named after that column: the filename should match the column name, all in lower-case, plus an extension (e.g. `.tsv`) -- in the example corpus, the column as reported in the first comment line (`global.columns`) is named `namedentity` and, correspondingly, the TSV file is named _namedentity.tsv_. Its first line should report headers, starting with `namedentity_id` and then any attributes associated with a named entity. The value in the first cell of all the non-header lines should correspond to the ones listed in the CoNLL-U file(s) for lookup purposes. For example:

```tsv
namedentity_id	type	form
1	ORG	General Assembly
2	DATE	10 December 1948
```

When parsed along with the CoNLL-U Plus lines above, this would associate the corresponding occurrence of the sequence "General Assembly" with a named entity of type `ORG` and the corresponding occurrence of "10 December 1948" with a named entity of type `DATE`.

Finally, you need to report a corresponding entity type in the template `.json` under the `layer` key, for example:

```json
"NamedEntity": {
    "abstract": false,
    "layerType": "span",
    "contains": "Token",
    "attributes": {
        "form": {
            "isGlobal": false,
            "type": "text",
            "nullable": false
        },
        "type": {
            "isGlobal": false,
            "type": "categorical",
            "nullable": true
        }
    }
},
```

Make sure to set the `abstract`, `layerType` and `contains` attributes as illustrated above. See the section [Convert and Upload](#convert-and-upload) for a full example of a template `.json` file.

One can then query named entities by specifying that they are contained in segments, and that they should contain specific tokens. For example, the following DQD query would match all the named entities the corpus' segments that contain an adjective token:

```dqd
Segment s

NamedEntity@s ne
    type = "ORG"

Token@ne t
    upos = "ADJ"

res => plain
    context
        s
    entities
        ne
```


##### Annotations of sequences of segments (e.g. Topics)


You can use `lcpcli` to define annotations on sequences of segments below the document level, for example topics. The approach is almost identical to the one for annotations of sequences of tokens; the following only describes the differences:

 - one does _not_ define a new column in `global.columns`
 - one does _not_ report the lookup indices in the token lines
 - one reports the indices as segment-level comments, named to match the TSV file; for example, a segment-level comment `# topic = 1` will look up the file _topic.tsv_ for a row whose first cell has the value `1`

Just like with token-level annotations, all consecutive segments sharing the same value in the annotation comment will be grouped together as one occurrence of that annotation.

One can then query segments that belong to specific topics. For example the following DQD query would match all the segments that belong to a topic named "bunny" (assuming `topic.csv` has a corresponding column `name`):

```dqd
Topic top
    name = "bunny"

Segment@top s

res => plain
    context
        s
    entities
        s
```

Note that while the documents represent the top annotation level containing segments, one cannot prepare a `.tsv` file as just described here; all the document annotations must be directly reported in the conllu files using the `# newdoc key = value` as described in the section **CoNLL-U Format**.


##### Time-aligned annotations

Your corpus can also include annotations that do not strictly group entities together. The example video corpus includes an annotation named _shot_ that is **time-aligned** but does not necessarily align with tokens or segments on the time axis (e.g. a shot can start in the middle of a sentence and end some time after its end)

Much like with the annotation types described above, you should also include a corresponding TSV file. The first column should list unique IDs; one column should be named `doc_id` and report the ID of the corresponding document (make sure to include corresponding `# newdoc id = <ID>` comments in your CoNLL-U files); two columns named `start` and `end` should list the time points for temporal anchoring, measured in seconds from the start of the document's media file; with extra columns for additional attributes. For example, `shot.tsv` starts with:

```tsv
shot_id	doc_id	start	end	view
1	Bunny	0.00	8.00	wide angle
2	Bunny	8.05	12.50	low angle
3	Bunny	12.75	16.00	face-cam
```

Your template `.json` file should report _Shot_ under `layer`, for example:

```json
"Shot": {
    "abstract": false,
    "layerType": "unit",
    "anchoring": {
        "location": false,
        "stream": false,
        "time": true
    },
    "attributes": {
        "view": {
            "type": "categorical"
        }
    }
},
```

Assuming the sentences are also time-aligned (as in the example corpus) you can then query segments that overlap with specific shots, for example:

```dqd
Segment s

Shot sh
    OR # either...
        AND # ... the shot start in the middle of the segment
            start >= s.start + 0.0s
            start <= s.end + 0.0s
        AND # ... or the short ends in the middle of the segment
            end >= s.start + 0.0s
            end <= s.end + 0.0s

res => plain
    context
        s
    entities
        ne
```

##### Global attributes

In some cases, it makes sense for multiple entity types to share references: in those cases, they can define _global attributes_. An example of a global attribute is a speaker or an agent that can have a name, an age, etc. and be associated with both a segment (a sentence) and, say, a gesture. The corpus template would include definitions along these lines:

```json
"globalAttributes": {
    "agent": {
        "type": "dict",
        "keys": {
            "name": {
                "type": "text"
            },
            "age": {
                "type": "number"
            }
        }
    }
},
"layer": {
    "Segment": {
        "abstract": false,
        "layerType": "span",
        "contains": "Token",
        "attributes": {
            "agent": {
                "ref": "agent"
            }
        }
    },
    "Gesture": {
        "abstract": false,
        "layerType": "unit",
        "anchoring": {
            "time": true
        },
        "attributes": {
            "agent": {
                "ref": "agent"
            }
        }
    }
}
```

You should include a file named `global_attribute_agent.tsv` (mind the singular on `attribute`) with three columns: `agent_id`, `name` and `age`, and reference the values of `agent_id` appropriately as a sentence-level comment in your CoNLL-U files as well as in a file named `gesture.tsv`. For example:

*global_attribute_agent.tsv*:
```tsv
agent_id	agent
10	{"name": "Jane Doe", "age": 37}
```

CoNLL-U file:
```conllu
## newdoc id = video1

## sent_id = 1
## agent_id = 10
The the _ _ _
```

*gesture.tsv*:
```tsv
gesture_id	agent_id	doc_id	start	end
1	10	video1	1.25	2.6
```

##### Media files

If your corpus includes media files, your `.json` template should report it under a `mediaSlots` key in `meta`, e.g.:

```json
"meta": {
    "name": "Free Single-Video Corpus",
    "author": "LiRI",
    "date": "2024-06-13",
    "version": 1,
    "corpusDescription": "Single, open-source video with annotated shots and a placeholder text stream from the Universal Declaration of Human Rights annotated with named entities",
    "mediaSlots": {
        "video": {
            "mediaType": "video",
            "isOptional": false
        }
    }
},
```

Your CoNLL-U file(s) should accordingly report each document's media file's name in a comment, like so:

```tsv
## newdoc video = bunny.mp4
```

The `.json` template should also define a main key named `tracks` to control what annotations will be represented along the time axis. For example the following will tell the interface to display separate timeline tracks for the shot, named entity and segment annotations, with the latter being subdivided in as many tracks as there are distinct values for the attribute `speaker` of the segments:

```json
"tracks": {
    "layers": {
        "Shot": {},
        "NamedEntity": {},
        "Segment": {
            "split": [
                "speaker"
            ]
        }
    }
}
```

Finally, your **output** corpus folder should include a subfolder named `media` in which all the referenced media files have been placed


##### Attribute types


The values of each attribute (on tokens, segments, documents or at any other level) have a **type**; the most common types are `text`, `number` or `categorical`. The attributes must be reported in the template `.json` file, along with their type (you can see an example in the section **Convert and Upload**)

 - `text` vs `categorical`: while both types correspond to alpha-numerical values, `categorical` is meant for attributes that have a limited number of possible values (typically, less than 100 distinct values) of a limited length (as a rule of thumb, each value can have up to 50 characters). There is no such limits on values of attributes of type `text`. When a user starts typing a constraint on an attribute of type `categorical`, the DQD editor will offer autocompletition suggestions. The attributes of type `text` will have their values listed in a dedicated table (`lcpcli`'s conversion step produces corresponding `.tsv` files) so a query that expresses a constraint on an attribute will be slower if that attribute if of type `text` than of type `categorical`

 - the type `labels` (with an `s` at the end) corresponds to a set of labels that users will be able to constrain in DQD using the `contain` keyword: for example, if an attribute named `genre` is of type `labels`, the user could write a constraint like `genre contain 'drama'` or `hobbies !contain 'comedy'`. The values of attributes of type `labels` should be one-line strings, with each value separated by a comma (`,`) character (as in, e.g., `# newdoc genre = drama, romance, coming of age, fiction`); as a consequence, no label can contain the character `,`.

 - the type `dict` corresponds to key-values pairs as represented in JSON

 - the type `date` requires values to be formatted in a way that can be parsed by PostgreSQL


#### Convert and Upload

1. Create a directory in which you have all your properly-fromatted CONLLU files

2. In the same directory, create a template `.json` file that describes your corpus structure (see above about the `attributes` key on `Document` and `Segment`), for example:

```json
{
    "meta": {
        "name": "Free Single-Video Corpus",
        "author": "LiRI",
        "date": "2024-06-13",
        "version": 1,
        "corpusDescription": "Single, open-source video with annotated shots and a placeholder text stream from the Universal Declaration of Human Rights annotated with named entities",
        "mediaSlots": {
            "video": {
                "mediaType": "video",
                "isOptional": false
            }
        }
    },
    "firstClass": {
        "document": "Document",
        "segment": "Segment",
        "token": "Token"
    },
    "layer": {
        "Token": {
            "abstract": false,
            "layerType": "unit",
            "anchoring": {
                "location": false,
                "stream": true,
                "time": true
            },
            "attributes": {
                "form": {
                    "isGlobal": false,
                    "type": "text",
                    "nullable": true
                },
                "lemma": {
                    "isGlobal": false,
                    "type": "text",
                    "nullable": false
                },
                "upos": {
                    "isGlobal": true,
                    "type": "categorical",
                    "nullable": true
                },
                "xpos": {
                    "isGlobal": false,
                    "type": "categorical",
                    "nullable": true
                },
                "ufeat": {
                    "isGlobal": false,
                    "type": "dict",
                    "nullable": true
                }
            }
        },
        "DepRel": {
            "abstract": true,
            "layerType": "relation",
            "attributes": {
                "udep": {
                    "type": "categorical",
                    "isGlobal": true,
                    "nullable": false
                },
                "source": {
                    "name": "dependent",
                    "entity": "Token",
                    "nullable": false
                },
                "target": {
                    "name": "head",
                    "entity": "Token",
                    "nullable": true
                },
                "left_anchor": {
                    "type": "number",
                    "nullable": false
                },
                "right_anchor": {
                    "type": "number",
                    "nullable": false
                }
            }
        },
        "NamedEntity": {
            "abstract": false,
            "layerType": "span",
            "contains": "Token",
            "attributes": {
                "form": {
                    "isGlobal": false,
                    "type": "text",
                    "nullable": false
                },
                "type": {
                    "isGlobal": false,
                    "type": "categorical",
                    "nullable": true
                }
            }
        },
        "Shot": {
            "abstract": false,
            "layerType": "span",
            "anchoring": {
                "location": false,
                "stream": false,
                "time": true
            },
            "attributes": {
                "view": {
                    "isGlobal": false,
                    "type": "categorical",
                    "nullable": false
                }
            }
        },
        "Segment": {
            "abstract": false,
            "layerType": "span",
            "contains": "Token",
            "attributes": {
                "meta": {
                    "text": {
                        "type": "text"
                    },
                    "start": {
                        "type": "text"
                    },
                    "end": {
                        "type": "text"
                    }
                }
            }
        },
        "Document": {
            "abstract": false,
            "contains": "Segment",
            "layerType": "span",
            "attributes": {
                "meta": {
                    "audio": {
                        "type": "text",
                        "isOptional": true
                    },
                    "video": {
                        "type": "text",
                        "isOptional": true
                    },
                    "start": {
                        "type": "number"
                    },
                    "end": {
                        "type": "number"
                    },
                    "name": {
                        "type": "text"
                    }
                }
            }
        }
    },
    "tracks": {
        "layers": {
            "Shot": {},
            "Segment": {},
            "NamedEntity": {}
        }
    }
}
```

3. If your corpus defines a character-anchored entity type such as named entities, make sure you also include a properly named and formatted TSV file for it in the directory (see [the Named Entities section](#named-entities))

4. Visit an LCP instance (e.g. _catchphrase_) and create a new project if you don't already have one where your corpus should go

5. Retrieve the API key and secret for your project by clicking on the button that says: "Create API Key"

    The secret will appear at the bottom of the page and remain visible only for 120s, after which it will disappear forever (you would then need to revoke the API key and create a new one)
    
    The key itself is listed above the button that says "Revoke API key" (make sure to **not** copy the line that starts with "Secret Key" along with the API key itself)

6. Once you have your API key and secret, you can start converting and uploading your corpus by running the following command:

```
lcpcli -i $CONLLU_FOLDER -o $OUTPUT_FOLDER -m upload -k $API_KEY -s $API_SECRET -p $PROJECT_NAME --live
```

- `$CONLLU_FOLDER` should point to the folder that contains your CONLLU files
- `$OUTPUT_FOLDER` should point to *another* folder that will be used to store the converted files to be uploaded
- `$API_KEY` is the key you copied from your project on LCP (still visible when you visit the page)
- `$API_SECRET` is the secret you copied from your project on LCP (only visible upon API Key creation)
- `$PROJECT_NAME` is the name of the project exactly as displayed on LCP -- it is case-sensitive, and space characters should be escaped
