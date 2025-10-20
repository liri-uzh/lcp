<template>
  <div id="query-editor">
    <div id="editor" ref="editor"></div>
  </div>
</template>

<style scoped>
#query-editor {
  text-align: left;
}
#editor {
  height: 500px;
  width: 100%;
}
</style>

<style>
/* need to use a non-scoped style because these classes are dynamically added */
.invalidDQDGlyph {
  border: 4px solid red;
  background: linear-gradient(45deg, rgba(0,0,0,0) 0%,rgba(0,0,0,0) 43%,#fff 45%,#fff 55%,rgba(0,0,0,0) 57%,rgba(0,0,0,0) 100%), linear-gradient(135deg, red 0%,red 43%,#fff 45%,#fff 55%,red 57%,red 100%);
  border-radius: 0.25em;
}
.invalidDQDLine {
	background: rgba(255, 55, 55, 0.15);
}
</style>

<script>
import * as monaco from "monaco-editor";
import DQDmonaco from "@/dqd_monaco.js";
// import DQDParser from "@/dqd_parser.js";


// function checkCode (content) {
//   let retval = null
//   class TreeIndenter extends DQDParser.Indenter {
//     static get NL_type() {
//       return "_NL";
//     }
//     get NL_type() {
//       return this.constructor.NL_type;
//     }
//     static get OPEN_PAREN_types() {
//       return [];
//     }
//     get OPEN_PAREN_types() {
//       return this.constructor.OPEN_PAREN_types;
//     }
//     static get CLOSE_PAREN_types() {
//       return [];
//     }
//     get CLOSE_PAREN_types() {
//       return this.constructor.CLOSE_PAREN_types;
//     }
//     static get INDENT_type() {
//       return "_INDENT";
//     }
//     get INDENT_type() {
//       return this.constructor.INDENT_type;
//     }
//     static get DEDENT_type() {
//       return "_DEDENT";
//     }
//     get DEDENT_type() {
//       return this.constructor.DEDENT_type;
//     }
//     static get tab_len() {
//       return 8;
//     }
//     get tab_len() {
//       return this.constructor.tab_len;
//     }
//   }
//   let parser = DQDParser.get_parser({
//     parser: "lalr",
//     postlex: new TreeIndenter
//   })
//   try {
//     parser.parser.parse(content)
//   }
//   catch (e) {
//     // console.log("ERROR", e.token_history, e.line, e.column)
//     retval = e.token_history
//   }
//   return retval
// }

// monaco.editor.defineTheme('DQDTheme', MonacoTheme)
monaco.editor.defineTheme('DQDTheme', {
  base: 'vs',
  inherit: true,
  colors: {
    "input.background": "#DDD6C1",
		"input.foreground": "#586E75",
  },
  rules: [
    { token: "identifier", foreground: "4287f5" },
    { token: "type.identifier", foreground: "2a7f62" },
    { token: "keyword", foreground: "ff6600" },
  ],
  tokenColors: [],
});

let editor = null;
let decorations = null;
// We use a hack to suggest continuation for attributes with categorical values
let suggestValuesCommandId = null; // Reference to a monaco command to immediately show the suggestion modal again
let suggestPrompt = undefined;  // This is either undefined, or set to a prompt to generate suggestions

const KEYWORDS = [
  'sequence ',
  'set',
  'group',
  'EXISTS\n    ',
  'NOT ',
  'AND\n    ',
  'OR\n    ',
  'plain\n    ',
  'analysis\n    ',
  'collocation\n    ',
  'center\n    ',
  'window\n    ',
  'space\n    ',
  'attribute\n    ',
  'attributes\n    ',
  'functions\n    ',
  'context\n    ',
  'entities\n    '
];

export default {
  name: "EditorView",
  data() {
    return {
      queryData: this.query,
      languageObj: null,
    };
  },
  props: ["query", "defaultQuery", "corpora", "invalidError", "errorList"],
  watch: {
    defaultQuery(){
      console.log('Default changed!');
      editor.getModel().setValue(this.defaultQuery);
    },
    corpora: {
      handler: function() {

        // Distroy old provider if exists
        if (this.languageObj) {
          this.languageObj()
        }

        // Reset highlighting
        this.setHighlighting();

        // Register a completion item provider for the new language
        const { dispose } = monaco.languages.registerCompletionItemProvider("DQDmonaco", {
          provideCompletionItems: (model, position) => {
            let suggestions = []
            var word = model.getWordUntilPosition(position), column = position.column;
            if (!suggestPrompt) {
              while (word.word=="" && column>0) {
                column--;
                let previousWord = model.getWordUntilPosition({lineNumber: position.lineNumber, column: column}).word;
                if (previousWord) {
                  suggestPrompt = previousWord;
                  break;
                }
              }
            }
            if (suggestPrompt) {
              if (suggestPrompt in this.corpora.corpus.layer)
                suggestions = [suggestPrompt.charAt(0).toLowerCase()];
              else {
                for (let lprops of Object.values(this.corpora.corpus.layer)) {
                  const attributes = lprops.attributes;
                  if (!(suggestPrompt in (attributes||{})))
                    continue;
                  if (attributes[suggestPrompt].type == "text")
                    suggestions.push('""');
                  if (attributes[suggestPrompt].type != "categorical")
                    continue;
                  let values = attributes[suggestPrompt].values;
                  if (!(values instanceof Array) && suggestPrompt in this.corpora.corpus.glob_attr)
                    values = this.corpora.corpus.glob_attr[suggestPrompt];
                  if (!(values instanceof Array) || values.length==0)
                    continue;
                  suggestions = [...suggestions, ...values.map(v=>`"${v}"`)];
                }
              }
            }
            var range = {
              startLineNumber: position.lineNumber,
              endLineNumber: position.lineNumber,
              startColumn: word.startColumn,
              endColumn: word.endColumn,
            };
            if (suggestions.length)
              suggestions = suggestions.map( (item) => Object({
                label: item,
                kind: monaco.languages.CompletionItemKind.Text,
                insertText: item,
                range: range
              }));
            else
              suggestions = this.mainSuggestions(range);
            suggestPrompt = undefined;
            return { suggestions: suggestions };
          },
          triggerCharacters: ["="," "]
        });
        this.languageObj = dispose
      },
      immediate: true
    },
    invalidError: {
      handler() {
        this.updateErrors();
      }
    },
    errorList: {
      handler() {
        const markers = (this.errorList||[]).map(errorLine => Object({
          severity: monaco.MarkerSeverity.Error,
          startLineNumber: errorLine.line,
          startColumn: errorLine.column,
          endLineNumber: errorLine.end_line,
          endColumn: errorLine.end_column,
          message: 'Error message ...'
        }));
        // change mySpecialLanguage to whatever your language id is
        monaco.editor.setModelMarkers(editor.getModel(), 'DQDmonaco', markers);
      }
    }
  },
  mounted() {
    monaco.languages.register({ id: "DQDmonaco" });
    this.setHighlighting();
    editor = monaco.editor.create(document.getElementById("editor"), {
      language: "DQDmonaco",
      scrollbar: {
        alwaysConsumeMouseWheel: false
      },
      value: this.query,
      theme: 'DQDTheme',
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      renderLineHighlight: "none",
      automaticLayout: true,
      folding: false,
      glyphMargin: true
    });

    editor.getModel().onDidChangeContent(() => {
      this.updateContent();
      this.updateErrors();
    });

    editor.getModel().updateOptions({ tabSize: 4 });

    // editor.onDidFocusEditorText(()=>{
    //   this.$refs.editor.style.height = "500px"
    //   editor.layout()
    // })
    // editor.onDidBlurEditorWidget(()=>{
    //   this.$refs.editor.style.height = "200px"
    //   editor.layout()
    // })

    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, ()=>console.log("Enter") || this.$emit("submit"));

    // Generate a command ID for manual triggering of autocompletion
    // eslint-disable-next-line no-unused-vars
    suggestValuesCommandId = editor.addCommand( 0, (_,suggestion) => this.triggerAutocomplete(suggestion) );

    editor.updateOptions({
      quickSuggestions: true,
      acceptSuggestionOnEnter: false, // disables accepting suggestions with Enter
    });

    window.addEventListener('contextmenu', e => {
      e.stopImmediatePropagation()
    }, true);
  },
  methods: {
    setHighlighting() {
      // Customize highlighting to current corpus
      const copyDQDmonaco = {...DQDmonaco}
      copyDQDmonaco.keywords = [...DQDmonaco.keywords];
      copyDQDmonaco.typeKeywords = [...DQDmonaco.typeKeywords];
      if (this.corpora && this.corpora.corpus && this.corpora.corpus.layer) {
        for (let [l,lp] of Object.entries(this.corpora.corpus.layer)) {
          const layer_type = lp.layerType;
          copyDQDmonaco.keywords.push(l);
          for (let [a,ap] of Object.entries(lp.attributes||{})) {
            let typeKeyword = a;
            if (layer_type == "relation" && "name" in ap)
              typeKeyword = ap.name;
              copyDQDmonaco.typeKeywords.push(typeKeyword);
          }
        }
      }
      monaco.languages.setMonarchTokensProvider("DQDmonaco", copyDQDmonaco);
    },
    mainSuggestions(range) {
      const s = [];
      if (!this.corpora || !this.corpora.corpus)
        return s;
      for (let [layer,props] of Object.entries(this.corpora.corpus.layer)) {
        s.push({
          label: layer,
          kind: monaco.languages.CompletionItemKind.Text,
          insertText: layer,
          range: range
        });
        let layer_type = props.layerType;
        for (let [a, ap] of Object.entries(props.attributes||{})) {
          let text = a;
          if (layer_type == "relation" && "name" in ap)
            text = ap.name;
          if (a == "meta") {
            for (let sa in ap)
              s.push({
                label: sa,
                kind: monaco.languages.CompletionItemKind.Keyword,
                insertText: `${sa} = `,
                range: range,
                command: {
                  id: suggestValuesCommandId,
                  title: "insert values",
                  arguments: [sa]
                }
              });
          }
          else
            s.push({
              label: text,
              kind: monaco.languages.CompletionItemKind.Keyword,
              insertText: `${text} ${ap.type == 'labels' ? 'contain' : '='} `,
              range: range,
              command: {
                id: suggestValuesCommandId,
                title: "insert values",
                arguments: [text]
              }
            });
        }
      }
      for (let k of KEYWORDS)
        s.push({
          label: k.trimEnd(),
          kind: monaco.languages.CompletionItemKind.Keyword,
          insertText: k,
          range: range
        });
      return s;
    },
    columnHeaders() {
      let keywords = []
      if (this.corpora && this.corpora.corpus) {
        let partitions = this.corpora.corpus.partitions
          ? this.corpora.corpus.partitions.values
          : [];
        let columns = this.corpora.corpus["mapping"]["layer"][this.corpora.corpus["segment"]];
        if (partitions.length) {
          columns = columns["partitions"][partitions[0]];
        }
        keywords = columns["prepared"]["columnHeaders"]
      }
      return keywords;
    },
    triggerAutocomplete(prompt) {
      if (!this.corpora || !this.corpora.corpus) return;
      suggestPrompt = prompt;
      setTimeout(()=>editor.trigger('', 'editor.action.triggerSuggest', {}), 1);
      return null;
    },
    processErrorMessage(message) {
      // if (message.startsWith("Unexpected token")) return "Invalid character";
      let msg = message.replace(/token [^(\s]+\([^),]+, ([^)]+)\)/,"$1")
                       .replace(/at line(.|\n)+$/,"");
      if (message.match(/Expected one of: \* STRING Previous tokens: \[Token\('OPERATOR', '[=<>]+'\)\]/))
        msg += " Provide a value for the comparison"
      return msg;
    },
    updateContent() {
      this.queryData = editor.getValue()
      this.$emit("update", this.queryData)
    },
    updateErrors() {
      if (decorations) decorations.clear();
      if (!this.invalidError) return null;
      try {
        let [line,column] = this.invalidError.match(/at line (\d+), column (\d+)/i).slice(1,3);
        setTimeout( ()=> {
          if (decorations) decorations.clear();
          if (!this.invalidError) return;
          let model = editor.getModel();
          [line,column] = [parseInt(line),parseInt(column)];
          let lineContent = model.getLineContent(line);
          if (column > lineContent.length) {
            let problematicText = this.invalidError.match(/^Unexpected \S+ \S+\([^),]+, '([^')]+)'\)/i);
            if (problematicText) {
              problematicText = problematicText[1];
              let oldline = line, nlines = model.getLineCount();
              while (line < nlines && !model.getLineContent(line).includes(problematicText)) line++;
              if (line < nlines)
                column = model.getLineContent(line).length;
              else
                line = oldline;
            }
          }
          decorations = editor.createDecorationsCollection([{
            range: new monaco.Range(parseInt(line), 1, parseInt(line), parseInt(column)),
            options: {
              isWholeLine: true,
              inlineClassName: "invalidDQDLine",
              glyphMarginClassName: "invalidDQDGlyph",
              glyphMarginHoverMessage: { value: this.processErrorMessage(this.invalidError) }
            }
          }]);
        } , 1000);
      } catch { /* nothing */ }
    }
  },
};
</script>
