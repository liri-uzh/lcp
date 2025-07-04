-- run DLL as lcp_production_owner

BEGIN;

\c lcp_production

CREATE EXTENSION IF NOT EXISTS rum WITH SCHEMA public;
COMMENT ON EXTENSION rum IS 'RUM index access method';

\c lcp_production lcp_production_owner

CREATE TYPE main.upload_status AS ENUM (
   'failed'
 , 'succeeded'
 , 'ongoing'
);

CREATE TABLE main.corpus (
   project_id        uuid
 , created_at        timestamptz    NOT NULL DEFAULT now()
 , corpus_id         int            GENERATED ALWAYS AS IDENTITY PRIMARY KEY
 , current_version   smallint       NOT NULL
 , enabled           bool           NOT NULL DEFAULT TRUE
 , corpus_template   jsonb          NOT NULL
 , description       text
 , mapping           jsonb
 , name              text           NOT NULL
 , sample_query      text
 , schema_path       text           NOT NULL
 , token_counts      jsonb
 , version_history   jsonb
 , UNIQUE (name, current_version, project_id)
);


CREATE TABLE main.inprogress_corpus (
   schema_path       uuid                 PRIMARY KEY
 , project_id        uuid
 , created_at        timestamptz          NOT NULL DEFAULT now()
 , corpus_id         int                  REFERENCES main.corpus
 , status            main.upload_status   NOT NULL
 , corpus_template   jsonb                NOT NULL
);


CREATE TYPE main.export_status AS ENUM (
   'querying'
 , 'failed'
 , 'exporting'
 , 'ready'
);

CREATE TABLE main.exports (
   query_hash        text                 NOT NULL
 , corpus_id         int                  NOT NULL
 , status            main.export_status   NOT NULL
 , message           text
 , user_id           text
 , format            text                 NOT NULL
 , n_offset          int                  NOT NULL
 , requested         int                  NOT NULL
 , delivered         int                  NOT NULL
 , fn                text                 NOT NULL
 , created_at        timestamptz          NOT NULL DEFAULT now()
 , modified_at       timestamptz          NOT NULL DEFAULT now()
);
CREATE INDEX ON main.exports (user_id);
CREATE INDEX ON main.exports (query_hash);

GRANT SELECT, INSERT, UPDATE ON main.exports TO lcp_production_owner;


-- user saved queries
CREATE TABLE lcp_user.queries (
   idx               uuid                 PRIMARY KEY
 , query             jsonb                NOT NULL
 , "user"            uuid                 NOT NULL
 , room              uuid
 , query_name        text
 , query_type        text
 , created_at        timestamptz          DEFAULT CURRENT_TIMESTAMP
);

-- global ENUM types
CREATE TYPE main.udep AS ENUM (
   'acl'
 , 'acl:adv'
 , 'acl:attr'
 , 'acl:cleft'
 , 'acl:cmpr'
 , 'acl:fixed'
 , 'acl:inf'
 , 'acl:relat'
 , 'acl:relcl'
 , 'acl:subj'
 , 'acl:tmod'
 , 'acl:tonp'
 , 'advcl'
 , 'advcl:abs'
 , 'advcl:cau'
 , 'advcl:cleft'
 , 'advcl:cmpr'
 , 'advcl:cond'
 , 'advcl:coverb'
 , 'advcl:eval'
 , 'advcl:lcl'
 , 'advcl:lto'
 , 'advcl:mcl'
 , 'advcl:objective'
 , 'advcl:pred'
 , 'advcl:relcl'
 , 'advcl:svc'
 , 'advcl:tcl'
 , 'advmod'
 , 'advmod:adj'
 , 'advmod:arg'
 , 'advmod:cau'
 , 'advmod:comp'
 , 'advmod:deg'
 , 'advmod:det'
 , 'advmod:df'
 , 'advmod:dir'
 , 'advmod:emph'
 , 'advmod:eval'
 , 'advmod:fixed'
 , 'advmod:foc'
 , 'advmod:freq'
 , 'advmod:lfrom'
 , 'advmod:lmod'
 , 'advmod:lmp'
 , 'advmod:loc'
 , 'advmod:locy'
 , 'advmod:lto'
 , 'advmod:mmod'
 , 'advmod:mode'
 , 'advmod:neg'
 , 'advmod:obl'
 , 'advmod:que'
 , 'advmod:tfrom'
 , 'advmod:tlocy'
 , 'advmod:tmod'
 , 'advmod:to'
 , 'advmod:tto'
 , 'amod'
 , 'amod:att'
 , 'amod:attlvc'
 , 'amod:flat'
 , 'appos'
 , 'appos:nmod'
 , 'appos:trans'
 , 'aux'
 , 'aux:aff'
 , 'aux:aspect'
 , 'aux:caus'
 , 'aux:clitic'
 , 'aux:cnd'
 , 'aux:ex'
 , 'aux:exhort'
 , 'aux:imp'
 , 'aux:nec'
 , 'aux:neg'
 , 'aux:opt'
 , 'aux:part'
 , 'aux:pass'
 , 'aux:pot'
 , 'aux:q'
 , 'aux:tense'
 , 'case'
 , 'case:acc'
 , 'case:adv'
 , 'case:aff'
 , 'case:det'
 , 'case:gen'
 , 'case:loc'
 , 'case:pred'
 , 'case:voc'
 , 'cc'
 , 'cc:nc'
 , 'ccomp'
 , 'ccomp:cleft'
 , 'ccomp:obj'
 , 'ccomp:obl'
 , 'ccomp:pmod'
 , 'ccomp:pred'
 , 'cc:preconj'
 , 'clf'
 , 'clf:det'
 , 'compound'
 , 'compound:a'
 , 'compound:adj'
 , 'compound:affix'
 , 'compound:amod'
 , 'compound:apr'
 , 'compound:atov'
 , 'compound:dir'
 , 'compound:ext'
 , 'compound:lvc'
 , 'compound:nn'
 , 'compound:preverb'
 , 'compound:pron'
 , 'compound:prt'
 , 'compound:quant'
 , 'compound:redup'
 , 'compound:smixut'
 , 'compound:svc'
 , 'compound:verbnoun'
 , 'compound:vmod'
 , 'compound:vo'
 , 'compound:vv'
 , 'compound:z'
 , 'conj'
 , 'conj:expl'
 , 'conj:extend'
 , 'conj:redup'
 , 'conj:svc'
 , 'cop'
 , 'cop:expl'
 , 'cop:locat'
 , 'cop:own'
 , 'csubj'
 , 'csubj:asubj'
 , 'csubj:cleft'
 , 'csubj:cop'
 , 'csubj:outer'
 , 'csubj:pass'
 , 'csubj:pred'
 , 'csubj:vsubj'
 , 'dep'
 , 'dep:aff'
 , 'dep:agr'
 , 'dep:alt'
 , 'dep:ana'
 , 'dep:aux'
 , 'dep:comp'
 , 'dep:conj'
 , 'dep:cop'
 , 'dep:emo'
 , 'dep:infl'
 , 'dep:mark'
 , 'dep:mod'
 , 'dep:pos'
 , 'dep:redup'
 , 'dep:ss'
 , 'det'
 , 'det:adj'
 , 'det:clf'
 , 'det:noun'
 , 'det:numgov'
 , 'det:nummod'
 , 'det:pmod'
 , 'det:poss'
 , 'det:predet'
 , 'det:pron'
 , 'det:rel'
 , 'discourse'
 , 'discourse:conn'
 , 'discourse:emo'
 , 'discourse:filler'
 , 'discourse:intj'
 , 'discourse:sp'
 , 'dislocated'
 , 'dislocated:cleft'
 , 'dislocated:csubj'
 , 'dislocated:nsubj'
 , 'dislocated:obj'
 , 'dislocated:subj'
 , 'dislocated:vo'
 , 'expl'
 , 'expl:comp'
 , 'expl:impers'
 , 'expl:pass'
 , 'expl:poss'
 , 'expl:pv'
 , 'expl:subj'
 , 'fixed'
 , 'flat'
 , 'flat:abs'
 , 'flat:date'
 , 'flat:dist'
 , 'flat:foreign'
 , 'flat:frac'
 , 'flat:gov'
 , 'flat:name'
 , 'flat:num'
 , 'flat:number'
 , 'flat:range'
 , 'flat:redup'
 , 'flat:repeat'
 , 'flat:sibl'
 , 'flat:time'
 , 'flat:title'
 , 'flat:vv'
 , 'goeswith'
 , 'iobj'
 , 'iobj:agent'
 , 'iobj:appl'
 , 'iobj:patient'
 , 'list'
 , 'mark'
 , 'mark:adv'
 , 'mark:advmod'
 , 'mark:aff'
 , 'mark:pcomp'
 , 'mark:plur'
 , 'mark:prt'
 , 'mark:q'
 , 'mark:rel'
 , 'nmod'
 , 'nmod:agent'
 , 'nmod:appos'
 , 'nmod:arg'
 , 'nmod:att'
 , 'nmod:attlvc'
 , 'nmod:attr'
 , 'nmod:bahuv'
 , 'nmod:cau'
 , 'nmod:comp'
 , 'nmod:det'
 , 'nmod:flat'
 , 'nmod:gen'
 , 'nmod:gobj'
 , 'nmod:gsubj'
 , 'nmod:lfrom'
 , 'nmod:lmod'
 , 'nmod:npmod'
 , 'nmod:obj'
 , 'nmod:obl'
 , 'nmod:part'
 , 'nmod:poss'
 , 'nmod:pred'
 , 'nmod:prep'
 , 'nmod:prp'
 , 'nmod:redup'
 , 'nmod:relat'
 , 'nmod:subj'
 , 'nmod:tmod'
 , 'nsubj'
 , 'nsubj:advmod'
 , 'nsubj:aff'
 , 'nsubj:bfoc'
 , 'nsubj:caus'
 , 'nsubj:cleft'
 , 'nsubj:cop'
 , 'nsubj:expl'
 , 'nsubj:ifoc'
 , 'nsubj:lfoc'
 , 'nsubj:lvc'
 , 'nsubj:nc'
 , 'nsubj:nn'
 , 'nsubj:obj'
 , 'nsubj:outer'
 , 'nsubj:pass'
 , 'nsubj:periph'
 , 'nsubj:pred'
 , 'nsubj:quasi'
 , 'nsubj:x'
 , 'nsubj:xsubj'
 , 'nummod'
 , 'nummod:det'
 , 'nummod:entity'
 , 'nummod:flat'
 , 'nummod:gov'
 , 'obj'
 , 'obj:advmod'
 , 'obj:advneg'
 , 'obj:agent'
 , 'obj:appl'
 , 'obj:caus'
 , 'obj:lvc'
 , 'obj:obl'
 , 'obj:periph'
 , 'obl'
 , 'obl:about'
 , 'obl:ad'
 , 'obl:adj'
 , 'obl:adv'
 , 'obl:advmod'
 , 'obl:agent'
 , 'obl:appl'
 , 'obl:arg'
 , 'obl:cau'
 , 'obl:cmp'
 , 'obl:cmpr'
 , 'obl:comp'
 , 'obl:dat'
 , 'obl:freq'
 , 'obl:inst'
 , 'obl:iobj'
 , 'obl:lfrom'
 , 'obl:lmod'
 , 'obl:lmp'
 , 'obl:lto'
 , 'obl:lvc'
 , 'obl:mcl'
 , 'obl:mod'
 , 'obl:npmod'
 , 'obl:obj'
 , 'obl:orphan'
 , 'obl:own'
 , 'obl:patient'
 , 'obl:pmod'
 , 'obl:poss'
 , 'obl:prep'
 , 'obl:sentcon'
 , 'obl:smod'
 , 'obl:subj'
 , 'obl:tmod'
 , 'obl:with'
 , 'orphan'
 , 'orphan:missing'
 , 'parataxis'
 , 'parataxis:appos'
 , 'parataxis:conj'
 , 'parataxis:coord'
 , 'parataxis:deletion'
 , 'parataxis:discourse'
 , 'parataxis:dislocated'
 , 'parataxis:hashtag'
 , 'parataxis:insert'
 , 'parataxis:mod'
 , 'parataxis:newsent'
 , 'parataxis:nsubj'
 , 'parataxis:obj'
 , 'parataxis:parenth'
 , 'parataxis:rel'
 , 'parataxis:rep'
 , 'parataxis:restart'
 , 'parataxis:rt'
 , 'parataxis:sentence'
 , 'parataxis:trans'
 , 'parataxis:url'
 , 'punct'
 , 'reparandum'
 , 'root'
 , 'vocative'
 , 'vocative:cl'
 , 'vocative:mention'
 , 'xcomp'
 , 'xcomp:adj'
 , 'xcomp:cleft'
 , 'xcomp:ds'
 , 'xcomp:obj'
 , 'xcomp:pred'
 , 'xcomp:subj'
 , 'xcomp:vcomp'
);


CREATE TYPE main.upos AS ENUM (
   'ADJ'
 , 'ADP'
 , 'ADV'
 , 'AUX'
 , 'CCONJ'
 , 'DET'
 , 'INTJ'
 , 'NOUN'
 , 'NUM'
 , 'PART'
 , 'PRON'
 , 'PROPN'
 , 'PUNCT'
 , 'SCONJ'
 , 'SYM'
 , 'VERB'
 , 'X'
);

GRANT SELECT
   ON main.corpus
    , main.inprogress_corpus
    , main.exports
    , lcp_user.queries
   TO lcp_production_maintenance
    , lcp_production_monitoring
    , lcp_production_importer
    , lcp_production_web_user
    ;


COMMIT;

