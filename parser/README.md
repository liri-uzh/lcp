## Guidelines to write the Lark file

 - Add `// skip: rule_name` to remove it from the json schema
 - Add `// rename: rule_name1>new_name1 rule_name2>new_name2` to change the property name in the json schema

## Generate the cobquec schema from the grammar

The grammar file must end in `.lark` and the json schema file (optional) nust end in `.json`

 `python lark_to_cobquec.py dqd_grammar.lark cobquec.auto.json`

Drop the JSON output into the left text box at https://www.jsonschemavalidator.net/ to check that it is a valid JSON schema

## Run the whole pipeline at once

Run `./update.sh`

## Convert a DQD query to its JSON representation

 `python -m lcpvian dqd test.dqd`

The script will use the first `.lark` and the first `.json` files it finds in `lcpvian/parser` as its grammar and schema files, respectively

Note that queries **must** close all their indentations, so make sure to include a line break at the bottom of the test dqd file as needed

Drop the JSON output into the right text box at https://www.jsonschemavalidator.net/ (along with the corresponding schema on the left) to check that the schema validates it