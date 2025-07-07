let config = {};

const testUserHeaders = {
  "X-Remote-User": "firstname.lastname@uzh.ch",
  "X-Display-Name": "Firstname Lastname",
  "X-Mail": "firstname.lastname@uzh.ch",
  "X-Edu-Person-Unique-Id": "test_user_uniq_id@uzh.ch",
}
// const testUserHeaders = {}

if (process.env.APP_TYPE == "videoscope") {
  if (process.env.NODE_ENV == "production") {
    config = {
      appName: "videoscope",
      apiUrl: "https://videoscope.linguistik.uzh.ch/be",
      wsUrl: "wss://videoscope.linguistik.uzh.ch/ws",
      apiHeaders: {},
      sentryDSN: null,
      baseMediaUrl: "https://videoscope.linguistik.uzh.ch/media",
    };
  } else if (process.env.NODE_ENV == "staging") {
    config = {
      appName: "videoscope",
      apiUrl: "https://videoscope.test.linguistik.uzh.ch/be",
      wsUrl: "wss://videoscope.test.linguistik.uzh.ch/ws",
      apiHeaders: {},
      sentryDSN: null,
      baseMediaUrl: "https://videoscope.test.linguistik.uzh.ch/media",
    };
  } else if (process.env.NODE_ENV == "USI") {
    config = {
      appName: "videoscope",
      apiUrl: "https://videoscope.lcp.usi.ch/be",
      wsUrl: "wss://videoscope.lcp.usi.ch/ws",
      apiHeaders: {},
      sentryDSN: null,
      baseMediaUrl: "https://videoscope.lcp.usi.ch/media/",
    }
  } else {
    // development
    config = {
      appName: "videoscope",
      apiUrl: "http://localhost:9090",
      wsUrl: "ws://localhost:9090/ws",
      apiHeaders: testUserHeaders,
      sentryDSN: null,
      baseMediaUrl: "http://localhost:8000",
    };
  }
}
else if (process.env.APP_TYPE == "soundscript") {
  if (process.env.NODE_ENV === "production") {
    config = {
      appName: "soundscript",
      apiUrl: "https://soundscript.linguistik.uzh.ch/be",
      wsUrl: "wss://soundscript.linguistik.uzh.ch/ws",
      apiHeaders: {},
      sentryDSN: null,
      baseMediaUrl: "https://soundscript.linguistik.uzh.ch/media",
    };
  } else if (process.env.NODE_ENV === "staging") {
    config = {
      appName: "soundscript",
      apiUrl: "https://soundscript.test.linguistik.uzh.ch/be",
      wsUrl: "wss://soundscript.test.linguistik.uzh.ch/ws",
      apiHeaders: {},
      sentryDSN: null,
      baseMediaUrl: "https://soundscript.test.linguistik.uzh.ch/media",
    };
  } else if (process.env.NODE_ENV === "USI") {
    config = {
      appName: "soundscript",
      apiUrl: "https://soundscript.lcp.usi.ch/be",
      wsUrl: "wss://soundscript.lcp.usi.ch/ws",
      apiHeaders: {},
      sentryDSN: null,
      baseMediaUrl: "https://soundscript.lcp.usi.ch/media/",
    };
  } else {
    // development
    config = {
      appName: "soundscript",
      apiUrl: "http://localhost:9090",
      wsUrl: "ws://localhost:9090/ws",
      apiHeaders: testUserHeaders,
      sentryDSN: null,
      baseMediaUrl: "http://localhost:8000",
    };
  }
}
else if (process.env.APP_TYPE == "catchphrase") {
  if (process.env.NODE_ENV === "production") {
    config = {
      appName: "catchphrase",
      apiUrl: "https://catchphrase.linguistik.uzh.ch/be",
      wsUrl: "wss://catchphrase.linguistik.uzh.ch/ws",
      apiHeaders: {},
      sentryDSN: null,
      baseMediaUrl: "https://catchphrase.linguistik.uzh.ch/media",
    };
  } else if (process.env.NODE_ENV === "staging") {
    config = {
      appName: "catchphrase",
      apiUrl: "https://catchphrase.test.linguistik.uzh.ch/be",
      wsUrl: "wss://catchphrase.test.linguistik.uzh.ch/ws",
      apiHeaders: {},
      sentryDSN: null,
      baseMediaUrl: "https://catchphrase.test.linguistik.uzh.ch/media",
    };
  } else if (process.env.NODE_ENV === "USI") {
    config = {
      appName: "catchphrase",
      apiUrl: "https://catchphrase.lcp.usi.ch/be",
      wsUrl: "wss://catchphrase.lcp.usi.ch/ws",
      apiHeaders: {},
      sentryDSN: null,
      baseMediaUrl: "https://catchphrase.lcp.usi.ch/media/",
    };
  } else {
    // development
    config = {
      appName: "catchphrase",
      apiUrl: "http://localhost:9090",
      wsUrl: "ws://localhost:9090/ws",
      apiHeaders: testUserHeaders,
      sentryDSN: null,
      baseMediaUrl: "http://localhost:8000",
    };
  }
}
else if (process.env.APP_TYPE == "lcphome") {
  // LCP HOME
  if (process.env.NODE_ENV === "production") {
    config = {
      appName: "LCP",
      apiUrl: "https://lcp.linguistik.uzh.ch/be",
      wsUrl: "wss://lcp.linguistik.uzh.ch/ws",
      apiHeaders: {},
      sentryDSN: null,
    };
  } else if (process.env.NODE_ENV === "staging") {
    config = {
      appName: "LCP",
      apiUrl: "https://lcp.test.linguistik.uzh.ch/be",
      wsUrl: "wss://lcp.test.linguistik.uzh.ch/ws",
      apiHeaders: {},
      sentryDSN: null,
    };
  } else if (process.env.NODE_ENV === "USI") {
    config = {
      appName: "LCP",
      apiUrl: "https://lcp.usi.ch/be",
      wsUrl: "wss://lcp.usi.ch/ws",
      apiHeaders: {},
      sentryDSN: null,
      baseMediaUrl: "https://lcp.usi.ch/media/",
    };
  } else {
    // development
    config = {
      appName: "LCP",
      apiUrl: "http://localhost:9090",
      wsUrl: "ws://localhost:9090/ws",
      apiHeaders: testUserHeaders,
      sentryDSN: null,
      baseMediaUrl: "http://localhost:9090/media/",
    };
  }
}
else {
  // LCP
  if (process.env.NODE_ENV === "production") {
    config = {
      appName: "LCP",
      apiUrl: "https://lcp.linguistik.uzh.ch/be",
      wsUrl: "wss://lcp.linguistik.uzh.ch/ws",
      apiHeaders: {},
      sentryDSN: null,
    };
  } else if (process.env.NODE_ENV === "staging") {
    config = {
      appName: "LCP",
      apiUrl: "https://lcp.test.linguistik.uzh.ch/be",
      wsUrl: "wss://lcp.test.linguistik.uzh.ch/ws",
      apiHeaders: {},
      sentryDSN: null,
    };
  } else if (process.env.NODE_ENV === "USI") {
    config = {
      appName: "LCP",
      apiUrl: "https://lcp.usi.ch/be",
      wsUrl: "wss://lcp.usi.ch/ws",
      apiHeaders: {},
      sentryDSN: null,
      baseMediaUrl: "https://lcp.usi.ch/media/",
    };
  } else {
    // development
    config = {
      appName: "LCP",
      apiUrl: "http://localhost:9090",
      wsUrl: "ws://localhost:9090/ws",
      apiHeaders: testUserHeaders,
      sentryDSN: null,
      baseMediaUrl: "http://localhost:8090/",
    };
  }
}
config.appType = process.env.APP_TYPE;

if (process.env.NODE_ENV == "production") {
  config['appLinks'] = {
    "lcphome": "https://lcp.linguistik.uzh.ch",
    "catchphrase": "https://catchphrase.linguistik.uzh.ch",
    "soundscript": "https://soundscript.linguistik.uzh.ch",
    "videoscope": "https://videoscope.linguistik.uzh.ch",
  }
}
else if (process.env.NODE_ENV == "staging") {
  config['appLinks'] = {
    "lcphome": "https://lcp.test.linguistik.uzh.ch",
    "catchphrase": "https://catchphrase.test.linguistik.uzh.ch",
    "soundscript": "https://soundscript.test.linguistik.uzh.ch",
    "videoscope": "https://videoscope.test.linguistik.uzh.ch"
  }
}
else if (process.env.NODE_ENV == "USI") {
  config['appLinks'] = {
    "catchphrase": "https://catchphrase.lcp.usi.ch",
    "soundscript": "https://soundscript.lcp.usi.ch",
    "videoscope": "https://videoscope.lcp.usi.ch"
  }
}
else {
  config['appLinks'] = {
    "lcphome": "http://localhost:8080",
    "catchphrase": "http://localhost:8081",
    "soundscript": "http://localhost:8082",
    "videoscope": "http://localhost:8083"
  }
}

export default config;
