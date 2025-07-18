import moment from 'moment';
import config from "@/config";

const Utils = {
    uuidv4(){
      return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
        (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
      )
    },
    sortHelper(a, b){
      if (typeof a === 'string' || a instanceof String){
        a = a.replace(/[^a-zA-Z 0-9]/g, "")
      }
      if (typeof b === 'string' || b instanceof String){
        b = b.replace(/[^a-zA-Z 0-9]/g, "")
      }
      return Intl.Collator().compare(a, b);
    },
    nFormatter: (num, digits) => {
      const lookup = [
        { value: 1, symbol: '' },
        { value: 1e6, symbol: ' M' },
        // { value: 1e9, symbol: 'G' },
        // { value: 1e12, symbol: 'T' },
        // { value: 1e15, symbol: 'P' },
        // { value: 1e18, symbol: 'E' },
      ];
      const rx = /\.0+$|(\.[0-9]*[1-9])0+$/;
      var item = lookup
        .slice()
        .reverse()
        .find(function (item) {
          return num >= item.value;
        });
      return item ? (num / item.value).toFixed(digits).replace(rx, '$1') + item.symbol : '0';
    },
    msToTime(duration) {
      var milliseconds = Math.floor((duration % 1000) / 100),
        seconds = Math.floor((duration / 1000) % 60),
        minutes = Math.floor((duration / (1000 * 60)) % 60),
        hours = Math.floor((duration / (1000 * 60 * 60)) % 24);

      hours = (hours < 10) ? "0" + hours : hours;
      minutes = (minutes < 10) ? "0" + minutes : minutes;
      seconds = (seconds < 10) ? "0" + seconds : seconds;

      return hours + ":" + minutes + ":" + seconds + "." + milliseconds;
    },
    secondsToTime(duration, showMilliseconds = false) {
      let seconds = Math.floor(duration % 60),
        minutes = Math.floor((duration / 60) % 60),
        hours = Math.floor((duration / (60 * 60)) % 24),
        milliseconds = Math.floor((duration % 1) * 1000);

      hours = (hours < 10) ? "0" + hours : hours;
      minutes = (minutes < 10) ? "0" + minutes : minutes;
      seconds = (seconds < 10) ? "0" + seconds : seconds;

      let retval = `${hours}:${minutes}:${seconds}`;
      if (showMilliseconds) {
        retval += `.${milliseconds}`;
      }
      return retval;
    },
    frameNumberToSeconds(frameNumber, frameRate = 25) {
      return frameNumber*1000/frameRate;
    },
    copyToClip(item) {
      let space = t=>!('spaceAfter' in t) || t.spaceAfter;
      let plain = item.map(t=>`${t.form}${space(t)?' ':''}`).join('');
      let rich = item.map(t=>`${t.group>=0?'<strong>':''}${t.form}${space(t)?' ':''}${t.group>=0?'</strong>':''}`).join('');
      function listener(e) {
        e.clipboardData.setData("text/html", rich);
        e.clipboardData.setData("text/plain", plain);
        e.preventDefault();
      }
      document.addEventListener("copy", listener);
      document.execCommand("copy");
      document.removeEventListener("copy", listener);
    },
    formatDate: (date, format = 'DD.MM.YYYY HH:mm') => {
      return date ? moment(date).format(format) : '';
    },
    dictToStr: (dict,{replaceYesNo, addTitles, reorder} = {}) => {
      if (!dict) return "";
      // default values
      replaceYesNo = replaceYesNo === undefined ? true : replaceYesNo;
      addTitles = addTitles === undefined ? false : addTitles;
      reorder = reorder && reorder instanceof Function ? reorder : ()=>0;
      const vals = [];
      for (let k of Object.keys(dict).sort(reorder)) {
        let val = dict[k]
        if (!val)
          continue;
        if (replaceYesNo && typeof(dict[k])=="string" && dict[k].match(/^(yes|no)$/i))
          val = dict[k].replace(/yes/i,"+").replace(/no/i,"-") + k;
        if (addTitles)
          val = `<abbr title="${k}">${val}</abbr>`;
        vals.push(val);
      }
      if (["number","string"].includes(typeof(dict)))
        vals.push(String(dict));
      return vals.join(" ")
    },
    slugify(str) {
      return String(str)
        .normalize('NFKD') // split accented characters into their base characters and diacritical marks
        .replace(/[\u0300-\u036f]/g, '') // remove all the accents, which happen to be all in the \u03xx UNICODE block.
        .trim() // trim leading or trailing whitespace
        // .toLowerCase() // convert to lowercase
        .replace(/[^a-zA-Z0-9 -]/g, '') // remove non-alphanumeric characters
        .replace(/\s+/g, '-') // replace spaces with hyphens
        .replace(/-+/g, '-'); // remove consecutive hyphens
    },
    validateEmail(email) {
      return String(email)
        .toLowerCase()
        .match(
          /^(([^<>()[\]\\.,;:\s@"]+(\.[^<>()[\]\\.,;:\s@"]+)*)|.(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/
        );
    },
    corpusDataType(corpus) {
      let corpusType = "text";
      if (corpus && corpus.meta && corpus.meta.mediaSlots) {
        for (let key of Object.keys(corpus.meta.mediaSlots)) {
          if (corpus.meta.mediaSlots[key].mediaType == "video") {
            corpusType = "video";
            break;
          }
          if (corpus.meta.mediaSlots[key].mediaType == "audio") {
            corpusType = "audio";
          }
        }
      }
      return corpusType
    },
    _hasProtocol(url) {
      // Regular expression to check if the URL starts with http:// or https://
      return /^(https?:\/\/)/i.test(url);
    },
    getURLWithProtocol(url) {
      if (!Utils._hasProtocol(url) && url) {
        return `https://${url}`; // Add default http:// if no protocol
      }
      return url; // Return the URL unchanged if it has a protocol
    },
    hasAccessToCorpus(corpus, userData) {
      // return (
      //   (userData.user.displayName) && (
      //     corpus.isSwissdox != true || userData.user.swissdoxUser == true
      //   )
      // );
      // Allow public corpora
      return corpus.authRequired != true
        || (
          (corpus.authRequired == true && userData.user.displayName) && (
            corpus.isSwissdox != true || userData.user.swissdoxUser == true
          )
        );
    },
    calculateSum(array) {
      return array.reduce((accumulator, value) => {
        return accumulator + value;
      }, 0);
    },
    getAppLink(appType, corpus) {
      let appLink = config.appLinks[appType]
      if (["catchphrase", "soundscript"].includes(appType)) {
        appLink = `${appLink}/query/${corpus.meta.id}/${Utils.slugify(corpus.shortname)}`
      }
      else {
        appLink = `${appLink}/query/${corpus.meta.id}/${Utils.slugify(corpus.shortname)}`
      }
      return appLink
    },
  }

  export default Utils
