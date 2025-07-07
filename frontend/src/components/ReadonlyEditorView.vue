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

export default {
  name: "ReadonlyEditorView",
  data() {
    return {
      queryData: this.query,
      languageObj: null,
    };
  },
  props: ["query", "defaultQuery", "invalidError", "errorList"],
  watch: {
    defaultQuery(){
      editor.getModel().setValue(this.defaultQuery);
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
    editor = monaco.editor.create(this.$refs.editor, {
      language: "DQDmonaco",
      scrollbar: {
        alwaysConsumeMouseWheel: false
      },
      readOnly: true,
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

    window.addEventListener('contextmenu', e => {
      e.stopImmediatePropagation()
    }, true);
  },
  methods: {
    processErrorMessage(message) {
      // if (message.startsWith("Unexpected token")) return "Invalid character";
      let msg = message.replace(/token [^(\s]+\([^),]+, ([^)]+)\)/,"$1")
                       .replace(/at line(.|\n)+$/,"");
      if (message.match(/Expected one of: \* STRING Previous tokens: \[Token\('OPERATOR', '[=<>]+'\)\]/))
        msg += " Provide a value for the comparison"
      return msg;
    },
    setHighlighting() {
      // Customize highlighting to current corpus
      const copyDQDmonaco = {...DQDmonaco}
      copyDQDmonaco.keywords = [...DQDmonaco.keywords];
      copyDQDmonaco.typeKeywords = [...DQDmonaco.typeKeywords];

      monaco.languages.setMonarchTokensProvider("DQDmonaco", copyDQDmonaco);
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
