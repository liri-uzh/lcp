# Importing CoNLL-U data sets

## CoNLL-U Format

The CoNLL-U format is documented at: https://universaldependencies.org/format.html

## Mappings

Besides the standard token-level CoNLL-U fields (`form`, `lemma`, `upos`, `xpos`, `feats`, `head`, `deprel`, `deps`) one can also provide document- and sentence-level annotations using comment lines in the files.

The `lcpcli` converter will treat all the comments that start with `# newdoc KEY = VALUE` as document-level attributes.
This means that if a CoNLL-U file contains the line `# newdoc author = Jane Doe`, then in LCP all the sentences from this file will be associated with a document attribute named `author` with value `"Jane Doe"`.

All other comment lines following the format `# key = value` will add an attribute to the _segment_ corresponding to the sentence below that line (i.e. not at the document level).

The key-value pairs in the `MISC` column of a token line will be treated as attributes of the corresponding token, with the exceptions of these key-value combinations:
 - `SpaceAfter=Yes` vs. `SpaceAfter=No` (case senstive) controls whether the token will be represented with a trailing space character in the database
 - `start=n.m|end=o.p` (case senstive) will align tokens, segments (sentences) and documents along a temporal axis, where `n.m` and `o.p` should be floating values in seconds

## Usage

To process all the .conllu files in `/path/to/conllu/files/` and generate prepared LCP files into `/path/for/output/files/`, use the following command:

```bash
lcpcli -i /path/to/conllu/files/ -o /path/for/output/files/
```

Then one can import the corpus using:

```bash
lcpcli -i $CONLLU_FOLDER -o $OUTPUT_FOLDER -m upload -k $API_KEY -s $API_SECRET -p $COLLECTION_NAME --live
```

See [Importing](importing.md) for explanations about this last command